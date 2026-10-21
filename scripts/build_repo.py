"""Generate the installable branch from signed extension build outputs."""
import argparse
import gzip
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tomllib

from google.protobuf import json_format
import index_pb2


ROOT = Path(__file__).resolve().parents[1]
MODULES = {'fr.animesama', 'fr.aniverse', 'fr.mangakawaii', 'fr.mangascantrad'}


def signer_fingerprint(path):
    version = tomllib.loads((ROOT / 'gradle/libs.versions.toml').read_text())['versions']['android-gradle']
    gradle_home = Path(os.environ.get('GRADLE_USER_HOME', Path.home() / '.gradle'))
    jars = list((gradle_home / 'caches/modules-2/files-2.1/com.android.tools.build/apksig' / version).glob('*/*.jar'))
    if len(jars) != 1:
        raise FileNotFoundError('Build the project first to obtain its APK signature verifier')
    return subprocess.check_output(['java', '--class-path', str(jars[0]), str(ROOT / 'scripts/VerifySignature.java'), str(path)]).decode().strip()


def generate(artifacts, output, repository, fingerprint, source=ROOT):
    if not re.fullmatch(r'[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+', repository):
        raise ValueError('Invalid GitHub repository')
    if not re.fullmatch(r'[a-f0-9]{64}', fingerprint):
        raise ValueError('Invalid signing fingerprint')
    files = sorted(artifacts.rglob('keiyoushi-source-info.json'))
    records = [json.loads(path.read_text(encoding='utf-8')) for path in files]
    if len(records) != len(MODULES) or {r['module'] for r in records} != MODULES:
        raise ValueError('The catalogue must contain exactly the four selected extensions')
    identities = json.loads((source / 'docs/upstream/source-identities.json').read_text(encoding='utf-8'))
    expected = {v['packageName']: v['sourceId'] for v in identities}
    prepared = []
    for path, info in zip(files, records):
        package = info['packageName']
        if len(info['sources']) != 1 or info['sources'][0]['lang'] != 'fr':
            raise ValueError(f'{package}: expected one French source')
        if str(info['sources'][0]['id']) != str(expected[package]):
            raise ValueError(f'{package}: source identity changed')
        assets = {}
        for kind in ('apk', 'jar'):
            candidates = list((path.parent / 'outputs' / kind / 'release').glob('*.' + kind))
            if len(candidates) != 1:
                raise ValueError(f'{package}: expected one {kind.upper()}')
            artifact = candidates[0]
            if signer_fingerprint(artifact) != fingerprint:
                raise ValueError(f'{artifact.name}: unexpected signing key')
            assets[kind] = artifact
        icon = source / 'src' / info['module'].replace('.', '/') / 'res/mipmap-xhdpi/ic_launcher.png'
        if not icon.is_file():
            raise FileNotFoundError(icon)
        prepared.append((info, assets, icon))
    if output.exists() and any(output.iterdir()):
        raise FileExistsError('The output directory must be empty')
    output.mkdir(parents=True, exist_ok=True)
    for directory in ('apk', 'jar', 'icon'):
        (output / directory).mkdir()
    base = f'https://raw.githubusercontent.com/{repository}/repo'
    website = f'https://github.com/{repository}'
    index = index_pb2.Index(name='TachiVF', badgeLabel='VF', signingKey=fingerprint, contact=index_pb2.Contact(website=website))
    legacy = []
    checksums = {}
    for info, assets, icon in sorted(prepared, key=lambda item: item[0]['packageName']):
        package = info['packageName']
        for kind, artifact in assets.items():
            relative = f'{kind}/{artifact.name}'
            shutil.copyfile(artifact, output / relative)
            checksums[relative] = hashlib.sha256(artifact.read_bytes()).hexdigest()
        icon_name = package + '.png'
        shutil.copyfile(icon, output / 'icon' / icon_name)
        sources = info['sources']
        index.extensionList.extensions.add(
            name=info['name'], packageName=package,
            resources=index_pb2.Resources(apkUrl=f"{base}/apk/{assets['apk'].name}", jarUrl=f"{base}/jar/{assets['jar'].name}", iconUrl=f'{base}/icon/{icon_name}'),
            extensionLib=info['extensionLib'], versionCode=info['versionCode'], versionName=info['versionName'], contentWarning=info['contentWarning'],
            sources=[index_pb2.Source(id=int(s['id']), name=s['name'], language=s['lang'], homeUrl=s['baseUrl'], mirrorUrls=s.get('mirrorUrls', [])) for s in sources],
        )
        legacy.append({
            'name': 'Tachiyomi: ' + info['name'], 'pkg': package, 'apk': assets['apk'].name, 'lang': 'fr',
            'code': info['versionCode'], 'version': info['versionName'], 'nsfw': int(info['contentWarning'] == 3),
            'sources': [{'name': s['name'], 'lang': s['lang'], 'id': str(s['id']), 'baseUrl': s['baseUrl'], 'versionId': 1} for s in sources],
        })
    (output / 'index.pb').write_bytes(gzip.compress(index.SerializeToString(deterministic=True), mtime=0))
    (output / 'index.json').write_text(json_format.MessageToJson(index, preserving_proto_field_name=True) + '\n', encoding='utf-8')
    (output / 'index.min.json').write_text(json.dumps(legacy, ensure_ascii=False, separators=(',', ':')) + '\n', encoding='utf-8')
    descriptor = {'index_v2': f'{base}/index.pb', 'meta': {'name': 'TachiVF', 'website': website, 'signingKeyFingerprint': fingerprint}}
    (output / 'repo.json').write_text(json.dumps(descriptor, indent=2) + '\n', encoding='utf-8')
    (output / 'checksums.json').write_text(json.dumps(checksums, indent=2, sort_keys=True) + '\n', encoding='utf-8')
    (output / 'README.md').write_text(f'# TachiVF\n\nExtensions françaises pour Mihon et Tachimanga.\n\nDépôt : {base}/repo.json\n\nAncien format : {base}/index.min.json\n\nCode source : {website}/tree/main\n', encoding='utf-8')
    shutil.copyfile(source / 'LICENSE', output / 'LICENSE')
    shutil.copyfile(source / 'NOTICE', output / 'NOTICE')
    return index


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--artifacts', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--repository', default='SyyeeIsNotAvailable/TachiVF')
    args = parser.parse_args()
    fingerprint = (ROOT / 'scripts/signing-key.sha256').read_text().strip()
    index = generate(args.artifacts, args.output, args.repository, fingerprint)
    print(f'Catalogue generated: {len(index.extensionList.extensions)} extensions')
