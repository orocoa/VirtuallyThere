import importlib.util
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from vt import config

ROOT = Path(__file__).resolve().parents[1]


def script(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / 'scripts' / (name + '.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class ReleaseTests(unittest.TestCase):
    def test_package_ignores_unlisted_notes_and_requires_all_sources(self):
        package = script('package_release')
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            for name in package.SOURCE_FILES:
                path = root / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text('fixture')
            (root / 'examples/private-story.txt').write_text('not for release')
            self.assertEqual({str(rel) for _, rel in package.sources(root)}, set(package.SOURCE_FILES))
            (root / 'vt/solid_geometry.py').unlink()
            with self.assertRaisesRegex(ValueError, 'Missing release source'):
                list(package.sources(root))

    def test_skill_upgrade_removes_obsolete_active_files_but_keeps_backup(self):
        installer = script('install_skill')
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / 'source'
            (root / 'skill/references').mkdir(parents=True)
            (root / 'skill/SKILL.md').write_text('new')
            skills = Path(temp) / 'skills'
            old = skills / 'virtually-there'
            old.mkdir(parents=True)
            (old / 'obsolete.md').write_text('old instructions')
            result = installer.install(root, skills, 'test-python')
            self.assertFalse((old / 'obsolete.md').exists())
            self.assertEqual((Path(result['backup']) / 'obsolete.md').read_text(), 'old instructions')
            self.assertEqual(json.loads((old / 'references/runtime.json').read_text())['python'], 'test-python')
            real_replace = os.replace

            def fail_new(source, target):
                if Path(source).name == 'new':
                    raise OSError('test installation failure')
                return real_replace(source, target)

            (root / 'skill/SKILL.md').write_text('next')
            with patch.object(installer.os, 'replace', side_effect=fail_new):
                with self.assertRaises(OSError):
                    installer.install(root, skills, 'test-python')
            self.assertEqual((old / 'SKILL.md').read_text(), 'new')

    def test_local_mcp_runtime_wins_over_global_path(self):
        with tempfile.TemporaryDirectory() as temp:
            local = Path(temp) / 'mcp-for-blender'
            local.write_text('local pinned runtime')
            with patch.object(config.sys, 'executable', str(Path(temp) / 'python')), \
                    patch.object(config.shutil, 'which', return_value='/unrelated/global-mcp'), \
                    patch.dict(os.environ, {}, clear=True):
                self.assertEqual(config.settings()['mcp_server'], str(local))


if __name__ == '__main__':
    unittest.main()
