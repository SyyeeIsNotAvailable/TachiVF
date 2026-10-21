"""Update the selected Keiyoushi sources, preserving local changes with a three-way merge."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile
import urllib.request


ROOT = Path(__file__).resolve().parents[1]
REPOSITORY = 'keiyoushi/extensions-source'
STATE = 'docs/upstream/sync-state.json'
MODULES = ('animesama', 'aniverse', 'mangakawaii', 'mangascantrad')
DIRECTORIES = tuple('src/fr/' + module for module in MODULES) + ('lib-multisrc/madara', 'lib/i18n', 'core', 'compiler', 'common', 'gradle')
FILES = ('.editorconfig', '.gitattributes', '.gitignore', 'AGENTS.md', 'CONTRIBUTING.md', 'LICENSE', 'build.gradle.kts', 'gradle.properties', 'settings.gradle.kts', 'gradlew', 'gradlew.bat', 'ext-bootstrap.py', 'ktlintCodeStyle.xml')


class SyncConflict(RuntimeError):
    pass


def selected(path):
    return path in FILES or any(path.startswith(directory + '/') for directory in DIRECTORIES)


def blob(data):
    return hashlib.sha1(b'blob ' + str(len(data)).encode() + b'\0' + data).hexdigest()


def git(directory, *arguments):
    return subprocess.check_output(['git', '-C', str(directory), *arguments], stderr=subprocess.PIPE)


def temporary():
    directory = tempfile.TemporaryDirectory(prefix='tachivf-sync-')
    if not Path(directory.name).resolve().is_relative_to(Path(tempfile.gettempdir()).resolve()):
        raise ValueError('Unexpected temporary directory')
    return directory


def merge_file(path, base, local, upstream):
    if local == base or local == upstream:
        return upstream
    if upstream == base:
        return local
    with temporary() as directory:
        paths = [Path(directory) / name for name in ('local', 'base', 'upstream')]
        for destination, data in zip(paths, (local, base, upstream)):
            destination.write_bytes(data)
        result = subprocess.run(['git', 'merge-file', '-p', *map(str, paths)], capture_output=True)
    if result.returncode:
        raise SyncConflict(f'{path}: local and upstream changes conflict; nothing applied')
    return result.stdout


def fetch(url):
    with urllib.request.urlopen(url, timeout=30) as response:
        return response.read()


def merge_wrapper(base, local, upstream, download=fetch):
    def url(data):
        return re.search(rb'^distributionUrl=(.+)$', data, re.M).group(1)
    old_url, local_url = url(base), url(local)
    if local_url != old_url.replace(b'services.gradle.org', b'downloads.gradle.org'):
        return merge_file('gradle/wrapper/gradle-wrapper.properties', base, local, upstream)
    def strip_checksum(data):
        return re.sub(rb'^distributionSha256Sum=.*\n?', b'', data, flags=re.M)
    merged = merge_file('Gradle wrapper', strip_checksum(base), strip_checksum(local.replace(local_url, old_url, 1)), strip_checksum(upstream))
    distribution = url(merged).replace(b'services.gradle.org', b'downloads.gradle.org')
    public_url = distribution.decode().replace('\\:', ':')
    if not re.fullmatch(r'https://downloads\.gradle\.org/distributions/gradle-[\w.-]+-(bin|all)\.zip', public_url):
        raise SyncConflict('Unexpected Gradle distribution URL')
    checksum = download(public_url + '.sha256').strip()
    if not re.fullmatch(rb'[a-f0-9]{64}', checksum):
        raise SyncConflict('Invalid Gradle checksum')
    return re.sub(rb'^distributionUrl=.*$', lambda _: b'distributionUrl=' + distribution + b'\ndistributionSha256Sum=' + checksum, merged, flags=re.M)


def synchronize(root, upstream, baseline, load_base):
    head = git(upstream, 'rev-parse', 'HEAD').decode().strip()
    current = {}
    for entry in git(upstream, 'ls-tree', '-r', '-z', 'HEAD').split(b'\0'):
        if not entry:
            continue
        metadata, raw_path = entry.split(b'\t', 1)
        mode, kind, sha = metadata.decode().split()
        path = raw_path.decode()
        if selected(path):
            if mode not in ('100644', '100755') or kind != 'blob':
                raise SyncConflict(f'{path}: unsupported upstream file')
            current[path] = {'sha': sha, 'mode': mode}
    for module in MODULES:
        if f'src/fr/{module}/build.gradle.kts' not in current:
            raise SyncConflict(f'{module}: selected extension removed or moved upstream')
    plan = {}
    for path in sorted(set(baseline['files']) | set(current)):
        previous, latest = baseline['files'].get(path), current.get(path)
        if previous == latest:
            continue
        destination = root / path
        if not destination.resolve().is_relative_to(root.resolve()):
            raise SyncConflict('Invalid upstream path')
        local = destination.read_bytes() if destination.is_file() else None
        if local is not None and path.endswith('.bat'):
            local = local.replace(b'\r\n', b'\n')
        if latest is None:
            if local is not None and blob(local) != previous['sha']:
                raise SyncConflict(f'{path}: upstream deletion would erase local changes')
            plan[path] = None
            continue
        remote = (upstream / path).read_bytes()
        if blob(remote) != latest['sha']:
            raise SyncConflict(f'{path}: upstream content does not match its Git hash')
        if previous is None:
            if local is not None and local != remote:
                raise SyncConflict(f'{path}: new upstream file collides with a local file')
            result = remote
        elif local is None:
            raise SyncConflict(f'{path}: locally deleted file changed upstream')
        elif blob(local) == previous['sha']:
            result = remote
        else:
            base = load_base(path)
            if blob(base) != previous['sha']:
                raise SyncConflict(f'{path}: invalid merge baseline')
            result = merge_wrapper(base, local, remote) if path == 'gradle/wrapper/gradle-wrapper.properties' else merge_file(path, base, local, remote)
        plan[path] = result
    if not plan:
        return {}, baseline
    return plan, {'repository': REPOSITORY, 'revision': head, 'files': current}


def main(apply):
    state_file = ROOT / STATE
    baseline = json.loads(state_file.read_text(encoding='utf-8'))
    url = f'https://github.com/{REPOSITORY}.git'
    remote = git(ROOT, 'ls-remote', url, 'refs/heads/main').decode().split()[0]
    if remote == baseline['revision']:
        print('Keiyoushi unchanged; nothing to synchronize.')
        return
    if apply and git(ROOT, 'status', '--porcelain').strip():
        raise SyncConflict('The working tree must be clean before applying upstream changes')
    with temporary() as directory:
        upstream = Path(directory) / 'upstream'
        subprocess.run(['git', 'clone', '--depth=1', '--filter=blob:none', '--no-checkout', url, str(upstream)], check=True, capture_output=True)
        git(upstream, 'sparse-checkout', 'set', '--no-cone', *('/' + path + '/' for path in DIRECTORIES), *('/' + path for path in FILES))
        git(upstream, 'checkout', 'HEAD')
        def load_base(path):
            return fetch(f"https://raw.githubusercontent.com/{REPOSITORY}/{baseline['revision']}/{path}")
        plan, updated = synchronize(ROOT, upstream, baseline, load_base)
    if apply and plan:
        for path, data in plan.items():
            destination = ROOT / path
            if data is None:
                destination.unlink(missing_ok=True)
            else:
                destination.parent.mkdir(parents=True, exist_ok=True)
                destination.write_bytes(data)
                if os.name != 'nt':
                    destination.chmod(int(updated['files'][path]['mode'], 8) & 0o777)
        state_file.write_text(json.dumps(updated, indent=2, sort_keys=True) + '\n', encoding='utf-8')
    print(f'{len(plan)} upstream files changed' + ('; applied.' if apply else '; check only.'))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args()
    main(args.apply)
