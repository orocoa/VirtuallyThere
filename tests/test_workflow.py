import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from vt import pipeline
from vt.store import init,add_brief,read,write,artifact,sha,integrity
from vt.prompts import prompts

class WorkflowTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name);self.job=self.root/'job'
        text=self.root/'story.txt';text.write_text('原文\n$() is text, never a command')
        init(self.job,text,[])
        b=self.root/'brief.json';write(b,{'title':'test','meaning':'remember','form':'one solid','invariants':['one'],'omissions':[],'dimensions_mm':[40,30,50],'lettering':None});add_brief(self.job,b)
        self.brief=b
    def boards(self):
        for name,views in [('a','front,right,back'),('b','top,bottom,three-quarter')]:
            f=self.root/(name+'.png');f.write_bytes(name.encode());pipeline.concept(self.job,f,views)
    def concept_ok(self):
        self.boards();d=read(self.job/'project.json');r=d['revisions']['r001']
        p=self.root/'review.json';write(p,{'concept_sha256':[x['artifact']['sha256'] for x in r['concepts']], 'reviewer':'codex','observations':['same object'],'direction_reason':'one coherent volume','checks':dict.fromkeys(['same_object','connections_consistent','voids_consistent','lettering_consistent','single_material_feasible'],True)})
        pipeline.concept_review(self.job,p)
    def test_original_is_snapshotted(self):
        d=read(self.job/'project.json');self.assertEqual((self.job/d['sources'][0]['path']).read_text(),'原文\n$() is text, never a command')
    def test_init_refuses_existing_directory(self):
        with self.assertRaises(ValueError):init(self.job,self.root/'story.txt',[])
    def test_prompt_generation_idempotent(self):
        self.assertEqual(prompts(self.job),prompts(self.job))
    def test_single_view_rejected(self):
        p=self.root/'a.png';p.write_bytes(b'x')
        with self.assertRaises(ValueError):pipeline.concept(self.job,p,'front')
    def test_incomplete_views_block_review(self):
        p=self.root/'a.png';p.write_bytes(b'x');pipeline.concept(self.job,p,'front,right,back')
        f=self.root/'r.json';write(f,{})
        with self.assertRaises(ValueError):pipeline.concept_review(self.job,f)
    def test_model_requires_concept_review(self):
        with self.assertRaises(ValueError):pipeline.model(self.job,script=self.brief)
    def test_locked_concept_cannot_be_mutated(self):
        self.concept_ok()
        with self.assertRaises(ValueError):pipeline.concept(self.job,self.root/'a.png','front,right')
    def test_revised_brief_does_not_inherit_ready(self):
        self.concept_ok();add_brief(self.job,self.brief)
        self.assertEqual(pipeline.status(self.job)['status'],'DESIGN_DEFINED')
        self.assertTrue(bool(list((self.job/'revisions/r001').glob('concept-review-*.json'))))
    def test_source_tampering_blocks(self):
        d=read(self.job/'project.json');(self.job/d['sources'][0]['path']).write_text('changed')
        self.assertEqual(pipeline.status(self.job)['status'],'INTEGRITY_ERROR')
    def test_delivery_before_checks_refused(self):
        with self.assertRaises(ValueError):pipeline.deliver(self.job)
    def test_open_before_ready_never_launches(self):
        with patch('vt.pipeline.subprocess.run') as run:
            with self.assertRaises(ValueError):pipeline.open_studio(self.job)
            run.assert_not_called()
    def test_path_escape_refused(self):
        d=read(self.job/'project.json');d['sources'][0]={'path':'../story.txt','sha256':sha(self.root/'story.txt')};write(self.job/'project.json',d)
        self.assertEqual(pipeline.status(self.job)['status'],'INTEGRITY_ERROR')
    def test_failed_worker_creates_no_model_success(self):
        self.concept_ok()
        with patch('vt.pipeline._worker',return_value=2):
            with self.assertRaises(ValueError):pipeline.model(self.job,script=self.brief)
        self.assertEqual(pipeline.status(self.job)['status'],'NEEDS_REPAIR')
        with patch('vt.pipeline._worker',return_value=2):
            with self.assertRaises(ValueError):pipeline.model(self.job,script=self.brief)
        self.assertEqual(len(list((self.job/'revisions/r001').glob('model-*'))),2)
    def test_incomplete_successful_export_is_rejected(self):
        self.concept_ok()
        def incomplete(command,folder,timeout):
            (folder/'model.stl').write_bytes(b'partial export')
            return 0
        with patch('vt.pipeline._worker',side_effect=incomplete):
            with self.assertRaises(ValueError):pipeline.model(self.job,script=self.brief)
        self.assertEqual(pipeline.status(self.job)['status'],'NEEDS_REPAIR')
        self.assertNotIn('model',read(self.job/'project.json')['revisions']['r001'])

    def test_duplicate_boards_rejected(self):
        p=self.root/'a.png';p.write_bytes(b'same')
        pipeline.concept(self.job,p,'front,right,back');pipeline.concept(self.job,p,'top,bottom,three-quarter')
        q=self.root/'q.json';write(q,{})
        with self.assertRaises(ValueError):pipeline.concept_review(self.job,q)

if __name__=='__main__':unittest.main()
