from tools.rare_family_evidence import evaluate


def test_real_rare_family_evidence_closes_without_auto_authority():
    result=evaluate()
    assert result['status']=='CLOSED_PRESERVE_NO_ELIGIBLE_PROFILE'
    assert result['eligible_auto_profiles']==[] and result['authority_granted'] is False
    assert all(result['exact_only_policy_checks'].values())
    assert all(result['permanent_preserve_checks'].values())


def test_eligible_synthetic_profile_reopens_review_but_never_grants_authority():
    sounds={'profiles':[{'identity':{'org_family':'ETHNIC','msb':1,'lsb':2,'program':3,'sound':'Test'},'support':{'grade':'GOOD','styles':12,'notes':500}}]}
    stability={'profiles':[{'identity':{'msb':1,'lsb':2,'program':3,'sound':'Test'},'stability':'STABLE'}]}
    result=evaluate(sounds,stability)
    assert result['status']=='OPEN_REVIEW_REQUIRED'
    assert len(result['eligible_auto_profiles'])==1
    assert result['authority_granted'] is False