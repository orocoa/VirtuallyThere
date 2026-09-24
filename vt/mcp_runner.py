"""Short-lived owned GUI + genuine SDK MCP client. Never attaches to user scenes."""
import asyncio
from datetime import timedelta
import importlib.util
import json
import os
from pathlib import Path
import socket
import signal
import subprocess
import sys
import time
import uuid
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

ROOT=Path(__file__).resolve().parent


def texts(result):
    return '\n'.join(x.text for x in result.content if x.type=='text')


async def call(config,out,script,brief):
    token=uuid.uuid4().hex
    with socket.socket() as s:
        s.bind(('127.0.0.1',0));port=s.getsockname()[1]
    package=importlib.util.find_spec('blender_mcp')
    addon=Path(next(iter(package.submodule_search_locations)))/'bundled/addon.py'
    bootstrap={'port':port,'token':token,'ready':str(out/'ready.json'),'addon':str(addon)}
    env=dict(os.environ,VT_BOOTSTRAP=json.dumps(bootstrap))
    process=None
    try:
        with (out/'blender.log').open('w') as log:
            process=subprocess.Popen([config['blender'],'--factory-startup','--python',str(ROOT/'blender_bootstrap.py'),'--','vt-owner:'+token],env=env,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
            (out/'launch.json').write_text(json.dumps({'pid':process.pid,'port':port,'token':token}))
            started=time.monotonic()
            while not (out/'ready.json').is_file():
                if process.poll() is not None: raise RuntimeError('Blender exited at startup; inspect blender.log')
                if time.monotonic()-started>75: raise RuntimeError('Blender MCP startup timeout')
                await asyncio.sleep(.3)
            ready=json.loads((out/'ready.json').read_text())
            if ready['pid']!=process.pid or ready['token']!=token: raise RuntimeError('Session identity mismatch')
            params=StdioServerParameters(command=config['mcp_server'],args=['--host','127.0.0.1','--port',str(port)],env=dict(os.environ,BLENDER_HOST='127.0.0.1',BLENDER_PORT=str(port),DISABLE_TELEMETRY='1',BLENDER_MCP_DISABLE_TELEMETRY='1'))
            with (out/'mcp.log').open('w') as mlog:
                async with stdio_client(params,errlog=mlog) as (reader,writer):
                    async with ClientSession(reader,writer,read_timeout_seconds=timedelta(seconds=300)) as session:
                        await session.initialize()
                        listing=await session.list_tools()
                        (out/'tools.json').write_text(listing.model_dump_json(indent=2))
                        if 'execute_blender_code' not in {x.name for x in listing.tools}: raise RuntimeError('Missing execute_blender_code')
                        code=('import bpy,sys\nfrom pathlib import Path\n'
                              f'assert bpy.context.scene.get("vt_session")=={token!r}, "Wrong scene"\n'
                              f'sys.path.insert(0,{str(ROOT.parent)!r})\nVT_OUTPUT={str(out)!r}\n'
                              f'VT_PYTHON={config["geometry_python"]!r}\n'
                              f'VT_BRIEF=__import__("json").loads({brief!r})\n'
                              'VT_PARAMETERS=VT_BRIEF.get("design_contract",{}).get("parameters",{}).copy()\n'
                              +script.read_text()+'\n'+(ROOT/'blender_export.py').read_text())
                        (out/'executed.py').write_text(code)
                        result=await session.call_tool('execute_blender_code',{'code':code,'user_prompt':brief})
                        (out/'response.json').write_text(result.model_dump_json(indent=2))
                        body=texts(result)
                        if result.isError or 'Traceback (most recent call last)' in body or not (out/'export.json').is_file():
                            raise RuntimeError('Modeling/export failed; inspect response.json and blender.log')
                        print(json.dumps({'status':'MODEL_EXPORTED','receipt':str(out/'export.json')}))
    finally:
        if process and process.poll() is None:
            process.terminate()
            try:process.wait(timeout=8)
            except subprocess.TimeoutExpired:process.kill();process.wait(timeout=5)
        (out/'session-closed.json').write_text(json.dumps({'owned_pid':process.pid if process else None,'exited':process is None or process.poll() is not None}))

if __name__=='__main__':
    def terminate(signum,frame): raise KeyboardInterrupt('Worker terminated')
    signal.signal(signal.SIGTERM,terminate)
    request=json.loads(Path(sys.argv[1]).read_text())
    try:asyncio.run(call(request['config'],Path(request['output']),Path(request['script']),request['brief']))
    except Exception as exc:print(json.dumps({'error':str(exc)}));sys.exit(2)
