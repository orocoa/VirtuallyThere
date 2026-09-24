import html
import json
from pathlib import Path
import subprocess
import os
import signal
import sys
from .store import (VIEWS,read,write,sha,artifact,verify,snapshot,locked,save,revision,integrity,now)
from .config import ROOT,settings


def concept(job,file,views):
    viewset=set(views.split(','))
    if not viewset <= VIEWS or len(viewset)<2: raise ValueError('Every concept image must show at least two distinct named views.')
    if Path(file).suffix.lower() not in ('.png','.jpg','.jpeg','.webp'): raise ValueError('Use a viewable concept image')
    with locked(job) as (job,data):
        folder,r=revision(job,data)
        if 'concept_review' in r: raise ValueError('Concept locked; create a new revision to change it.')
        dest=snapshot(file,folder/'concept'/('%02d'%len(r['concepts'])+Path(file).suffix.lower()))
        r['concepts'].append({'artifact':artifact(dest,job),'views':sorted(viewset)})
        r['state']='CONCEPT_REGISTERED';save(job,data,'concept_registered')
        return {'views_available':sorted(set().union(*(set(x['views']) for x in r['concepts'])))}


def concept_review(job,file):
    record=read(file)
    with locked(job) as (job,data):
        folder,r=revision(job,data);integrity(data,job)
        if len(r['concepts'])<2 or set().union(*(set(x['views']) for x in r['concepts'])) != VIEWS:
            raise ValueError('Two or more multi-angle boards covering all six views required.')
        expected={x['artifact']['sha256'] for x in r['concepts']}
        if len(expected)<2:raise ValueError('Concept boards must be different images, not duplicated files.')
        if set(record.get('concept_sha256',[])) != expected:raise ValueError('Review must bind exact concept images')
        if record.get('reviewer')!='codex' or not record.get('observations') or not record.get('direction_reason'):
            raise ValueError('Record actual observations and automatic direction choice, reviewer=codex')
        required={'same_object','connections_consistent','voids_consistent','lettering_consistent','single_material_feasible'}
        if set(record.get('checks',{}))!=required or any(v is not True for v in record['checks'].values()):
            raise ValueError('Concept consistency checks must all pass; regenerate inconsistent views.')
        dest=snapshot(file,folder/('concept-review-%03d.json'%(len(list(folder.glob('concept-review-*.json')))+1)))
        r['concept_review']={'record':artifact(dest,job)};r['state']='CONCEPT_READY';save(job,data,'concept_reviewed')
        return {'status':r['state']}


def _files(folder,job):
    return {str(p.relative_to(folder)):artifact(p,job) for p in sorted(folder.rglob('*')) if p.is_file()}


