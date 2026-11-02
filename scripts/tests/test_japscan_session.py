import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import textwrap
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import apply_patches as patches


class JapscanSessionTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix='tachivf-japscan-test-')
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.module = 'src/fr/japscan'
        for path in patches.git(patches.ROOT, 'ls-tree', '-r', '--name-only', 'HEAD', self.module).decode().splitlines():
            destination = self.root / path
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(patches.git(patches.ROOT, 'show', 'HEAD:' + path))
        shutil.copytree(patches.ROOT / 'patches/japscan', self.root / 'patches/japscan')
        self.git('init', '-b', 'main')
        self.git('config', 'user.name', 'Fixture')
        self.git('config', 'user.email', 'fixture@example.org')
        self.git('config', 'core.autocrlf', 'false')
        self.commit()

    def git(self, *args):
        return patches.git(self.root, *args)

    def commit(self):
        self.git('add', '-A')
        self.git('commit', '-m', 'Fixture update')

    def test_reader_waits_for_pages_and_reports_site_captcha_first(self):
        patches.apply(self.root)
        state = next((self.root / self.module).rglob('ReaderState.kt')).read_text(encoding='utf-8')
        script = textwrap.dedent(re.search(r'READER_STATE_SCRIPT = """(.*?)"""', state, re.S).group(1))
        cases = [
            {'needed': True, 'pages': 20, 'webtoon': False, 'expected': 'captcha'},
            {'needed': False, 'pages': 20, 'webtoon': False, 'expected': 'ready'},
            {'needed': False, 'pages': 0, 'webtoon': True, 'expected': 'ready'},
            {'needed': False, 'pages': 0, 'webtoon': False, 'expected': 'loading'},
            {'needed': None, 'pages': 0, 'webtoon': False, 'expected': 'loading'},
        ]
        runner = '''
            const vm = require('node:vm');
            const input = JSON.parse(require('node:fs').readFileSync(0, 'utf8'));
            for (const item of input.cases) {
                const context = {
                    window: {__captcha: item.needed === null ? undefined : {needed: item.needed}},
                    document: {
                        getElementById: () => ({options: {length: item.pages}}),
                        querySelector: () => item.webtoon ? {} : null,
                    },
                    fetch: () => {throw new Error('Captcha detection must not make HTTP requests');},
                };
                const actual = vm.runInNewContext(input.script, context, {timeout: 1000});
                if (actual !== item.expected) throw new Error(JSON.stringify({item, actual}));
            }
        '''
        subprocess.run(['node', '-e', runner], input=json.dumps({'script': script, 'cases': cases}),
                       text=True, check=True, capture_output=True)

    def test_actual_patch_applies_after_an_upstream_version_bump(self):
        metadata = self.root / self.module / 'build.gradle.kts'
        content = metadata.read_text()
        content = re.sub(r'versionCode = (\d+)', lambda m: f'versionCode = {int(m[1]) + 1}', content)
        metadata.write_text(content, newline='\n')
        self.commit()
        plan, count = patches.prepare(self.root)
        self.assertGreater(count, 0)
        self.assertIn(self.module + '/build.gradle.kts', plan)
        self.assertEqual(metadata.read_text(), content)
