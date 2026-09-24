import contextlib
import fcntl
import hashlib
import json
import math
import os
from pathlib import Path
import re
import shutil
from datetime import datetime, timezone

VIEWS = {'front', 'right', 'back', 'top', 'bottom', 'three-quarter'}


def read(path):
    return json.loads(Path(path).read_text())


def write(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + '.tmp')
    temp.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')
    os.replace(temp, path)


def sha(path):
    with Path(path).open('rb') as stream:
        h = hashlib.sha256()
        for chunk in iter(lambda: stream.read(1024 * 1024), b''): h.update(chunk)
        return h.hexdigest()


def artifact(path, root):
    path, root = Path(path).resolve(), Path(root).resolve()
    return {'path': str(path.relative_to(root)), 'sha256': sha(path)}


def verify(item, root):
    root = Path(root).resolve()
    path = (root / item['path']).resolve()
    if not path.is_relative_to(root) or not path.is_file() or sha(path) != item['sha256']:
        raise ValueError('Artifact missing or changed: ' + item['path'])
    return path


def snapshot(source, target):
    source, target = Path(source).resolve(), Path(target)
    if not source.is_file():
        raise ValueError('Missing input: ' + str(source))
    target.parent.mkdir(parents=True, exist_ok=True)
    with source.open('rb') as src, target.open('xb') as dst:
        shutil.copyfileobj(src, dst)
    return target


def now():
    return datetime.now(timezone.utc).isoformat()


@contextlib.contextmanager
def locked(job):
    job = Path(job).resolve()
    if not (job / 'project.json').is_file():
        raise ValueError('Not a project: ' + str(job))
    with (job / '.lock').open('a') as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise ValueError('Another operation owns this project; retry after it finishes.')
        yield job, read(job / 'project.json')


def save(job, data, event):
    data['updated_at'] = now()
    write(job / 'project.json', data)
    with (job / 'events.jsonl').open('a') as f:
        f.write(json.dumps({'at': now(), 'event': event, 'revision': data.get('current')}, ensure_ascii=False) + '\n')


def revision(job, data):
    rev = data.get('current')
    if not rev:
        raise ValueError('Create a brief first.')
    return job / 'revisions' / rev, data['revisions'][rev]


def check_brief(b):
    if not isinstance(b, dict):
        raise ValueError('Brief must be an object.')
    required = ('title', 'meaning', 'form', 'invariants', 'omissions', 'dimensions_mm')
    if any(k not in b for k in required):
        raise ValueError('Brief needs: ' + ', '.join(required))
    if any(not isinstance(b[k], str) or not b[k].strip() for k in ('title', 'meaning', 'form')):
        raise ValueError('Title, meaning and form must be nonempty text.')
    if any(not isinstance(b[k], list) or any(not isinstance(x, str) for x in b[k]) for k in ('invariants', 'omissions')):
        raise ValueError('Invariants/omissions must be text lists.')
    if not b['invariants']:
        raise ValueError('At least one form invariant is needed.')
    dims = b['dimensions_mm']
    if not isinstance(dims, list) or len(dims) != 3 or any(type(v) not in (int, float) or not 5 <= v <= 200 for v in dims):
        raise ValueError('Three finite nominal dimensions between 5 and 200 mm required.')
    if b.get('lettering') is not None and (not isinstance(b['lettering'], dict) or not isinstance(b['lettering'].get('text'), str) or not b['lettering']['text'].strip()):
        raise ValueError('Lettering needs exact nonempty text, or null.')
    if 'color' in b and b['color'] not in ('black','white'):
        raise ValueError('Single-material color must be black or white.')
    if 'design_contract' in b:
        check_contract(b['design_contract'])
        if any(not x.strip() for x in b['invariants']) or len(set(b['invariants'])) != len(b['invariants']):
            raise ValueError('Contract invariants must be nonempty and unique.')


def check_parameters(parameters):
    if not isinstance(parameters, dict) or any(
        not isinstance(k, str) or not k.isidentifier() or type(v) not in (int, float) or (type(v) is float and not math.isfinite(v))
        for k, v in parameters.items()
    ):
        raise ValueError('Parameters must map identifier names to finite numbers (not booleans).')


def check_contract(contract, sources=None, job=None):
    if not isinstance(contract, dict) or set(contract) != {'source_cues', 'interpretation', 'parameters'}:
        raise ValueError('Design contract needs exactly source_cues, interpretation and parameters.')
    if not isinstance(contract['interpretation'], str) or not contract['interpretation'].strip():
        raise ValueError('Design interpretation must be nonempty text.')
    check_parameters(contract['parameters'])
    cues = contract['source_cues']
    if not isinstance(cues, list) or not cues:
        raise ValueError('At least one source cue is required.')
    by_path = {item['path']: item for item in sources} if sources is not None else None
    for cue in cues:
        if not isinstance(cue, dict) or set(cue) != {'source', 'evidence'} or any(
            not isinstance(cue[k], str) or not cue[k].strip() for k in ('source', 'evidence')
        ):
            raise ValueError('Each source cue needs exactly nonempty source and evidence text.')
        if by_path is not None:
            item = by_path.get(cue['source'])
            if item is None:
                raise ValueError('Source cue must reference a snapshotted manifest source: ' + cue['source'])
            source = verify(item, job)
            if item['kind'] == 'text':
                try:
                    original = source.read_text(encoding='utf-8')
                except UnicodeDecodeError as exc:
                    raise ValueError('Text source must be UTF-8 for evidence validation.') from exc
                if cue['evidence'] not in original:
                    raise ValueError('Text evidence must quote the source exactly: ' + cue['source'])
            # Image evidence is a visual assertion by the reviewer, not a machine-verified fact.


