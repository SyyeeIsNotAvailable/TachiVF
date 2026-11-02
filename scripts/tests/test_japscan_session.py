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

    def run_batch(self, start, count, total=68, no_blob=False, fail_page=None):
        patches.apply(self.root)
        source = next((self.root / self.module).rglob('PaginatedReader.kt')).read_text(encoding='utf-8')
        script = textwrap.dedent(re.search(r'= \$\$"""(.*?)"""', source, re.S).group(1))
        script = script.replace('$${interfaceName}', 'probe').replace('$$startPage', str(start)).replace('$$pageCount', str(count))
        fixture = {'total': total, 'noBlob': no_blob, 'failPage': fail_page}
        runner = r'''
            const vm = require('node:vm');
            const input = JSON.parse(require('node:fs').readFileSync(0, 'utf8'));
            const fixture = input.fixture;
            let clock = 0;
            const output = {pages: [], navigations: [], done: false, error: null};
            let rendered = 0;
            const window = {__japscanLastBlob: fixture.noBlob ? null : 'blob:' + (fixture.total - 1)};
            const selected = {
                value: '0', options: {length: fixture.total},
                dispatchEvent() {
                    const index = Number(this.value);
                    if (index < 0 || index >= fixture.total) throw new Error('Invalid page navigation');
                    output.navigations.push(index);
                    if (index !== rendered && !fixture.noBlob) window.__japscanLastBlob = 'blob:' + index;
                    rendered = index;
                },
            };
            window.probe_savePage = {post(data) {output.pages.push(Number(data.split(',')[1]));}};
            window.probe_passDone = {post() {output.done = true;}};
            window.probe_captureError = {post(message) {output.error = message;}};
            class FileReader {
                readAsDataURL(blob) {this.result = 'data:image/mock,' + blob.page; this.onload();}
            }
            const context = {
                window, document: {getElementById: () => selected},
                Event: class Event {}, FileReader, URL: {revokeObjectURL() {}},
                setTimeout(callback, delay) {clock += delay; Promise.resolve().then(callback);},
                async fetch(url) {
                    const page = Number(url.split(':')[1]);
                    if (page === fixture.failPage) throw new Error('Image request failed');
                    return {async blob() {return {page};}};
                },
            };
            Promise.resolve(vm.runInNewContext(input.script, context, {timeout: 1000}))
                .then(() => {output.clock = clock; console.log(JSON.stringify(output));})
                .catch(error => {console.error(error); process.exitCode = 1;});
        '''
        result = subprocess.run(['node', '-e', runner], input=json.dumps({'script': script, 'fixture': fixture}),
                                text=True, encoding='utf-8', check=True, capture_output=True)
        return json.loads(result.stdout)

    def test_batch_captures_only_requested_pages_in_order(self):
        for start, count, total in [(0, 4, 68), (16, 4, 68), (64, 4, 68), (0, 1, 1)]:
            with self.subTest(start=start, total=total):
                result = self.run_batch(start, count, total)
                self.assertEqual(result['pages'], list(range(start, start + count)))
                self.assertTrue(result['done'])
                self.assertIsNone(result['error'])

    def test_batch_fails_fast_when_no_image_is_produced(self):
        result = self.run_batch(0, 4, no_blob=True)
        self.assertEqual(result['pages'], [])
        self.assertFalse(result['done'])
        self.assertIn('page 1', result['error'])
        self.assertLessEqual(result['clock'], 10000)

    def test_missing_image_cannot_shift_later_page_numbers(self):
        result = self.run_batch(0, 4, fail_page=2)
        self.assertEqual(result['pages'], [0, 1])
        self.assertFalse(result['done'])
        self.assertIn('page 3', result['error'])

    def test_changed_page_count_stops_capture(self):
        result = self.run_batch(0, 4, total=3)
        self.assertEqual(result['pages'], [])
        self.assertFalse(result['done'])
        self.assertIn('actualisez', result['error'])
