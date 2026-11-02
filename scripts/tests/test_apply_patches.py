import difflib
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import apply_patches as patches


class PatchTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix='tachivf-patch-test-')
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.directory = self.root / 'patches/japscan'
        self.directory.mkdir(parents=True)
        self.series = self.directory / 'series'
        self.series.write_text('# Local patches\n')
        self.path = 'src/fr/japscan/src/Source.kt'
        self.original = ''.join(f'line {i}\n' for i in range(30))
        self.source = self.root / self.path
        self.source.parent.mkdir(parents=True)
        self.source.write_text(self.original, newline='\n')
        self.git('init', '-b', 'main')
        self.git('config', 'user.name', 'Fixture')
        self.git('config', 'user.email', 'fixture@example.org')
        self.commit()

    def git(self, *args):
        return subprocess.check_output(['git', '-C', str(self.root), *args], stderr=subprocess.DEVNULL)

    def commit(self):
        self.git('add', '-A')
        self.git('commit', '-m', 'Fixture update')

    def patch(self, name, path, before, after):
        diff = ''.join(difflib.unified_diff(before.splitlines(True), after.splitlines(True),
                                          fromfile='a/' + path, tofile='b/' + path))
        (self.directory / name).write_text(diff, newline='\n')
        with self.series.open('a') as series:
            series.write(name + '\n')

    def test_patch_survives_upstream_update_and_repeated_build(self):
        self.patch('reader.patch', self.path, self.original, self.original.replace('line 0\n', 'local fix\n'))
        updated = self.original.replace('line 29\n', 'upstream fix\n')
        self.source.write_text(updated, newline='\n')
        self.commit()
        patches.apply(self.root)
        expected = updated.replace('line 0\n', 'local fix\n')
        self.assertEqual(self.source.read_text(), expected)
        patches.apply(self.root)
        self.assertEqual(self.source.read_text(), expected)

    def test_incompatible_second_patch_leaves_source_unchanged(self):
        self.patch('first.patch', self.path, self.original, self.original.replace('line 0\n', 'first fix\n'))
        self.patch('second.patch', self.path, self.original, self.original.replace('line 0\n', 'conflicting fix\n'))
        with self.assertRaisesRegex(patches.PatchConflict, 'incompatible with upstream'):
            patches.apply(self.root)
        self.assertEqual(self.source.read_text(), self.original)

    def test_check_does_not_modify_files(self):
        self.patch('reader.patch', self.path, self.original, self.original.replace('line 0\n', 'local fix\n'))
        patches.apply(self.root, check=True)
        self.assertEqual(self.source.read_text(), self.original)

    def test_uncommitted_edits_are_preserved(self):
        self.patch('reader.patch', self.path, self.original, self.original.replace('line 0\n', 'local fix\n'))
        self.source.write_text('work in progress\n')
        with self.assertRaisesRegex(patches.PatchConflict, 'uncommitted edits'):
            patches.apply(self.root)
        self.assertEqual(self.source.read_text(), 'work in progress\n')

    def test_patch_cannot_modify_another_extension(self):
        self.patch('foreign.patch', 'src/fr/aniverse/src/Source.kt', 'old\n', 'new\n')
        with self.assertRaisesRegex(patches.PatchConflict, 'must only change'):
            patches.apply(self.root)

    def test_empty_series_keeps_upstream_unchanged(self):
        self.assertEqual(patches.prepare(self.root), ({}, 0))