def _worker(command,folder,timeout):
    with (folder/'worker.log').open('w') as log:
        process=subprocess.Popen(command,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
        try:
            return process.wait(timeout=timeout)
        except (subprocess.TimeoutExpired,KeyboardInterrupt):
            process.terminate()
            try:process.wait(timeout=20)
            except subprocess.TimeoutExpired:pass
            cleanup_note=''
            try:
                # A promptly exited worker may still have live child processes in its group.
                try:os.killpg(process.pid,signal.SIGTERM)
                except ProcessLookupError:pass
                import time
                deadline=time.monotonic()+2
                while time.monotonic()<deadline:
                    try:os.killpg(process.pid,0)
                    except ProcessLookupError:break
                    time.sleep(.1)
                try:os.killpg(process.pid,signal.SIGKILL)
                except ProcessLookupError:pass
            except PermissionError:
                # The OS can deny a group probe after termination. Do not retry denied signals.
                cleanup_note=' Process-group cleanup could not be fully verified (OS denied access).'
            process.wait(timeout=5)
            # Blender owns a separate session. Only its unique launch token allows cleanup.
            launch=folder/'launch.json'
            if launch.exists():
                owned=read(launch)
                probe=subprocess.run(['/bin/ps','-p',str(owned['pid']),'-o','command='],capture_output=True,text=True)
                if str(ROOT/'vt/blender_bootstrap.py') in probe.stdout and ('vt-owner:'+owned['token']) in probe.stdout:
                    try:os.kill(owned['pid'],signal.SIGTERM)
                    except ProcessLookupError:pass
            raise ValueError('Worker interrupted or timed out; saved logs: '+str(folder)+cleanup_note)


def model(job,script=None,stl=None,editable=None,views=None):
    config=settings()
    with locked(job) as (job,data):
        folder,r=revision(job,data);integrity(data,job)
        if 'concept_review' not in r:raise ValueError('Multi-angle concepts must be inspected before modeling.')
        if 'model' in r:raise ValueError('A model already exists in this revision; revise to preserve it.')
        out=folder/('model-%03d'%(len(list(folder.glob('model-*')))+1));out.mkdir(exist_ok=False)
        if script:
            src=snapshot(script,out/'authored-model.py')
            brief=read(verify(r['brief'],job))
            request=out/'request.json';write(request,{'config':config,'output':str(out),'script':str(src),'brief':json.dumps(brief,ensure_ascii=False)})
            rc=_worker([config['mcp_python'],str(ROOT/'vt/mcp_runner.py'),str(request)],out,390)
            expected=[out/'model.stl',out/'model.blend',out/'export.json']+[out/'views'/(name+'.png') for name in VIEWS]
            if rc or any(not p.is_file() or p.stat().st_size==0 for p in expected):
                r['state']='NEEDS_REPAIR';r['error']='MCP modeling failed; see '+str(out);save(job,data,'model_failed')
                raise ValueError(r['error'])
        else:
            if not editable or not views or Path(editable).suffix not in ('.blend','.3dm'):raise ValueError('Import requires .blend/.3dm source and an actual STL-rendered views directory.')
            snapshot(stl,out/'model.stl');snapshot(editable,out/('model'+Path(editable).suffix))
            for name in sorted(VIEWS):snapshot(Path(views)/(name+'.png'),out/'views'/(name+'.png'))
            write(out/'export.json',{'transport':'explicit existing-model intake','model_sha256':sha(out/'model.stl'),'render_source':'to be verified by Codex against actual export','units':'mm'})
        r['model']={'folder':str(out.relative_to(job)),'artifacts':_files(out,job),'stl':artifact(out/'model.stl',job),'editable':artifact(next(p for p in (out/'model.blend',out/'model.3dm') if p.exists()),job)}
        r['state']='MODEL_EXPORTED';r.pop('error',None);save(job,data,'model_exported')
        return {'status':r['state'],'model':str(out/'model.stl'),'views':str(out/'views')}


def check(job):
    c=settings()
    with locked(job) as (job,data):
        folder,r=revision(job,data);integrity(data,job)
        if 'model' not in r:raise ValueError('No model exported.')
        if 'geometry' in r and read(verify(r['geometry']['report'],job))['status']=='GEOMETRY_CHECKED':return read(verify(r['geometry']['report'],job))
        out=folder/('geometry-%03d'%(len(list(folder.glob('geometry-*')))+1));out.mkdir(exist_ok=False)
        src=verify(r['model']['stl'],job);report=out/'report.json'
        rc=_worker([c['geometry_python'],str(ROOT/'vt/geometry_worker.py'),str(src),str(report)],out,240)
        result=read(report) if report.exists() else {'status':'NEEDS_REPAIR','error':'Worker did not return a report'}
        required={'closed','consistent_winding','positive_volume','one_component','nondegenerate','manifold','no_self_intersections','on_bed','desktop_size','analysis_budget','contact','stability'}
        checks=result.get('hard_checks',{})
        if rc!=0 or not required<=checks.keys() or any(checks[k] is not True for k in required) or result.get('model_sha256')!=r['model']['stl']['sha256'] or sha(src)!=r['model']['stl']['sha256']:
            result['status']='NEEDS_REPAIR';result['worker_returncode']=rc
        write(report,result)
        r['geometry']={'artifacts':_files(out,job),'report':artifact(report,job)}
        r['state']=result['status'];save(job,data,'geometry_checked')
        return {'status':r['state'],'report':str(report),'failed':[k for k,v in result.get('hard_checks',{}).items() if not v], 'advisories':result.get('advisories',[])}


def review(job,file):
    """Bind actual visual observations to an import-ready model, never to a print claim."""
    record=read(file)
    with locked(job) as (job,data):
        folder,r=revision(job,data);integrity(data,job)
        if 'geometry' not in r or read(verify(r['geometry']['report'],job))['status']!='GEOMETRY_CHECKED':
            raise ValueError('Passing geometry checks required before visual review.')
        for key,item in [('model_sha256',r['model']['stl']),('geometry_report_sha256',r['geometry']['report'])]:
            if record.get(key)!=item['sha256']:raise ValueError('Review is stale or wrong: '+key)
        needed={'silhouette','side_back_volume','meaning_preserved','lettering','resting_surface'}
        if record.get('reviewer')!='codex' or set(record.get('checks',{}))!=needed or any(v is not True for v in record['checks'].values()):
            raise ValueError('Record actual observations for all five design checks.')
        if not record.get('observations'):raise ValueError('Review requires concrete observations')
        brief=read(verify(r['brief'],job))
        if 'design_contract' in brief:
            if record.get('brief_sha256')!=r['brief']['sha256']:
                raise ValueError('Review must bind the current brief, including revised parameters.')
            evidence=record.get('invariant_checks')
            if not isinstance(evidence,list) or len(evidence)!=len(brief['invariants']):
                raise ValueError('Review every design invariant against actual model views.')
            seen=set()
            for item in evidence:
                if not isinstance(item,dict) or not isinstance(item.get('invariant'),str):
                    raise ValueError('Each invariant check needs an invariant, views, observation and passed=true.')
                name=item['invariant'];views=item.get('views')
                if name not in brief['invariants'] or name in seen or item.get('passed') is not True:
                    raise ValueError('Unresolved, duplicate or unknown design invariant: '+name)
                if not isinstance(views,list) or not views or any(not isinstance(v,str) or v not in VIEWS for v in views):
                    raise ValueError('Name the actual model views used to check each invariant.')
                if not isinstance(item.get('observation'),str) or not item['observation'].strip():
                    raise ValueError('Record a concrete visual observation for each invariant.')
                seen.add(name)
        review_dir=folder/('review-%03d'%(len(list(folder.glob('review-*')))+1));review_dir.mkdir(exist_ok=False)
        record_path=snapshot(file,review_dir/'review.json')
        r['model_review']={'record':artifact(record_path,job)}
        r['state']='MODEL_READY';save(job,data,'same_revision_visual_review_completed')
        return {'status':r['state'],'scope':'Geometry and visual review only. Slice and print manually in Studio.'}


def deliver(job):
    with locked(job) as (job,data):
        folder,r=revision(job,data);integrity(data,job)
        if r['state']!='MODEL_READY':raise ValueError('Complete geometry and visual review before delivery.')
        if 'delivery' in r:return {'delivery':str(job/r['delivery']['folder']),'status':r['state']}
        out=folder/('delivery-%03d'%(len(list(folder.glob('delivery-*')))+1));out.mkdir(exist_ok=False)
        mappings={'model.stl':r['model']['stl'],'model'+Path(r['model']['editable']['path']).suffix:r['model']['editable']}
        for name,item in mappings.items():snapshot(verify(item,job),out/name)
        for name in sorted(VIEWS):snapshot(job/r['model']['folder']/'views'/(name+'.png'),out/'views'/(name+'.png'))
        geo=read(verify(r['geometry']['report'],job));brief=read(verify(r['brief'],job))
        write(out/'manifest.json',{'status':'MODEL_READY','revision':data['current'],'model_sha256':sha(out/'model.stl'),'units':'mm','dimensions_mm':geo['dimensions_mm'],'advisories':geo.get('advisories',[]),'physical_print_started':False,'scope':'Ready to import. Wall thickness, supports and toolpaths must be reviewed in the slicer.'})
        snapshot(verify(r['geometry']['report'],job),out/'geometry.json')
        cards=''.join('<figure><img src="views/'+name+'.png"><figcaption>'+name+'</figcaption></figure>' for name in sorted(VIEWS))
        notices=''.join('<li>'+html.escape(x)+'</li>' for x in geo.get('advisories',[]))
        editable='model'+Path(r['model']['editable']['path']).suffix
        page='<!doctype html><meta charset="utf-8"><meta name="viewport" content="width=device-width"><title>'+html.escape(brief['title'])+'</title><style>body{font:16px system-ui;max-width:1100px;margin:40px auto;padding:0 20px;background:#eee;color:#222}main{display:grid;grid-template-columns:repeat(auto-fit,minmax(240px,1fr))}img{width:100%}figure{margin:8px}a{margin-right:20px}</style><h1>'+html.escape(brief['title'])+'</h1><p>'+html.escape(brief['meaning'])+'</p><p>Ready to import · millimetres. Slice and print manually in Bambu Studio.</p><ul>'+notices+'</ul><p><a href="model.stl">STL</a><a href="'+editable+'">Editable source</a><a href="geometry.json">Geometry report</a><a href="manifest.json">Manifest</a></p><main>'+cards+'</main>'
        (out/'index.html').write_text(page)
        r['delivery']={'folder':str(out.relative_to(job)),'artifacts':_files(out,job)};save(job,data,'delivery_created')
        return {'status':r['state'],'delivery':str(out),'preview':str(out/'index.html'),'studio_file':str(out/'model.stl')}


def status(job):
    with locked(job) as (job,data):
        if not data['current']:return {'status':'INPUT_SAVED'}
        folder,r=revision(job,data)
        try:integrity(data,job)
        except ValueError as exc:return {'status':'INTEGRITY_ERROR','error':str(exc),'revision':data['current']}
        return {'status':r['state'],'revision':data['current'],'folder':str(folder),'physical_print_started':False,'error':r.get('error')}


def open_studio(job):
    with locked(job) as (job,data):
        folder,r=revision(job,data);integrity(data,job)
        if r['state']!='MODEL_READY' or 'delivery' not in r:raise ValueError('A verified delivery is required.')
        file=job/r['delivery']['folder']/'model.stl'
        executable=Path(settings()['studio'])
        if not executable.is_file():raise ValueError('Bambu Studio not found; configure studio or import '+str(file)+' manually.')
        if sys.platform!='darwin':raise ValueError('Automatic app opening is currently supported on macOS. Import '+str(file)+' manually.')
        subprocess.run(['/usr/bin/open','-a',str(executable.parents[2]),str(file)],check=True)
        receipt={'requested_file':str(file),'sha256':sha(file),'requested_at':now(),'status':'OPEN_REQUESTED','ui_import_verified':False,'physical_print_started':False}
        write(folder/'studio-open.json',receipt)
        return dict(receipt,note='Open request sent. Observe Studio to confirm import. No slicing or print command exists.')
