import gzip
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import build_repo
import index_pb2


class CatalogueTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.artifacts = Path(self.temporary.name) / 'artifacts'
        self.output = Path(self.temporary.name) / 'repo'
        self.fingerprint = 'a' * 64
        identities = json.loads((build_repo.ROOT / 'docs/upstream/source-identities.json').read_text())
        for identity in identities:
            module = identity['packageName'].removeprefix('eu.kanade.tachiyomi.extension.')
            build = self.artifacts / module / 'build'
            build.mkdir(parents=True)
            info = {'module': module, 'name': identity['name'], 'packageName': identity['packageName'], 'extensionLib': '1.6', 'versionCode': 106001, 'versionName': '1.6.1', 'contentWarning': 1, 'sources': [{'id': int(identity['sourceId']), 'name': identity['name'], 'lang': 'fr', 'baseUrl': 'https://example.org'}]}
            (build / 'keiyoushi-source-info.json').write_text(json.dumps(info))
            for kind in ('apk', 'jar'):
                folder = build / 'outputs' / kind / 'release'
                folder.mkdir(parents=True)
                (folder / f'{module}.{kind}').write_bytes(b'fixture')

    def generate(self):
        return build_repo.generate(self.artifacts, self.output, 'SyyeeIsNotAvailable/TachiVF', self.fingerprint)

    @patch('build_repo.signer_fingerprint', return_value='a' * 64)
    def test_modern_and_legacy_catalogues_preserve_identities(self, signer):
        self.generate()
        modern = index_pb2.Index.FromString(gzip.decompress((self.output / 'index.pb').read_bytes()))
        legacy = json.loads((self.output / 'index.min.json').read_text())
        self.assertEqual(len(modern.extensionList.extensions), 4)
        self.assertEqual({str(s.id) for e in modern.extensionList.extensions for s in e.sources}, {s['id'] for e in legacy for s in e['sources']})
        self.assertEqual(modern.signingKey, self.fingerprint)
        for extension in modern.extensionList.extensions:
            for url in (extension.resources.apkUrl, extension.resources.jarUrl, extension.resources.iconUrl):
                self.assertTrue((self.output / url.split('/repo/', 1)[1]).is_file())

    @patch('build_repo.signer_fingerprint', return_value='b' * 64)
    def test_wrong_signature_prevents_publication(self, signer):
        with self.assertRaisesRegex(ValueError, 'unexpected signing key'):
            self.generate()
        self.assertFalse(self.output.exists())

    def test_missing_extension_prevents_partial_catalogue(self):
        next(self.artifacts.rglob('keiyoushi-source-info.json')).unlink()
        with self.assertRaisesRegex(ValueError, 'exactly the four'):
            self.generate()

    @patch('build_repo.signer_fingerprint', return_value='a' * 64)
    def test_identity_change_is_rejected(self, signer):
        path = next(self.artifacts.rglob('keiyoushi-source-info.json'))
        info = json.loads(path.read_text())
        info['sources'][0]['id'] = 123
        path.write_text(json.dumps(info))
        with self.assertRaisesRegex(ValueError, 'source identity changed'):
            self.generate()
