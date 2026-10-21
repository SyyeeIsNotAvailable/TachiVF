import json
from pathlib import Path
import subprocess
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import sync_upstream as sync


class SyncTests(unittest.TestCase):
    def setUp(self):
        temporary = sync.temporary()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name) / 'local'
        self.upstream = Path(temporary.name) / 'upstream'
        self.root.mkdir()
        self.upstream.mkdir()
        self.run_git('init', '-b', 'main')
        self.run_git('config', 'user.name', 'Fixture')
        self.run_git('config', 'user.email', 'fixture@example.org')
        self.original = {}
        for module in sync.MODULES:
            for suffix, content in [('build.gradle.kts', b'fixture\n'), ('src/Source.kt', ''.join(f'line {i}\n' for i in range(20)).encode())]:
                path = f'src/fr/{module}/{suffix}'
                self.write(self.upstream, path, content)
                self.write(self.root, path, content)
                self.original[path] = content
        self.commit()
        files = {path: {'sha': sync.blob(data), 'mode': '100644'} for path, data in self.original.items()}
        self.baseline = {'repository': sync.REPOSITORY, 'revision': self.run_git('rev-parse', 'HEAD').strip(), 'files': files}
        self.path = 'src/fr/animesama/src/Source.kt'

    def run_git(self, *arguments):
        return subprocess.check_output(['git', '-C', str(self.upstream), *arguments], stderr=subprocess.DEVNULL).decode()

    def commit(self):
        self.run_git('add', '-A')
        self.run_git('commit', '-m', 'Fixture update')

    def write(self, root, path, data):
        target = root / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)

    def plan(self):
        return sync.synchronize(self.root, self.upstream, self.baseline, self.original.__getitem__)

    def test_upstream_source_and_shared_dependency_are_selected(self):
        self.write(self.upstream, self.path, b'upstream update\n')
        self.write(self.upstream, 'core/src/NewHelper.kt', b'new helper\n')
        self.write(self.upstream, 'README.md', b'upstream readme\n')
        self.write(self.upstream, '.github/workflows/foreign.yml', b'not ours\n')
        self.commit()
        changes, state = self.plan()
        self.assertEqual(changes[self.path], b'upstream update\n')
        self.assertIn('core/src/NewHelper.kt', changes)
        self.assertNotIn('README.md', changes)
        self.assertNotIn('.github/workflows/foreign.yml', changes)
        self.assertEqual(state['revision'], self.run_git('rev-parse', 'HEAD').strip())

    def test_independent_local_changes_survive(self):
        self.write(self.root, self.path, self.original[self.path].replace(b'line 0\n', b'local correction\n'))
        self.write(self.upstream, self.path, self.original[self.path].replace(b'line 19\n', b'upstream correction\n'))
        self.commit()
        changes, _ = self.plan()
        self.assertIn(b'local correction', changes[self.path])
        self.assertIn(b'upstream correction', changes[self.path])

    def test_conflict_does_not_modify_any_local_file(self):
        local = b'local correction\n'
        self.write(self.root, self.path, local)
        self.write(self.upstream, self.path, b'conflicting upstream correction\n')
        self.commit()
        with self.assertRaises(sync.SyncConflict):
            self.plan()
        self.assertEqual((self.root / self.path).read_bytes(), local)

    def test_deletion_does_not_erase_a_local_fix(self):
        self.write(self.root, self.path, b'local correction\n')
        (self.upstream / self.path).unlink()
        self.commit()
        with self.assertRaisesRegex(sync.SyncConflict, 'erase local changes'):
            self.plan()

    def test_required_extension_cannot_disappear(self):
        (self.upstream / 'src/fr/aniverse/build.gradle.kts').unlink()
        self.commit()
        with self.assertRaisesRegex(sync.SyncConflict, 'removed or moved'):
            self.plan()

    def test_gradle_upgrade_keeps_mirror_and_updates_checksum(self):
        base = b'distributionUrl=https\\://services.gradle.org/distributions/gradle-9.8.1-bin.zip\nnetworkTimeout=10000\n'
        local = base.replace(b'services.gradle.org', b'downloads.gradle.org') + b'distributionSha256Sum=' + b'a' * 64 + b'\n'
        remote = base.replace(b'9.8.1', b'9.9')
        merged = sync.merge_wrapper(base, local, remote, download=lambda url: b'b' * 64)
        self.assertIn(b'downloads.gradle.org/distributions/gradle-9.9-bin.zip', merged)
        self.assertIn(b'distributionSha256Sum=' + b'b' * 64, merged)
