from contextlib import redirect_stdout
import hashlib
from io import StringIO
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import signing


class SigningTests(unittest.TestCase):
    def test_missing_secret_disables_publication(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / 'output'
            with patch.dict(os.environ, {'SIGNING_BUNDLE': '', 'GITHUB_OUTPUT': str(output)}), redirect_stdout(StringIO()):
                signing.restore()
            self.assertEqual(output.read_text(), 'ready=false\n')

    def test_wrong_key_cannot_enable_publication(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'scripts').mkdir()
            (root / 'scripts/signing-key.sha256').write_text(hashlib.sha256(b'expected').hexdigest())
            output, environment = root / 'output', root / 'environment'
            bundle = {'keystore': 'Zml4dHVyZQ==', 'storePassword': 'fixture', 'keyPassword': 'fixture', 'alias': 'fixture'}
            env = {'SIGNING_BUNDLE': json.dumps(bundle), 'GITHUB_OUTPUT': str(output), 'GITHUB_ENV': str(environment)}
            with patch.object(signing, 'ROOT', root), patch.object(signing, 'certificate', return_value=b'wrong'), patch.dict(os.environ, env), redirect_stdout(StringIO()):
                with self.assertRaisesRegex(ValueError, 'does not match'):
                    signing.restore()
            self.assertFalse(output.exists())
            self.assertFalse(environment.exists())
