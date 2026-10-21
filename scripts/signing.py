"""Create a local signing backup or restore the GitHub Actions signing secret."""
import argparse
import base64
import hashlib
import json
import os
from pathlib import Path
import secrets
import subprocess


ROOT = Path(__file__).resolve().parents[1]


def keytool():
    home = os.environ.get('JAVA_HOME')
    return str(Path(home) / 'bin' / ('keytool.exe' if os.name == 'nt' else 'keytool')) if home else 'keytool'


def certificate(keystore, password, alias):
    env = dict(os.environ, KEY_STORE_PASSWORD=password)
    return subprocess.check_output([
        keytool(), '-exportcert', '-keystore', str(keystore),
        '-storepass:env', 'KEY_STORE_PASSWORD', '-alias', alias,
    ], env=env, stderr=subprocess.DEVNULL)


def restore():
    value = os.environ.get('SIGNING_BUNDLE', '')
    output = Path(os.environ['GITHUB_OUTPUT'])
    if not value:
        with output.open('a') as stream:
            stream.write('ready=false\n')
        print('Signing secret absent; build only, no publication.')
        return
    bundle = json.loads(value)
    for key in ('storePassword', 'keyPassword'):
        print('::add-mask::' + bundle[key])
    keystore = ROOT / 'signingkey.jks'
    keystore.write_bytes(base64.b64decode(bundle['keystore'], validate=True))
    keystore.chmod(0o600)
    fingerprint = hashlib.sha256(certificate(keystore, bundle['storePassword'], bundle['alias'])).hexdigest()
    expected = (ROOT / 'scripts/signing-key.sha256').read_text().strip()
    if fingerprint != expected:
        raise ValueError('Signing secret does not match the public repository fingerprint')
    with Path(os.environ['GITHUB_ENV']).open('a') as stream:
        for name, key in [('KEY_STORE_PASSWORD', 'storePassword'), ('KEY_PASSWORD', 'keyPassword'), ('ALIAS', 'alias')]:
            value = bundle[key]
            if '\n' in value or '\r' in value:
                raise ValueError('Invalid signing field')
            stream.write(f'{name}={value}\n')
    with output.open('a') as stream:
        stream.write('ready=true\n')


def initialize(directory):
    if directory.resolve().is_relative_to(ROOT):
        raise ValueError('Keep the signing backup outside the repository')
    directory.mkdir(parents=True, exist_ok=True)
    directory.chmod(0o700)
    target = directory / 'signing-secret.json'
    keystore = directory / 'signingkey.jks'
    if target.exists():
        bundle = json.loads(target.read_text())
    else:
        if keystore.exists():
            raise FileExistsError('An existing keystore requires its original backup')
        password = secrets.token_hex(24)
        env = dict(os.environ, KEY_STORE_PASSWORD=password)
        subprocess.run([
            keytool(), '-genkeypair', '-noprompt', '-storetype', 'PKCS12',
            '-keystore', str(keystore), '-alias', 'tachivf', '-keyalg', 'RSA',
            '-keysize', '3072', '-validity', '36500', '-dname', 'CN=TachiVF',
            '-storepass:env', 'KEY_STORE_PASSWORD', '-keypass:env', 'KEY_STORE_PASSWORD',
        ], env=env, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
        bundle = {'keystore': base64.b64encode(keystore.read_bytes()).decode(), 'storePassword': password, 'keyPassword': password, 'alias': 'tachivf'}
        target.write_text(json.dumps(bundle), encoding='utf-8')
        target.chmod(0o600)
    fingerprint = hashlib.sha256(certificate(keystore, bundle['storePassword'], bundle['alias'])).hexdigest()
    public_file = ROOT / 'scripts/signing-key.sha256'
    if public_file.exists() and public_file.read_text().strip() != fingerprint:
        raise ValueError('Refusing to replace the existing repository signing identity')
    public_file.write_text(fingerprint + '\n', encoding='utf-8')
    print('Signing backup saved locally. Public fingerprint: ' + fingerprint)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('command', choices=['init', 'restore'])
    parser.add_argument('--directory', type=Path)
    args = parser.parse_args()
    if args.command == 'init':
        if args.directory is None:
            parser.error('--directory is required for init')
        initialize(args.directory)
    else:
        restore()
