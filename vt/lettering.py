"""Reusable font-outline boolean worker. Called from a Blender MCP script."""
import json
from pathlib import Path
import sys
import numpy as np
import manifold3d as md
import trimesh
from fontTools.ttLib import TTFont
from fontTools.pens.basePen import BasePen

class Contours(BasePen):
    def __init__(self,gs):super().__init__(gs);self.paths=[];self.path=[]
    def _moveTo(self,p):self.path=[p]
    def _lineTo(self,p):self.path.append(p)
    def _qCurveToOne(self,p1,p2):
        p0=self._getCurrentPoint()
        for i in range(1,13):
            t=i/12;self.path.append(tuple((1-t)**2*p0[k]+2*(1-t)*t*p1[k]+t*t*p2[k] for k in range(2)))
    def _curveToOne(self,p1,p2,p3):
        p0=self._getCurrentPoint()
        for i in range(1,15):
            t=i/14;self.path.append(tuple((1-t)**3*p0[k]+3*(1-t)**2*t*p1[k]+3*(1-t)*t*t*p2[k]+t**3*p3[k] for k in range(2)))
    def _closePath(self):
        if len(self.path)>2:self.paths.append(self.path)
        self.path=[]
    def _endPath(self):self._closePath()

def engrave(source,target,spec):
    if Path(target).exists():raise ValueError('Output exists')
    mesh=trimesh.load(source,force='mesh')
    if not mesh.is_watertight or not mesh.is_winding_consistent:raise ValueError('Body must be closed and consistently wound')
    solid=md.Manifold(md.Mesh(np.asarray(mesh.vertices,dtype=np.float32),np.asarray(mesh.faces,dtype=np.uint32)))
    if solid.status()!=md.Error.NoError:raise ValueError(str(solid.status()))
    original_volume=solid.volume()
    line_receipts=[]
    for item in spec['lines']:
        font=TTFont(item['font'],fontNumber=item.get('font_index',0));gs=font.getGlyphSet();cmap=font.getBestCmap();scale=float(item['em_mm'])/font['head'].unitsPerEm
        loops=[];cursor=0
        for char in item['text']:
            if ord(char) not in cmap:raise ValueError('Font does not contain '+char)
            name=cmap[ord(char)];pen=Contours(gs);gs[name].draw(pen)
            loops += [np.array([((p[0]+cursor)*scale,p[1]*scale) for p in path]) for path in pen.paths]
            cursor += font['hmtx'].metrics[name][0]
        if not loops:raise ValueError('No visible glyphs')
        shape=md.CrossSection(loops,md.FillRule.EvenOdd).simplify(float(spec.get('contour_tolerance_mm',.01)))
        cutter=shape.extrude(float(item['extrude_mm'])).transform(item['transform'])
        before=solid.volume()
        solid=solid-cutter
        removed=before-solid.volume()
        if removed<=1e-5:raise ValueError('Lettering line did not intersect body: '+item['text'])
        line_receipts.append({'text':item['text'],'removed_volume_mm3':removed})
        if solid.status()!=md.Error.NoError:raise ValueError(str(solid.status()))
    if solid.volume()>=original_volume-1e-5:raise ValueError('Letter cutters did not intersect the body')
    solid=solid.simplify(float(spec.get('solid_tolerance_mm',.002)))
    result=solid.to_mesh()
    out=trimesh.Trimesh(np.asarray(result.vert_properties)[:,:3],np.asarray(result.tri_verts),process=True)
    if not out.is_watertight:raise ValueError('Lettering export not closed')
    out.export(target)
    return {'kernel':'manifold3d','removed_volume_mm3':original_volume-solid.volume(),'triangles':len(out.faces),'lines':line_receipts,'requires_independent_export_qa':True}

if __name__=='__main__':
    print(json.dumps(engrave(sys.argv[1],sys.argv[2],json.loads(Path(sys.argv[3]).read_text()))))
