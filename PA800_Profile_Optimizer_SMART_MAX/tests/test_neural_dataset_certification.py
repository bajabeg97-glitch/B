from tools.run_neural_dataset_certification import certify

def test_neural_dataset_v2_certification(tmp_path):
    report=certify(tmp_path/'certification')
    assert report['pass'] and report['roundtrip_passed']==14
    assert report['dataset_cases']>=50 and report['hard_negatives']>=20
    assert all(report['checks'].values()) and set(report['corruption_types'])=={'ONSET_SPIKE','GATE_TRUNCATE','GATE_OVERLAP','DUPLICATE_HIT','CHORD_DESYNC','GROOVE_DRIFT'}
    assert report['mutations_to_original_sources']==0 and report['authority_granted'] is False and report['trained_model'] is False