from tools.instrument_family_holdout import evaluate


def test_grouped_holdout_uses_disjoint_folds_and_never_grants_authority():
    data={'profiles':[{'identity':{'org_family':'PIANO','msb':1,'lsb':2,'program':3,'sound':'Piano','role':'SONG'},'support':{'styles':12},'stability':'STABLE','folds':[{'v_p50':80},{'v_p50':82},{'v_p50':81}]}]}
    result=evaluate(data);row=result['rows'][0]
    assert result['grouping'].startswith('disjoint Factory Style') and result['authority_granted'] is False
    assert row['proxy_pass'] and row['median_error']==1.5
    assert result['families']['PIANO']['proxy_pass']==1


def test_context_dependent_profile_cannot_pass_positive_model_proxy():
    data={'profiles':[{'identity':{'org_family':'GUITAR','msb':1,'lsb':2,'program':3},'support':{'styles':9},'stability':'CONTEXT_DEPENDENT','folds':[{'v_p50':60},{'v_p50':61},{'v_p50':60}]}]}
    result=evaluate(data)
    assert not result['rows'][0]['proxy_pass']


def test_phrase_family_profile_can_pass_without_granting_hardware_authority():
    data={'profiles':[{'identity':{'org_family':'ENSEMBLE','msb':121,'lsb':2,'program':50,'sound':'Analog Strings 2'},'support':{'styles':34},'stability':'STABLE','folds':[{'v_p50':78},{'v_p50':78},{'v_p50':74}]}]}
    result=evaluate(data);row=result['rows'][0]
    assert row['proxy_pass'] and row['max_error']==4.0
    assert result['families']['ENSEMBLE']['proxy_pass']==1
    assert result['authority_granted'] is False