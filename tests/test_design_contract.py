import contextlib
import io
from pathlib import Path
import tempfile
import unittest

from vt import cli, pipeline
from vt.prompts import prompts
from vt.store import add_brief, artifact, check_brief, init, read, revise_model, sha, write


class DesignContractTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.job = self.root / 'job'
        story = self.root / 'story.txt'
        story.write_text('拐过弯，视野突然开阔。', encoding='utf-8')
        photo = self.root / 'photo.png'
        photo.write_bytes(b'image fixture')
        init(self.job, story, [photo])
        self.file = self.root / 'brief.json'
        self.brief = {'title': '弯', 'meaning': '记住视野变化', 'form': '开放弧形体',
                      'invariants': ['开口保持开放'], 'omissions': [], 'dimensions_mm': [60, 45, 40],
                      'design_contract': {
                          'source_cues': [{'source': 'sources/00-story.txt', 'evidence': '视野突然开阔'}],
                          'interpretation': '开口从狭窄走向开阔是设计解释。',
                          'parameters': {'gap_mm': 12, 'arc_deg': 240}}}

    def add(self, brief=None):
        write(self.file, self.brief if brief is None else brief)
        return add_brief(self.job, self.file)

    def accepted(self):
        self.add()
        for name, views in [('a', 'front,right,back'), ('b', 'top,bottom,three-quarter')]:
            image = self.root / (name + '.png')
            image.write_bytes(name.encode())
            pipeline.concept(self.job, image, views)
        r = read(self.job / 'project.json')['revisions']['r001']
        record = self.root / 'concept-review.json'
        write(record, {'concept_sha256': [x['artifact']['sha256'] for x in r['concepts']],
                       'reviewer': 'codex', 'observations': ['same open form'], 'direction_reason': 'opening',
                       'checks': dict.fromkeys(['same_object', 'connections_consistent', 'voids_consistent',
                                               'lettering_consistent', 'single_material_feasible'], True)})
        pipeline.concept_review(self.job, record)

    def test_legacy_brief_and_revision_remain_supported(self):
        del self.brief['design_contract']
        self.accepted()
        self.assertEqual(revise_model(self.job)['status'], 'CONCEPT_READY')

    def test_unknown_source_and_invented_quote_leave_no_revision(self):
        for cue in [{'source': '../story.txt', 'evidence': '拐过弯'},
                    {'source': 'sources/00-story.txt', 'evidence': '咖啡店'}]:
            with self.subTest(cue=cue):
                self.brief['design_contract']['source_cues'] = [cue]
                with self.assertRaises(ValueError): self.add()
                self.assertIsNone(read(self.job / 'project.json')['current'])
                self.assertFalse((self.job / 'revisions').exists())

    def test_contract_rejects_invalid_structure_and_types(self):
        valid = self.brief['design_contract']
        invalid = [None, {}, {**valid, 'extra': True}, {**valid, 'source_cues': []},
                   {**valid, 'source_cues': [{'source': 'x', 'evidence': 'y', 'extra': 1}]},
                   {**valid, 'interpretation': ' '}, {**valid, 'parameters': []}]
        invalid += [{**valid, 'parameters': {'gap_mm': value}} for value in (True, '12', None, float('nan'), float('inf'))]
        invalid += [{**valid, 'parameters': {'bad-name': 12}}]
        for contract in invalid:
            with self.subTest(contract=contract):
                candidate = {**self.brief, 'design_contract': contract}
                with self.assertRaises(ValueError): check_brief(candidate)
        for invariants in [[''], ['same', 'same']]:
            with self.assertRaises(ValueError): check_brief({**self.brief, 'invariants': invariants})

    def test_empty_parameters_and_image_observation_supported(self):
        self.brief['design_contract']['parameters'] = {}
        self.brief['design_contract']['source_cues'] = [{'source': 'sources/01-photo.png', 'evidence': '两条弧线相接'}]
        self.assertEqual(self.add()['revision'], 'r001')

    def test_requested_color_reaches_both_prompt_boards(self):
        self.brief['color'] = 'black'
        self.add()
        for path in prompts(self.job)['prompts'].values():
            self.assertIn('matte black material', Path(path).read_text())
            self.assertNotIn('matte white material', Path(path).read_text())
        with self.assertRaises(ValueError):
            check_brief({**self.brief, 'color': 'red'})

    def test_tampered_source_blocks_new_brief(self):
        (self.job / 'sources/00-story.txt').write_text('改变的原文')
        with self.assertRaises(ValueError): self.add()
        self.assertFalse((self.job / 'revisions').exists())

    def test_parameter_revision_updates_shared_brief_and_discards_results(self):
        self.accepted()
        old = self.job / 'revisions/r001/brief.json'
        old_sha = sha(old)
        data = read(self.job / 'project.json')
        r = data['revisions']['r001']
        dummy = self.job / 'revisions/r001/model.stl'
        dummy.write_bytes(b'fixture')
        for section in ('model', 'geometry', 'delivery'):
            r[section] = {'artifacts': {'fixture': artifact(dummy, self.job)}}
        r['model_review'] = {'record': artifact(dummy, self.job)}
        write(self.job / 'project.json', data)
        result = revise_model(self.job, {'gap_mm': 16})
        current = read(self.job / 'project.json')['revisions'][result['revision']]
        self.assertEqual(sha(old), old_sha)
        self.assertEqual(read(old)['design_contract']['parameters']['gap_mm'], 12)
        revised = read(self.job / current['brief']['path'])
        self.assertEqual(revised['design_contract']['parameters'], {'gap_mm': 16, 'arc_deg': 240})
        self.assertEqual(current['parameter_changes'], {'gap_mm': {'from': 12, 'to': 16}})
        self.assertEqual(current['derived_from'], 'r001')
        self.assertIn('prior design', current['concept_reference'])
        self.assertEqual(len(current['concepts']), 2)
        for section in ('model', 'geometry', 'delivery', 'model_review'):
            self.assertNotIn(section, current)
        for path in prompts(self.job)['prompts'].values():
            self.assertIn('"gap_mm": 16', Path(path).read_text())

    def test_invalid_parameter_patch_leaves_project_untouched(self):
        self.accepted()
        before = (self.job / 'project.json').read_bytes()
        for parameters in ({'unknown_mm': 1}, {'gap_mm': True}, {'gap_mm': float('nan')}, []):
            with self.subTest(parameters=parameters):
                with self.assertRaises(ValueError): revise_model(self.job, parameters)
                self.assertEqual((self.job / 'project.json').read_bytes(), before)
                self.assertFalse((self.job / 'revisions/r002').exists())

    def test_cli_reads_parameter_file(self):
        self.accepted()
        parameters = self.root / 'parameters.json'
        write(parameters, {'gap_mm': 18})
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(cli.main(['revise-model', str(self.job), '--parameters', str(parameters)]), 0)
        self.assertEqual(read(self.job / 'revisions/r002/brief.json')['design_contract']['parameters']['gap_mm'], 18)

    def test_cli_null_patch_is_rejected_without_revision(self):
        self.accepted()
        parameters = self.root / 'parameters.json'
        write(parameters, None)
        with contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(cli.main(['revise-model', str(self.job), '--parameters', str(parameters)]), 2)
        self.assertEqual(read(self.job / 'project.json')['current'], 'r001')


if __name__ == '__main__':
    unittest.main()
