"""Only launched with a new isolated GUI Blender instance."""
import importlib.util
import json
import os
from pathlib import Path
import sys
import bpy
config=json.loads(os.environ['VT_BOOTSTRAP'])
if bpy.app.background: raise RuntimeError('MCP addon requires the GUI event loop.')
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.context.scene['vt_session']=config['token']
spec=importlib.util.spec_from_file_location('vt_owned_addon',config['addon'])
addon=importlib.util.module_from_spec(spec);sys.modules[spec.name]=addon;spec.loader.exec_module(addon);addon.register()
bpy.context.scene.blendermcp_auto_start_server=False
bpy.context.scene.blendermcp_port=config['port']
server=addon.BlenderMCPServer(host='127.0.0.1',port=config['port'])
bpy.types.blendermcp_server=server;server.start()
if not server.running: raise RuntimeError('MCP port unavailable')
bpy.context.scene.blendermcp_server_running=True
Path(config['ready']).write_text(json.dumps({'pid':os.getpid(),'port':config['port'],'token':config['token'],'blender_version':bpy.app.version_string}))
