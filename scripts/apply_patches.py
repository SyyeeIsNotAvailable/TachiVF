"""Apply the ordered Japscan patches over the committed upstream source before building."""
import argparse
from pathlib import Path, PurePosixPath
import subprocess
import tempfile


ROOT = Path(__file__).resolve().parents[1]
SOURCE = 'src/fr/japscan/'


class PatchConflict(RuntimeError):
    pass


def git(root, *args):
    return subprocess.check_output(['git', '-C', str(root), *args], stderr=subprocess.PIPE)


def prepare(root):
    directory = root / 'patches/japscan'
    series = [line.strip() for line in (directory / 'series').read_text(encoding='utf-8').splitlines()
              if line.strip() and not line.lstrip().startswith('#')]
    patches = []
    targets = set()
    for name in series:
        if Path(name).name != name or not name.endswith('.patch'):
            raise PatchConflict(f'Invalid patch name: {name}')
        patch = directory / name
        for record in git(root, 'apply', '--numstat', '-z', str(patch.resolve())).split(b'\0'):
            if not record:
                continue
            parts = record.decode().split('\t', 2)
            path = parts[-1]
            if len(parts) != 3 or not path.startswith(SOURCE) or '\\' in path or '..' in PurePosixPath(path).parts:
                raise PatchConflict(f'{name}: patch must only change {SOURCE}')
            targets.add(path)
        patches.append(patch.resolve())
    if not patches:
        return {}, 0
    # Start with HEAD, so a second local build produces the same result without applying twice.
    originals = {}
    with tempfile.TemporaryDirectory(prefix='tachivf-patches-') as temporary:
        staging = Path(temporary)
        if not staging.resolve().is_relative_to(Path(tempfile.gettempdir()).resolve()):
            raise PatchConflict('Unexpected temporary directory')
        for path in targets:
            try:
                content = git(root, 'show', f'HEAD:{path}')
            except subprocess.CalledProcessError:
                content = None
            originals[path] = content
            if content is not None:
                target = staging / path
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(content)
        for patch in patches:
            try:
                git(staging, 'apply', '--check', '--whitespace=error', str(patch))
                git(staging, 'apply', '--whitespace=error', str(patch))
            except subprocess.CalledProcessError as error:
                raise PatchConflict(f'{patch.name}: incompatible with upstream; nothing applied\n'
                                    + error.stderr.decode(errors='replace')) from error
        plan = {}
        for path in targets:
            destination = root / path
            if not destination.resolve().is_relative_to((root / SOURCE).resolve()):
                raise PatchConflict(f'Invalid patch target: {path}')
            staged = staging / path
            result = staged.read_bytes() if staged.is_file() else None
            local = destination.read_bytes() if destination.is_file() else None
            normalized = local.replace(b'\r\n', b'\n') if local is not None else None
            if local not in (originals[path], result) and normalized not in (originals[path], result):
                raise PatchConflict(f'{path}: uncommitted edits; nothing applied')
            plan[path] = result
    return plan, len(patches)


def apply(root=ROOT, check=False):
    plan, count = prepare(root)
    if not check:
        for path, content in plan.items():
            destination = root / path
            if content is None:
                destination.unlink(missing_ok=True)
            else:
                destination.parent.mkdir(parents=True, exist_ok=True)
                destination.write_bytes(content)
    print(f'{count} Japscan patches ' + ('checked.' if check else 'applied.'))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--check', action='store_true')
    apply(check=parser.parse_args().check)
