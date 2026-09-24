"""Screen a mesh with the bundled geometry backend; never repairs it implicitly."""
import json
import hashlib
import sys
from pathlib import Path
import numpy as np
import trimesh


def load(path):
    m = trimesh.load(path, force='mesh', process=False)
    if not isinstance(m, trimesh.Trimesh) or not len(m.faces) or not np.isfinite(m.vertices).all():
        raise ValueError('Empty mesh or nonfinite vertices.')
    # Exact equality only. A near-coordinate weld must be an explicit new model.
    verts, inverse = np.unique(m.vertices, axis=0, return_inverse=True)
    return trimesh.Trimesh(verts, inverse[m.faces], process=False)


def run(model, out):
    # Support both `python -m vt.geometry_worker` and direct worker execution.
    if __package__:
        from .geometry_backend import topology
    else:
        from geometry_backend import topology
    from shapely.geometry import Polygon, Point
    from shapely.ops import unary_union
    m = load(model)
    if len(m.faces)>25000:
        Path(out).write_text(json.dumps({"status":"NEEDS_REPAIR","hard_checks":{"analysis_budget":False},"triangles":len(m.faces),"error":"Reduce mesh before native topology analysis."},indent=2))
        return 2
    topo = topology(m)
    hard = {
      'closed': bool(m.is_watertight), 'consistent_winding': bool(m.is_winding_consistent),
      'positive_volume': bool(m.volume > 0), 'one_component': len(m.split(only_watertight=False)) == 1,
      'nondegenerate': bool(np.all(m.area_faces > 1e-10)),
      'manifold': topo['edge_manifold'] and topo['vertex_manifold'] and topo['orientable'],
      'no_self_intersections': not topo['self_intersecting'],
      'on_bed': abs(float(m.bounds[0,2])) < 1e-4,
      'desktop_size': bool(np.all(m.extents >= 1.25) and np.all(m.extents <= 200)),
      'analysis_budget': len(m.faces) <= 25000,
    }
    result = {'hard_checks': hard, 'triangles': len(m.faces), 'dimensions_mm': m.extents.tolist(), 'bounds_mm': m.bounds.tolist(), 'topology': topo, 'advisories': [], 'scope': 'Fast geometry screening for importing a decorative single-body model into Bambu Studio; no wall-thickness, toolpath, strength or physical-print certification.'}
    if all(hard.values()):
        contact = unary_union([Polygon(t[:,:2]) for t in m.triangles[np.all(np.abs(m.triangles[:,:,2]) < 1e-4, axis=1)]])
        p = Point(m.center_mass[:2]); hull = contact.convex_hull
        margin = float(hull.boundary.distance(p)) if not hull.is_empty and hull.covers(p) else -1
        hard['contact'] = contact.area >= 25
        hard['stability'] = margin >= 2 and margin / max(float(m.center_mass[2]), 1e-6) >= .12
        result['contact_mm2'] = contact.area; result['stability_margin_mm'] = margin
        risky = (m.triangles_center[:,2] > 1e-4) & (m.face_normals[:,2] < -np.sqrt(.5)-1e-5)
        area = float(m.area_faces[risky].sum()); result['downward_area_mm2'] = area
        if area > 1e-5: result['advisories'].append('OVERHANG: inspect orientation, supports and bridge/overhang toolpaths in Bambu Studio before printing; geometry screening does not certify printability.')
    result['model_sha256']=hashlib.sha256(Path(model).read_bytes()).hexdigest()
    result['status'] = 'GEOMETRY_CHECKED' if all(hard.values()) else 'NEEDS_REPAIR'
    Path(out).write_text(json.dumps(result, indent=2))
    print(json.dumps({'status': result['status'], 'failed': [k for k,v in hard.items() if not v], 'advisories': result['advisories']}))
    return 0 if all(hard.values()) else 2

if __name__ == '__main__':
    try: sys.exit(run(*sys.argv[1:]))
    except Exception as exc:
        Path(sys.argv[2]).write_text(json.dumps({'status':'NEEDS_REPAIR','error':str(exc),'hard_checks':{'analysis_completed':False}},indent=2))
        print(json.dumps({'error':str(exc)}));sys.exit(2)
