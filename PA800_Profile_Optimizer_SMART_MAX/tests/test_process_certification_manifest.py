from pa800_optimizer.analysis.process_certification import PROCESS_STAGES,evaluate_process_coverage


def test_process_matrix_contains_every_a_to_z_stage_once():
    assert ''.join(row['stage'] for row in PROCESS_STAGES)=='ABCDEFGHIJKLMNOPQRSTUVWXYZ'
    assert all(row['positive_tests'] and row['negative_tests'] for row in PROCESS_STAGES)


def test_process_coverage_requires_both_fixture_polarities_and_registered_tests():
    nodeids=[node for stage in PROCESS_STAGES for key in ('positive_tests','negative_tests') for node in stage[key]]
    fixtures={'scenarios':[{'stage':stage['stage'],'polarity':polarity,'file':'x.mid'} for stage in PROCESS_STAGES for polarity in ('positive','negative')]}
    assert evaluate_process_coverage(nodeids,fixtures)['pass']
    fixtures['scenarios'].pop();result=evaluate_process_coverage(nodeids,fixtures)
    assert not result['pass'] and result['stages'][-1]['missing_fixture_polarities']==['negative']