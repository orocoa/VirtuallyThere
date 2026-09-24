"""Appended to each authored modeling script by the MCP runner."""
import bpy
import hashlib
import json
from pathlib import Path
from mathutils import Vector
root=Path(VT_OUTPUT)
scene=bpy.context.scene
obj=bpy.data.objects.get('VT_MODEL')
if obj is None or obj.type!='MESH': raise ValueError('Script must leave the printable mesh named VT_MODEL.')
scene.unit_settings.system='METRIC';scene.unit_settings.scale_length=.001;scene.unit_settings.length_unit='MILLIMETERS'
bpy.ops.object.select_all(action='DESELECT');obj.hide_set(False);obj.hide_render=False;obj.select_set(True);bpy.context.view_layer.objects.active=obj
obj.data=obj.data.copy()
bpy.ops.object.transform_apply(location=False,rotation=False,scale=True)
for other in scene.objects:
    if other.type=='MESH' and other!=obj: other.hide_render=True;other.hide_set(True)
for poly in obj.data.polygons:poly.use_smooth=True
bpy.ops.wm.stl_export(filepath=str(root/'model.stl'),export_selected_objects=True,global_scale=1,apply_modifiers=True,use_scene_unit=False)
# Inspect/preview the exact exported file, not only the pre-export editable object.
obj.hide_set(True);obj.hide_render=True
bpy.ops.wm.stl_import(filepath=str(root/'model.stl'))
visible=bpy.context.object;visible.name='VT_EXPORT_READBACK'
import bmesh,math
bm=bmesh.new();bm.from_mesh(visible.data)
for face in bm.faces:face.smooth=True
for edge in bm.edges:
    if edge.is_manifold:edge.smooth=edge.calc_face_angle(0)<math.radians(35)
bm.to_mesh(visible.data);bm.free();visible.data.update()
scene.world=scene.world or bpy.data.worlds.new('World')
scene.render.engine='BLENDER_WORKBENCH'
scene.display.shading.light='STUDIO';scene.display.shading.color_type='SINGLE'
scene.display.shading.single_color=(.045,.045,.045) if VT_BRIEF.get('color')=='black' else (.78,.78,.76)
scene.display.shading.show_shadows=True;scene.display.shading.show_cavity=True
scene.display.shading.background_type='WORLD';scene.world.color=(.3,.3,.3) if VT_BRIEF.get('color')=='black' else (.09,.09,.09)
scene.render.resolution_x=800;scene.render.resolution_y=800;scene.render.resolution_percentage=100
scene.render.image_settings.file_format='PNG';scene.render.film_transparent=False
center=sum((visible.matrix_world@Vector(p) for p in visible.bound_box),Vector())/8
scale=max(visible.dimensions)*1.35
camdata=bpy.data.cameras.new('VT_CAM');camera=bpy.data.objects.new('VT_CAM',camdata);scene.collection.objects.link(camera);scene.camera=camera
camdata.type='ORTHO';camdata.ortho_scale=scale;camdata.clip_end=10000
views={'front':(0,-1,0),'right':(1,0,0),'back':(0,1,0),'top':(0,0,1),'bottom':(0,0,-1),'three-quarter':(1,-2,1.2)}
(root/'views').mkdir(exist_ok=True)
for name,axis in views.items():
    direction=Vector(axis).normalized();camera.location=center+direction*scale*3
    camera.rotation_euler=(-direction).to_track_quat('-Z','Y').to_euler()
    scene.render.filepath=str(root/'views'/f'{name}.png');bpy.ops.render.render(write_still=True)
# Keep source and exact export readback separately editable, save after all views.
bpy.ops.wm.save_as_mainfile(filepath=str(root/'model.blend'))
receipt={'dimensions_mm':list(visible.dimensions),'model_sha256':hashlib.sha256((root/'model.stl').read_bytes()).hexdigest(),'views':list(views),'transport':'actual Blender MCP execute_blender_code','render_source':'STL reimport','units':'mm'}
(root/'export.json').write_text(json.dumps(receipt,indent=2));print(json.dumps(receipt))
