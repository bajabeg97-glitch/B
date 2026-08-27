from tools.run_instrument_profile_certification import certify

def test_instrument_profile_certification(tmp_path):
    report=certify(tmp_path/'result.json');assert report['pass'] and report['profiles']==565 and report['exact_resolved']==565 and report['families']==18;assert report['manual_only_profiles']==23 and report['production_auto_profiles']==0;assert all(report['checks'].values()) and report['authority_granted'] is False