def init(job, text, images):
    job = Path(job).resolve()
    if job.exists():
        raise ValueError('Project path already exists; existing work is preserved.')
    if not text and not images:
        raise ValueError('Provide text and/or images.')
    for p in ([text] if text else []) + list(images):
        if not Path(p).is_file():
            raise ValueError('Missing input: ' + str(p))
    job.mkdir(parents=True)
    sources = []
    for i, p in enumerate(([text] if text else []) + list(images)):
        safe = re.sub(r'[^\w.\-]', '_', Path(p).name)
        dest = snapshot(p, job / 'sources' / ('%02d-' % i + safe))
        sources.append({**artifact(dest, job), 'kind': 'text' if text and i == 0 else 'image', 'original': str(Path(p).resolve())})
    data = {'schema': 1, 'created_at': now(), 'sources': sources, 'current': None, 'revisions': {}, 'physical_print_started': False}
    save(job, data, 'input_saved')
    return {'job': str(job), 'status': 'INPUT_SAVED', 'next': 'Codex reads sources and writes a brief; then vt brief JOB --file brief.json'}


def add_brief(job, source):
    b = read(source); check_brief(b)
    with locked(job) as (job, data):
        for item in data['sources']: verify(item, job)
        if 'design_contract' in b: check_contract(b['design_contract'], data['sources'], job)
        existing = [int(p.name[1:]) for p in (job/'revisions').glob('r[0-9][0-9][0-9]') if p.is_dir()]
        name = 'r%03d' % (max(existing, default=0) + 1)
        dest = snapshot(source, job / 'revisions' / name / 'brief.json')
        data['current'] = name
        data['revisions'][name] = {'brief': artifact(dest, job), 'concepts': [], 'state': 'DESIGN_DEFINED'}
        save(job, data, 'brief_selected_by_codex')
        return {'revision': name, 'next': 'Generate two consistent multi-angle boards with imagegen, then register them.'}


def integrity(data, job):
    for x in data['sources']: verify(x, job)
    _, r = revision(job, data)
    b = read(verify(r['brief'], job))
    check_brief(b)
    if 'design_contract' in b: check_contract(b['design_contract'], data['sources'], job)
    for x in r['concepts']: verify(x['artifact'], job)
    for section in ('model', 'geometry', 'slice', 'slice_previews', 'delivery'):
        for x in r.get(section, {}).get('artifacts', {}).values(): verify(x, job)
    for section in ('concept_review', 'model_review'):
        if section in r:
            verify(r[section]['record'], job)
            for x in r[section].get('evidence', []): verify(x, job)
    return r


def revise_model(job, parameters=None):
    with locked(job) as (job,data):
        old_folder,r=revision(job,data);integrity(data,job)
        if 'concept_review' not in r:raise ValueError('No accepted concept to preserve.')
        brief = read(verify(r['brief'], job))
        changes = {}
        if parameters is not None:
            check_parameters(parameters)
            if 'design_contract' not in brief:
                raise ValueError('Parameter edits require a design contract; create a new brief first.')
            current = brief['design_contract']['parameters']
            unknown = set(parameters) - set(current)
            if unknown:
                raise ValueError('Only existing parameters can be revised: ' + ', '.join(sorted(unknown)))
            changes = {key: {'from': current[key], 'to': value} for key, value in parameters.items() if current[key] != value}
            current.update(parameters)
            check_brief(brief)
        existing=[int(p.name[1:]) for p in (job/'revisions').glob('r[0-9][0-9][0-9]') if p.is_dir()]
        name='r%03d'%(max(existing,default=0)+1);folder=job/'revisions'/name
        b=folder/'brief.json'
        if changes: write(b, brief)
        else: snapshot(verify(r['brief'],job),b)
        concepts=[]
        for i,item in enumerate(r['concepts']):
            p=snapshot(verify(item['artifact'],job),folder/'concept'/('%02d'%i+Path(item['artifact']['path']).suffix))
            concepts.append({'artifact':artifact(p,job),'views':item['views']})
        p=snapshot(verify(r['concept_review']['record'],job),folder/'concept-review-inherited.json')
        new={'brief':artifact(b,job),'concepts':concepts,'concept_review':{'record':artifact(p,job)},'state':'CONCEPT_READY','derived_from':data['current']}
        if changes:
            new['parameter_changes'] = changes
            new['concept_reference'] = 'Inherited boards approximate the prior design; they do not verify revised parameter values. Check the current brief against new model views.'
        data['revisions'][name]=new;data['current']=name;save(job,data,'model_revision_preserving_concept')
        return {'revision':name,'status':'CONCEPT_READY','parameter_changes':changes,'next':'Model again from the current brief. Inherited boards are prior-design references; validate revised parameters in new model views. Prior geometry and delivery states remain only in the prior revision.'}
