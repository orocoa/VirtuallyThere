"""Reusable shape operations, executed inside Blender through MCP. Units are mm."""
import math
import bpy


def solid_from_spec(spec, output, python, name='VT_MODEL'):
    """Build with external Manifold, then import the millimetre STL into Blender."""
    import json
    from pathlib import Path
    import subprocess
    import uuid
    stem=Path(output)/('solid-'+uuid.uuid4().hex[:12])
    source=stem.with_suffix('.json');target=stem.with_suffix('.stl')
    with source.open('x') as stream:json.dump(spec,stream,allow_nan=False)
    subprocess.run([python,'-m','vt.solid_geometry',str(source),str(target)],
                   cwd=str(Path(__file__).resolve().parents[1]),check=True,timeout=90)
    bpy.ops.wm.stl_import(filepath=str(target),use_scene_unit=False)
    obj=bpy.context.object;obj.name=name;obj.data=obj.data.copy()
    return obj


def loft(name, stations, segments=48):
    """Stations: [z, center_x, center_y, radius_x, radius_y]."""
    if len(stations) < 2 or any(len(s)!=5 or min(s[3:])<=0 for s in stations):
        raise ValueError('Loft requires positive radii and at least two five-value stations.')
    if any(b[0]<=a[0] for a,b in zip(stations,stations[1:])):
        raise ValueError('Loft station Z must increase.')
    vertices=[];faces=[]
    for z,x,y,rx,ry in stations:
        vertices += [(x+rx*math.cos(i*2*math.pi/segments),y+ry*math.sin(i*2*math.pi/segments),z) for i in range(segments)]
    for k in range(len(stations)-1):
        for i in range(segments):
            a=k*segments+i;b=k*segments+(i+1)%segments
            faces.append((a,b,b+segments,a+segments))
    faces += [tuple(reversed(range(segments))),tuple((len(stations)-1)*segments+i for i in range(segments))]
    mesh=bpy.data.meshes.new(name);mesh.from_pydata(vertices,[],faces);mesh.update()
    obj=bpy.data.objects.new(name,mesh);bpy.context.scene.collection.objects.link(obj)
    return obj


def ellipsoid(name, center, radii):
    bpy.ops.mesh.primitive_uv_sphere_add(segments=48,ring_count=24,location=center)
    obj=bpy.context.object;obj.name=name;obj.scale=radii
    bpy.ops.object.transform_apply(location=False,rotation=False,scale=True)
    return obj


def fuse(parts, voxel=.5, smooth=4, budget=18000):
    if not parts or not .2<=voxel<=1.0: raise ValueError('Invalid fusion request')
    bpy.ops.object.select_all(action='DESELECT')
    for obj in parts: obj.select_set(True)
    bpy.context.view_layer.objects.active=parts[0];bpy.ops.object.join();obj=bpy.context.object
    mod=obj.modifiers.new('Volume fusion','REMESH');mod.mode='VOXEL';mod.voxel_size=voxel
    bpy.ops.object.modifier_apply(modifier=mod.name)
    if smooth:
        mod=obj.modifiers.new('Shape smoothing','SMOOTH');mod.factor=1;mod.iterations=smooth
        bpy.ops.object.modifier_apply(modifier=mod.name)
    obj.data.calc_loop_triangles()
    if len(obj.data.loop_triangles)>budget:
        mod=obj.modifiers.new('Mesh budget','DECIMATE');mod.ratio=budget/len(obj.data.loop_triangles)
        bpy.ops.object.modifier_apply(modifier=mod.name)
    return obj


def flat_bottom(obj,z=0):
    bpy.ops.mesh.primitive_cube_add(size=1,location=(0,0,z-500))
    cut=bpy.context.object;cut.scale=(1000,1000,1000)
    bpy.ops.object.transform_apply(location=False,rotation=False,scale=True)
    bpy.context.view_layer.objects.active=obj
    mod=obj.modifiers.new('Integral resting surface','BOOLEAN');mod.operation='DIFFERENCE';mod.solver='EXACT';mod.object=cut
    bpy.ops.object.modifier_apply(modifier=mod.name);bpy.data.objects.remove(cut,do_unlink=True)
    return obj
