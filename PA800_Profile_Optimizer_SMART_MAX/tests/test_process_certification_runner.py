import json

from pa800_optimizer.analysis.process_certification import PROCESS_STAGES,evaluate_process_coverage
from tools.process_certification_midis import generate


def test_generated_pack_closes_every_a_to_z_stage(tmp_path):
    rows=generate(tmp_path);manifest=json.loads((tmp_path/'PROCESS_CERTIFICATION_MANIFEST.json').read_text(encoding='utf-8'))
    nodeids=[node for stage in PROCESS_STAGES for kind in ('positive_tests','negative_tests') for node in stage[kind]]
    result=evaluate_process_coverage(nodeids,manifest)
    assert len(rows)==52 and result['pass'] and result['passed_stages']==26

def test_structural_only_process_certification_does_not_require_release_evidence(tmp_path):
    from tools.run_process_certification import certify
    report=certify(tmp_path/'structural',run_regression=False)
    assert report['pass']
    assert report['release_audit'].get('skipped') is True
