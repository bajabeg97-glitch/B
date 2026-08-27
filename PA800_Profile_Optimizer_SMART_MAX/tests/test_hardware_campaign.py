from pa800_optimizer.analysis.hardware_campaign import MAJOR_FX_ROLES,MAJOR_VOICE_FAMILIES,campaign_template,evaluate_hardware_campaign


def passing_campaign():
    data=campaign_template();data['device'].update({'os_version':'2.03','musical_resources_version':'2.03','set_id':'FACTORY','audio_chain_id':'LINE_OUT_24BIT'})
    for family in MAJOR_VOICE_FAMILIES:
        for index in range(30):data['records'].append({'kind':'voice','family':family,'top1_correct':True,'top3_correct':True,'false_positive':False,'preference':'same'})
    for role in MAJOR_FX_ROLES:
        for index in range(30):data['records'].append({'kind':'fx','role':role,'preference':'same','mud_failure':False})
    for index in range(23):data['records'].append({'kind':'dnc','address':'121.18.%d'%index,'status':'PASS'})
    return data


def test_complete_hardware_campaign_passes_all_roadmap_gates():
    result=evaluate_hardware_campaign(passing_campaign())
    assert result['pass'];assert all(row['auto_eligible'] for row in result['voice_families']);assert result['dnc']['unique_addresses']==23


def test_critical_playback_failure_blocks_campaign_even_with_good_scores():
    data=passing_campaign();data['records'][0]['stuck_note']=True
    result=evaluate_hardware_campaign(data)
    assert not result['pass'] and not result['gates']['no_critical_playback_failures']


def test_empty_campaign_is_infrastructure_not_evidence():
    result=evaluate_hardware_campaign(campaign_template())
    assert not result['pass'];assert not result['gates']['device_identity_complete'];assert not result['gates']['voice_family_quotas_complete']