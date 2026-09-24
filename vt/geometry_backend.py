"""Native topology screening without vendoring geometry-library code.

Extracted from the project-owned thought-to-3d-print geometry module.
Copyright (c) 2026 LuumiAI. MIT license: see GEOMETRY_LICENSE.txt.
The implementation calls the separately installed Open3D public API.
"""
import numpy as np

def topology(mesh):
    # Use a separately maintained native geometry library for vertex manifold and
    # self-intersection, rather than treating edge incidence as sufficient.
    import open3d as o3d
    native=o3d.geometry.TriangleMesh(
        o3d.utility.Vector3dVector(np.asarray(mesh.vertices)),
        o3d.utility.Vector3iVector(np.asarray(mesh.faces,dtype=np.int32)))
    return {'edge_manifold':bool(native.is_edge_manifold(allow_boundary_edges=False)),
            'vertex_manifold':bool(native.is_vertex_manifold()),
            'self_intersecting':bool(native.is_self_intersecting()),
            'orientable':bool(native.is_orientable()),'open3d':o3d.__version__}
