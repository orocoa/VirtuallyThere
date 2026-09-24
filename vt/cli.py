import argparse
import json
from pathlib import Path
import sys
from . import __version__
from .config import settings
from .store import init,add_brief,revise_model,read
from .prompts import prompts
from . import pipeline


def doctor():
    c=settings();found={k:{'path':v,'exists':Path(v).exists()} for k,v in c.items()}
    import importlib.util
    modules={name:importlib.util.find_spec(name) is not None for name in ('numpy','trimesh','open3d','shapely','mcp','blender_mcp','manifold3d','fontTools')}
    required=('geometry_python','mcp_python','mcp_server','blender','studio')
    return {'version':__version__,'ok':all(found[k]['exists'] for k in required) and all(modules.values()),'paths':found,'modules':modules,
      'mode':'Codex handles design and imagegen; local tools export and check models.',
      'automatic_slicing':False,'printer_control':False,'startup':'doctor never launches GUI apps'}


def main(argv=None):
    p=argparse.ArgumentParser(prog='vt',description='Virtually There — Codex-directed text/photos to import-ready abstract objects')
    s=p.add_subparsers(dest='cmd',required=True)
    s.add_parser('doctor')
    q=s.add_parser('init');q.add_argument('job');q.add_argument('--text');q.add_argument('--images',nargs='*',default=[])
    q=s.add_parser('brief');q.add_argument('job');q.add_argument('--file',required=True)
    for name in ('prompts','check','deliver','status','open-studio'):
        q=s.add_parser(name);q.add_argument('job')
    q=s.add_parser('revise-model');q.add_argument('job');q.add_argument('--parameters',help='JSON file patching existing design-contract parameters')
    q=s.add_parser('concept');q.add_argument('job');q.add_argument('--file',required=True);q.add_argument('--views',required=True)
    for name in ('concept-review','review'):
        q=s.add_parser(name);q.add_argument('job');q.add_argument('--file',required=True)
    q=s.add_parser('finish');q.add_argument('job');q.add_argument('--review',required=True);q.add_argument('--open-studio',action='store_true')
    q=s.add_parser('model');q.add_argument('job');q.add_argument('--script',required=True)
    q=s.add_parser('import-model');q.add_argument('job');q.add_argument('--stl',required=True);q.add_argument('--editable',required=True);q.add_argument('--views',required=True)
    a=p.parse_args(argv)
    try:
        if a.cmd=='doctor':result=doctor()
        elif a.cmd=='init':result=init(a.job,a.text,a.images)
        elif a.cmd=='brief':result=add_brief(a.job,a.file)
        elif a.cmd=='prompts':result=prompts(a.job)
        elif a.cmd=='concept':result=pipeline.concept(a.job,a.file,a.views)
        elif a.cmd=='concept-review':result=pipeline.concept_review(a.job,a.file)
        elif a.cmd=='revise-model':
            parameters=read(a.parameters) if a.parameters is not None else None
            if a.parameters is not None and not isinstance(parameters,dict):raise ValueError('Parameter patch must be a JSON object.')
            result=revise_model(a.job,parameters)
        elif a.cmd=='model':result=pipeline.model(a.job,script=a.script)
        elif a.cmd=='import-model':result=pipeline.model(a.job,stl=a.stl,editable=a.editable,views=a.views)
        elif a.cmd=='check':result=pipeline.check(a.job)
        elif a.cmd=='review':result=pipeline.review(a.job,a.file)
        elif a.cmd=='finish':
            pipeline.review(a.job,a.review)
            result=pipeline.deliver(a.job)
            if a.open_studio:result['studio']=pipeline.open_studio(a.job)
        elif a.cmd=='deliver':result=pipeline.deliver(a.job)
        elif a.cmd=='open-studio':result=pipeline.open_studio(a.job)
        else:result=pipeline.status(a.job)
        print(json.dumps(result,ensure_ascii=False,indent=2))
        return 2 if result.get('ok') is False or result.get('status') in ('NEEDS_REPAIR','INTEGRITY_ERROR') else 0
    except (ValueError,OSError,KeyError,TypeError) as exc:
        print(json.dumps({'status':'BLOCKED','error':str(exc)},ensure_ascii=False),file=sys.stderr);return 2

if __name__=='__main__':sys.exit(main())
