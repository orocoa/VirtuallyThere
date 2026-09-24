"""New contracts must remain visible at the final delivery gate."""
from pathlib import Path
import tempfile
import unittest

from vt import pipeline
from vt.store import add_brief, init, read, write
import test_delivery


class DesignReviewTests(unittest.TestCase):
    boards = test_delivery.DeliveryTests.boards
    concept_ok = test_delivery.DeliveryTests.concept_ok
    fake_model = test_delivery.DeliveryTests.fake_model

    def ready(self):
        path = test_delivery.DeliveryTests.ready(self)
        record = read(path)
        record['brief_sha256'] = read(self.job / 'project.json')['revisions']['r001']['brief']['sha256']
        write(path, record)
        return path

    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.job = self.root / 'job'
        story = self.root / 'story.txt'
        story.write_text('The path opened toward the sea.')
        init(self.job, story, [])
        self.brief = self.root / 'brief.json'
        write(self.brief, {
            'title': 'Test', 'meaning': 'An opening', 'form': 'An open curved band',
            'invariants': ['One continuous body', 'An open front'],
            'omissions': [], 'dimensions_mm': [60, 50, 40],
            'design_contract': {
                'source_cues': [{'source': 'sources/00-story.txt', 'evidence': 'opened toward the sea'}],
                'interpretation': 'A widening view suggested by an open form.',
                'parameters': {'height_mm': 40},
            },
        })
        add_brief(self.job, self.brief)

    def evidence(self):
        return [
            {'invariant': 'One continuous body', 'views': ['back', 'three-quarter'],
             'observation': 'The outer band has no separate pieces.', 'passed': True},
            {'invariant': 'An open front', 'views': ['front', 'top'],
             'observation': 'The two ends leave an unfilled front opening.', 'passed': True},
        ]

    def test_generic_pass_flags_cannot_bypass_contract(self):
        review = self.ready()
        with self.assertRaises(ValueError):
            pipeline.review(self.job, review)
        with self.assertRaises(ValueError):
            pipeline.deliver(self.job)

    def test_unresolved_or_unobserved_invariant_blocks_delivery(self):
        review = self.ready()
        record = read(review)
        invalid = [self.evidence()[:1], self.evidence(), self.evidence(), self.evidence()]
        invalid[1][1]['passed'] = False
        invalid[2][1]['views'] = ['imagined']
        invalid[3][1]['observation'] = ' '
        for checks in invalid:
            with self.subTest(checks=checks):
                record['invariant_checks'] = checks
                write(review, record)
                with self.assertRaises(ValueError):
                    pipeline.review(self.job, review)
                self.assertNotEqual(pipeline.status(self.job)['status'], 'MODEL_READY')

    def test_matching_observations_allow_same_version_delivery(self):
        review = self.ready()
        record = read(review)
        record['brief_sha256'] = read(self.job / 'project.json')['revisions']['r001']['brief']['sha256']
        record['invariant_checks'] = self.evidence()
        write(review, record)
        self.assertEqual(pipeline.review(self.job, review)['status'], 'MODEL_READY')
        result = pipeline.deliver(self.job)
        self.assertTrue((Path(result['delivery']) / 'model.stl').is_file())

    def test_stale_brief_cannot_reuse_model_approval(self):
        review = self.ready()
        record = read(review)
        record['invariant_checks'] = self.evidence()
        record['brief_sha256'] = 'previous-brief-hash'
        write(review, record)
        with self.assertRaisesRegex(ValueError, 'current brief'):
            pipeline.review(self.job, review)
        with self.assertRaises(ValueError):
            pipeline.deliver(self.job)


if __name__ == '__main__':
    unittest.main()
