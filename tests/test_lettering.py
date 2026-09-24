"""Run with the installed geometry Python. No GUI or printer required."""
import tempfile
import unittest
from pathlib import Path
import trimesh
from vt.lettering import engrave

class LetteringTests(unittest.TestCase):
    def test_missing_second_line_blocks(self):
        with tempfile.TemporaryDirectory() as d:
            d=Path(d);m=trimesh.creation.box([30,30,10]);m.export(d/'body.stl')
            a={'font':__import__('matplotlib.font_manager',fromlist=['findfont']).findfont('DejaVu Sans'),'text':'A','em_mm':8,'extrude_mm':4,'transform':[[1,0,0,-5],[0,1,0,0],[0,0,1,3]]}
            b={**a,'text':'B','transform':[[1,0,0,100],[0,1,0,0],[0,0,1,3]]}
            with self.assertRaisesRegex(ValueError,'line did not intersect'):
                engrave(d/'body.stl',d/'bad.stl',{'lines':[a,b]})
            self.assertFalse((d/'bad.stl').exists())
    def test_real_glyph_removes_material_and_closes(self):
        with tempfile.TemporaryDirectory() as d:
            d=Path(d);trimesh.creation.box([30,30,10]).export(d/'body.stl')
            a={'font':__import__('matplotlib.font_manager',fromlist=['findfont']).findfont('DejaVu Sans'),'text':'A','em_mm':8,'extrude_mm':4,'transform':[[1,0,0,-5],[0,1,0,0],[0,0,1,3]]}
            result=engrave(d/'body.stl',d/'good.stl',{'lines':[a]})
            self.assertGreater(result['lines'][0]['removed_volume_mm3'],0)
            self.assertTrue(trimesh.load(d/'good.stl',force='mesh').is_watertight)

if __name__=='__main__':unittest.main()
