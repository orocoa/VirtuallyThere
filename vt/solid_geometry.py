"""Small constructive shape helpers, in millimetres, for the external VT Python.

Manifold is deliberately not imported inside Blender. Build an STL here and
import it into Blender for further edits, preview and the existing export checks.
These helpers check topology, not all physical printing constraints.
"""
import argparse
import json
import math
from numbers import Real
from pathlib import Path

import manifold3d as md
import numpy as np
from shapely.geometry import Polygon
import trimesh


def _number(value, name, positive=False):
    if isinstance(value, bool) or not isinstance(value, Real):
        raise ValueError(f'{name} must be a finite number')
    try:
        value = float(value)
    except (OverflowError, ValueError) as exc:
        raise ValueError(f'{name} must be a finite number') from exc
    if not math.isfinite(value):
        raise ValueError(f'{name} must be a finite number')
    if positive and value <= 0:
        raise ValueError(f'{name} must be positive')
    return value


def _checked(solid):
    if not isinstance(solid, md.Manifold):
        raise ValueError('Expected a Manifold solid')
    volume = solid.volume()
    if solid.status() != md.Error.NoError or solid.is_empty() or not math.isfinite(volume) or volume <= 0:
        raise ValueError('Operation produced an empty or invalid solid')
    return solid


def arc_band(inner_radius_mm, outer_radius_mm, height_mm, sweep_degrees=240,
             start_degrees=0, end_height_mm=None, segments=80):
    """Open circular band, flat Z=0 bottom and optional linear height ramp.

    Angles advance counterclockwise around +Z from +X. Ends remain open relative
    to each other, but each end of the solid is capped. No bevel is added.
    """
    inner = _number(inner_radius_mm, 'inner_radius_mm', True)
    outer = _number(outer_radius_mm, 'outer_radius_mm', True)
    height = _number(height_mm, 'height_mm', True)
    end_height = height if end_height_mm is None else _number(end_height_mm, 'end_height_mm', True)
    sweep = _number(sweep_degrees, 'sweep_degrees', True)
    start = _number(start_degrees, 'start_degrees')
    if outer <= inner or sweep >= 360:
        raise ValueError('Outer radius must exceed inner radius and sweep must be below 360 degrees')
    if isinstance(segments, bool) or not isinstance(segments, int) or not 3 <= segments <= 1024:
        raise ValueError('segments must be an integer from 3 to 1024')
    if sweep / segments >= 180:
        raise ValueError('Arc segments must span less than 180 degrees')
    vertices, faces = [], []
    for i in range(segments + 1):
        angle = math.radians(start % 360 + sweep * i / segments)
        c, s = math.cos(angle), math.sin(angle)
        h = height + (end_height - height) * i / segments
        vertices.extend([(inner*c, inner*s, 0), (outer*c, outer*s, 0),
                         (outer*c, outer*s, h), (inner*c, inner*s, h)])
    def quad(a, b, c, d):
        faces.extend([(a, b, c), (a, c, d)])
    quad(0, 1, 2, 3)
    for i in range(segments):
        for j in range(4):
            a, b = 4*i+j, 4*i+(j+1) % 4
            quad(a, a+4, b+4, b)
    end = 4*segments
    quad(end+3, end+2, end+1, end)
    return _checked(md.Manifold(md.Mesh(
        np.asarray(vertices, dtype=np.float32), np.asarray(faces, dtype=np.uint32))))


def _loop(points, name):
    if not isinstance(points, (list, tuple)) or len(points) < 3:
        raise ValueError(f'{name} requires at least three XY points')
    result = []
    for point in points:
        if not isinstance(point, (list, tuple)) or len(point) != 2:
            raise ValueError(f'{name} points must have two coordinates')
        result.append(tuple(_number(v, name) for v in point))
    if result[0] == result[-1]:
        result.pop()
    if len(set(result)) != len(result) or len(result) < 3:
        raise ValueError(f'{name} contains duplicate or insufficient points')
    return result


