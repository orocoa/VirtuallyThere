import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from vt import pipeline
from vt.store import init,add_brief,read,write,artifact,revise_model
import test_workflow

class FailureTests(unittest.TestCase):
    setUp = test_workflow.WorkflowTests.setUp
    boards = test_workflow.WorkflowTests.boards
    concept_ok = test_workflow.WorkflowTests.concept_ok
    def fake_model(self):
        self.concept_ok();d=read(self.job/'project.json');r=d['revisions']['r001']
        out=self.job/'revisions/r001/model-fixture';out.mkdir();m=out/'model.stl';m.write_bytes(b'mesh fixture')
        item=artifact(m,self.job);r['model']={'artifacts':{'model.stl':item},'stl':item,'editable':item,'folder':str(out.relative_to(self.job))};r['state']='MODEL_EXPORTED';write(self.job/'project.json',d)
    def test_false_success_worker_rejected(self):
        self.fake_model()
        def worker(command,folder,timeout):
            write(folder/'report.json',{'status':'GEOMETRY_CHECKED','hard_checks':{'closed':False}});return 2
        with patch('vt.pipeline._worker',side_effect=worker):result=pipeline.check(self.job)
        self.assertEqual(result['status'],'NEEDS_REPAIR')
        with self.assertRaises(ValueError):pipeline.deliver(self.job)
    def test_model_revision_preserves_concept_not_results(self):
        self.fake_model();result=revise_model(self.job);self.assertEqual(result['status'],'CONCEPT_READY')
        d=read(self.job/'project.json');self.assertNotIn('model',d['revisions'][d['current']]);self.assertEqual(len(d['revisions'][d['current']]['concepts']),2)
        self.assertIn('model',d['revisions']['r001'])
    def test_orphan_brief_does_not_block_new_revision(self):
        orphan=self.job/'revisions/r002';orphan.mkdir();(orphan/'brief.json').write_text('interrupted')
        result=add_brief(self.job,self.brief);self.assertEqual(result['revision'],'r003')

if __name__=='__main__':unittest.main()
