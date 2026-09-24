import json
from pathlib import Path
import unittest
from unittest.mock import patch
from vt import pipeline
from vt.store import read,write,artifact
import test_fail_closed

class DeliveryTests(unittest.TestCase):
    setUp=test_fail_closed.FailureTests.setUp
    boards=test_fail_closed.FailureTests.boards
    concept_ok=test_fail_closed.FailureTests.concept_ok
    fake_model=test_fail_closed.FailureTests.fake_model

    def ready(self):
        self.fake_model();d=read(self.job/'project.json');r=d['revisions']['r001'];folder=self.job/r['model']['folder']
        source=folder/'model.blend';source.write_bytes(b'editable fixture')
        r['model']['editable']=artifact(source,self.job);r['model']['artifacts']['model.blend']=artifact(source,self.job)
        (folder/'views').mkdir()
        for name in pipeline.VIEWS:(folder/'views'/(name+'.png')).write_bytes(b'view fixture')
        geo=self.job/'revisions/r001/geometry.json';write(geo,{'status':'GEOMETRY_CHECKED','dimensions_mm':[30,30,50],'advisories':['Inspect overhangs in Studio.']})
        r['geometry']={'report':artifact(geo,self.job),'artifacts':{'report':artifact(geo,self.job)}};write(self.job/'project.json',d)
        review=self.root/'final.json';write(review,{'reviewer':'codex','model_sha256':r['model']['stl']['sha256'],'geometry_report_sha256':r['geometry']['report']['sha256'],'observations':['Fixture tests state management only.'],'checks':dict.fromkeys(['silhouette','side_back_volume','meaning_preserved','lettering','resting_surface'],True)})
        return review

    def test_deliver_without_any_slice_and_keep_advisories(self):
        review=self.ready();pipeline.review(self.job,review);result=pipeline.deliver(self.job)
        out=Path(result['delivery']);self.assertTrue((out/'model.stl').is_file());self.assertFalse((out/'print.3mf').exists())
        manifest=read(out/'manifest.json');self.assertEqual(manifest['status'],'MODEL_READY');self.assertTrue(manifest['advisories']);self.assertFalse(manifest['physical_print_started'])

    def test_studio_opens_stl_only_and_does_not_claim_ui_verified(self):
        review=self.ready();pipeline.review(self.job,review);pipeline.deliver(self.job)
        with patch('vt.pipeline.settings',return_value={'studio':str(self.root/'Bambu.app/Contents/MacOS/Bambu')}),patch('vt.pipeline.sys.platform','darwin'),patch('vt.pipeline.subprocess.run') as run:
            file=self.root/'Bambu.app/Contents/MacOS/Bambu';file.parent.mkdir(parents=True);file.write_text('fixture')
            result=pipeline.open_studio(self.job)
            args=run.call_args.args[0];self.assertEqual(args[:3],['/usr/bin/open','-a',str(self.root/'Bambu.app')]);self.assertTrue(args[-1].endswith('/model.stl'));self.assertEqual(len(args),4)
            self.assertFalse(result['physical_print_started']);self.assertFalse(result['ui_import_verified'])

    def test_wrong_model_review_blocked(self):
        review=self.ready();r=read(review);r['model_sha256']='stale';write(review,r)
        with self.assertRaises(ValueError):pipeline.review(self.job,review)
        with self.assertRaises(ValueError):pipeline.deliver(self.job)

if __name__=='__main__':unittest.main()