def profile_extrude(outline, height_mm, holes=()):
    """Extrude one simple XY polygon with optional interior holes from Z=0.

    Hole winding is immaterial. Overlapping, touching or out-of-outline holes
    and self-intersecting outlines are rejected rather than silently repaired.
    """
    height = _number(height_mm, 'height_mm', True)
    outer = _loop(outline, 'outline')
    if not isinstance(holes, (list, tuple)):
        raise ValueError('holes must be a list of loops')
    inner = [_loop(hole, 'hole') for hole in holes]
    polygon = Polygon(outer, inner)
    if not polygon.is_valid or polygon.is_empty or polygon.area <= 0:
        raise ValueError('Outline and holes must form a valid, positive-area polygon')
    outer_polygon = Polygon(outer)
    hole_polygons = [Polygon(loop) for loop in inner]
    if any(not outer_polygon.boundary.disjoint(hole) for hole in hole_polygons) or any(
            not hole.disjoint(other) for i, hole in enumerate(hole_polygons) for other in hole_polygons[:i]):
        raise ValueError('Holes must not touch the outline or each other')
    cross_section = md.CrossSection([outer, *inner], md.FillRule.EvenOdd)
    return _checked(cross_section.extrude(height))


def subtract(body, cutters):
    """Subtract solids, rejecting cuts that remove nothing or the entire body."""
    result = _checked(body)
    for cutter in cutters:
        _checked(cutter)
        before = result.volume()
        result = _checked(result - cutter)
        if before - result.volume() <= max(1e-8, before * 1e-10):
            raise ValueError('A cutter did not remove measurable volume')
    return result


def export_stl(solid, target):
    """Export one closed connected solid without overwriting an existing file."""
    _checked(solid)
    if len(solid.decompose()) != 1:
        raise ValueError('Export requires one connected solid')
    data = solid.to_mesh()
    mesh = trimesh.Trimesh(np.asarray(data.vert_properties)[:, :3],
                           np.asarray(data.tri_verts), process=True)
    if (not np.isfinite(mesh.vertices).all() or not mesh.is_watertight
            or not mesh.is_winding_consistent or mesh.volume <= 0
            or np.any(mesh.area_faces <= 0)):
        raise ValueError('Export mesh failed topology checks')
    target = Path(target)
    with target.open('xb') as stream:
        stream.write(trimesh.exchange.stl.export_stl(mesh))
    return {'path': str(target.resolve()), 'units': 'mm', 'triangles': len(mesh.faces),
            'volume_mm3': float(mesh.volume), 'dimensions_mm': mesh.extents.tolist(),
            'requires_independent_export_qa': True}


_OPERATIONS = {'arc_band': arc_band, 'profile_extrude': profile_extrude}


def _operation(spec):
    if not isinstance(spec, dict) or set(spec) - {'operation', 'parameters', 'translation_mm'}:
        raise ValueError('Invalid operation specification')
    name = spec.get('operation')
    operation = _OPERATIONS.get(name) if isinstance(name, str) else None
    parameters = spec.get('parameters')
    if operation is None or not isinstance(parameters, dict):
        raise ValueError('Use arc_band or profile_extrude with a parameters object')
    try:
        solid = operation(**parameters)
    except TypeError as exc:
        raise ValueError(f'Invalid operation parameters: {exc}') from exc
    if 'translation_mm' in spec:
        translation = spec['translation_mm']
        if not isinstance(translation, (list, tuple)) or len(translation) != 3:
            raise ValueError('translation_mm requires three numbers')
        solid = solid.translate([_number(v, 'translation_mm') for v in translation])
    return _checked(solid)


def build(spec):
    """Evaluate one base operation and optional translated solid cuts."""
    if not isinstance(spec, dict) or set(spec) - {'operation', 'parameters', 'cuts', 'translation_mm'}:
        raise ValueError('Invalid shape specification')
    cuts = spec.get('cuts', [])
    if not isinstance(cuts, list) or len(cuts) > 32:
        raise ValueError('cuts must be a list of at most 32 operations')
    body = _operation({k: v for k, v in spec.items() if k != 'cuts'})
    return subtract(body, (_operation(cut) for cut in cuts))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('spec', type=Path)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    try:
        result = export_stl(build(json.loads(args.spec.read_text())), args.output)
    except (ValueError, OSError) as exc:
        parser.exit(1, f'{exc}\n')
    print(json.dumps(result))


if __name__ == '__main__':
    main()
