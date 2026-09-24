"""Constructive geometry regressions; run with the external geometry Python."""
import json
import math
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

import numpy as np
import trimesh

from vt.solid_geometry import arc_band, build, export_stl, profile_extrude, subtract


SQUARE = [[0, 0], [20, 0], [20, 20], [0, 20]]
HOLE = [[5, 5], [15, 5], [15, 15], [5, 15]]


class SolidGeometryTests(unittest.TestCase):
    def test_arc_ramp_is_closed_and_preserves_opening(self):
        solid = arc_band(20, 32, 18, start_degrees=-30, end_height_mm=42)
        ideal = math.radians(240) * (32**2 - 20**2) / 2 * 30
        self.assertAlmostEqual(solid.volume() / ideal, 1, delta=.002)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'arc.stl'
            receipt = export_stl(solid, path)
            mesh = trimesh.load(path, force='mesh')
            self.assertTrue(mesh.is_watertight)
            self.assertTrue(mesh.is_winding_consistent)
            self.assertEqual(len(mesh.split()), 1)
            np.testing.assert_allclose(mesh.bounds[:, 2], [0, 42], atol=1e-5)
            self.assertLessEqual(receipt['triangles'], 650)
            # The complete negative-Y sector is an intentional opening, not
            # a cap bridging the two tips or a base closing the interior.
            cutter = profile_extrude([[-5, -35], [5, -35], [5, -20], [-5, -20]], 50)
            self.assertTrue((solid ^ cutter).is_empty())
            centre = profile_extrude([[-5, -5], [5, -5], [5, 5], [-5, 5]], 50)
            self.assertTrue((solid ^ centre).is_empty())
            vertices = np.asarray(solid.to_mesh().vert_properties)
            for angle, height in [(-30, 18), (210, 42)]:
                tip = [32*math.cos(math.radians(angle)), 32*math.sin(math.radians(angle)), height]
                self.assertLess(np.min(np.linalg.norm(vertices[:, :3] - tip, axis=1)), 1e-4)

    def test_profile_hole_survives_export_with_either_winding(self):
        for hole in [HOLE, list(reversed(HOLE))]:
            solid = profile_extrude(SQUARE, 10, [hole])
            self.assertAlmostEqual(solid.volume(), 3000, places=4)
            self.assertEqual(solid.genus(), 1)
            plug = profile_extrude([[6, 6], [14, 6], [14, 14], [6, 14]], 10)
            self.assertTrue((solid ^ plug).is_empty())
            with tempfile.TemporaryDirectory() as directory:
                path = Path(directory) / 'ring.stl'
                export_stl(solid, path)
                mesh = trimesh.load(path, force='mesh')
                self.assertTrue(mesh.is_watertight)
                self.assertEqual(mesh.euler_number, 0)
                self.assertAlmostEqual(mesh.volume, 3000, places=4)

    def test_through_cut_volume_and_noop_rejection(self):
        body = profile_extrude(SQUARE, 10)
        cutter = profile_extrude(HOLE, 12).translate([0, 0, -1])
        result = subtract(body, [cutter])
        self.assertAlmostEqual(result.volume(), 3000, places=4)
        self.assertEqual(result.genus(), 1)
        with self.assertRaisesRegex(ValueError, 'did not remove'):
            subtract(body, [cutter.translate([100, 0, 0])])
        with self.assertRaisesRegex(ValueError, 'empty or invalid'):
            subtract(body, [body])

    def test_disconnected_cut_blocks_export_and_existing_files_survive(self):
        body = profile_extrude(SQUARE, 10)
        cutter = profile_extrude([[9, -1], [11, -1], [11, 21], [9, 21]], 12).translate([0, 0, -1])
        divided = subtract(body, [cutter])
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'body.stl'
            with self.assertRaisesRegex(ValueError, 'one connected'):
                export_stl(divided, path)
            self.assertFalse(path.exists())
            path.write_bytes(b'original')
            with self.assertRaises(FileExistsError):
                export_stl(body, path)
            self.assertEqual(path.read_bytes(), b'original')

    def test_bad_dimensions_and_profiles_fail(self):
        for value in [True, float('nan'), float('inf'), 10**1000, -1, 0, '10']:
            with self.subTest(value=value), self.assertRaises(ValueError):
                arc_band(20, 32, value)
        for params in [{'outer_radius_mm': 10}, {'segments': True}, {'segments': 2},
                       {'sweep_degrees': 360}, {'end_height_mm': float('nan')}]:
            arguments = dict(inner_radius_mm=20, outer_radius_mm=32, height_mm=10)
            arguments.update(params)
            with self.subTest(params=params), self.assertRaises(ValueError):
                arc_band(**arguments)
        for outline, holes in [([[0, 0], [20, 20], [0, 20], [20, 0]], []),
                               (SQUARE, [[[30, 0], [40, 0], [40, 10], [30, 10]]]),
                               (SQUARE, [HOLE, HOLE]),
                               (SQUARE, [[[0, 10], [5, 5], [5, 15]]]),
                               ([[0, 0], [20, 0], [True, 20]], [])]:
            with self.subTest(outline=outline, holes=holes), self.assertRaises(ValueError):
                profile_extrude(outline, 10, holes)

    def test_cli_builds_translated_cut_and_reports_mm(self):
        spec = {'operation': 'profile_extrude', 'parameters': {'outline': SQUARE, 'height_mm': 10},
                'cuts': [{'operation': 'profile_extrude', 'parameters': {'outline': HOLE, 'height_mm': 12},
                          'translation_mm': [0, 0, -1]}]}
        with tempfile.TemporaryDirectory() as directory:
            source, target = Path(directory) / 'shape.json', Path(directory) / 'shape.stl'
            source.write_text(json.dumps(spec))
            result = subprocess.run([sys.executable, '-m', 'vt.solid_geometry', str(source), str(target)],
                                    capture_output=True, text=True, timeout=30)
            self.assertEqual(result.returncode, 0, result.stderr)
            receipt = json.loads(result.stdout)
            self.assertEqual(receipt['units'], 'mm')
            self.assertAlmostEqual(receipt['volume_mm3'], 3000, places=4)
            self.assertTrue(target.is_file())
        for invalid in [{'operation': 'unknown', 'parameters': {}},
                        {**spec, 'cuts': 'bad'}, {**spec, 'unused': True}]:
            with self.assertRaises(ValueError):
                build(invalid)


if __name__ == '__main__':
    unittest.main()
