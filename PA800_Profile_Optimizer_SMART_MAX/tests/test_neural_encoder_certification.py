from tools.run_neural_encoder_certification import certify

def test_neural_encoder_certification(tmp_path):
    report=certify(tmp_path/'model.json');assert report['pass'] and report['trained_model'] and not report['production_ready'];assert report['transposition_cosine']>=.999999 and all(report['checks'].values());assert report['mutations']==0 and report['authority_granted'] is False