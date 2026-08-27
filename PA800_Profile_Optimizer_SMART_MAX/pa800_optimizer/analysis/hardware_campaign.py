"""Evaluate physical Pa800 A/B evidence without granting authority prematurely."""
from __future__ import annotations

from collections import Counter,defaultdict

MAJOR_VOICE_FAMILIES=('PIANO','BASS','GUITAR','STRINGS','BRASS','REED','ORGAN')
MAJOR_FX_ROLES=('FOUNDATION_DRUM','FOUNDATION_BASS','LEAD','HARMONIC_COMP','PAD_BACKGROUND')
CRITICAL_FLAGS=('stuck_note','wrong_program','lost_articulation','playback_error')


def campaign_template():
    return {'schema':'PA800_HARDWARE_CAMPAIGN_V1','device':{'model':'Pa800','os_version':'','musical_resources_version':'','set_id':'','audio_chain_id':''},'protocol':{'strict_case_ids':False,'blinded_ab':True,'same_mixer_master_audio_chain':True},'requirements':{'voice_trials_per_major_family':30,'fx_trials_per_major_role':30,'manual_dnc_addresses':23,'voice_top1_min':.85,'voice_false_positive_max_exclusive':.02,'better_or_equal_min':.90},'records':[]}


def evaluate_hardware_campaign(data):
    records=list((data or {}).get('records') or []);errors=[];voice=defaultdict(list);fx=defaultdict(list);dnc=[];critical=[]
    if (data or {}).get('schema')!='PA800_HARDWARE_CAMPAIGN_V1':errors.append('invalid_schema')
    strict=bool(((data or {}).get('protocol') or {}).get('strict_case_ids'));case_ids=[]
    device=(data or {}).get('device') or {}
    for field in ('os_version','musical_resources_version','set_id','audio_chain_id'):
        if not str(device.get(field,'')).strip():errors.append('missing_device_'+field)
    for index,row in enumerate(records):
        if strict:
            case_id=str(row.get('case_id','')).strip();case_ids.append(case_id)
            if not case_id:errors.append('record_%d_missing_case_id'%index)
            if str(row.get('blind_order','')).upper() not in ('A_REFERENCE_B_OPTIMIZED','A_OPTIMIZED_B_REFERENCE'):errors.append('record_%d_invalid_blind_order'%index)
            for field in ('operator','session_utc','input_midi_sha256','reference_output_sha256','optimized_output_sha256'):
                if not str(row.get(field,'')).strip():errors.append('record_%d_missing_%s'%(index,field))
        kind=str(row.get('kind','')).lower()
        if kind=='voice':voice[str(row.get('family','UNKNOWN')).upper()].append(row)
        elif kind=='fx':fx[str(row.get('role','UNKNOWN')).upper()].append(row)
        elif kind=='dnc':dnc.append(row)
        else:errors.append('record_%d_invalid_kind'%index);continue
        if any(bool(row.get(flag)) for flag in CRITICAL_FLAGS):critical.append(index)
    if strict and len(case_ids)!=len(set(case_ids)):errors.append('duplicate_case_id')
    voice_rows=[]
    for family in MAJOR_VOICE_FAMILIES:
        rows=voice.get(family,[]);n=len(rows);top1=sum(bool(row.get('top1_correct')) for row in rows)/max(1,n);top3=sum(bool(row.get('top3_correct')) for row in rows)/max(1,n);false_positive=sum(bool(row.get('false_positive')) for row in rows)/max(1,n);better_equal=sum(str(row.get('preference','')).lower() in ('optimized','same') for row in rows)/max(1,n);eligible=n>=30 and top1>=.85 and false_positive<.02 and better_equal>=.90 and not any(any(bool(row.get(flag)) for flag in CRITICAL_FLAGS) for row in rows)
        voice_rows.append({'family':family,'trials':n,'top1_accuracy':round(top1,4),'top3_accuracy':round(top3,4),'false_positive_rate':round(false_positive,4),'better_or_equal_rate':round(better_equal,4),'auto_eligible':eligible})
    fx_rows=[]
    for role in MAJOR_FX_ROLES:
        rows=fx.get(role,[])
        n=len(rows);better_equal=sum(str(row.get('preference','')).lower() in ('optimized','same') for row in rows)/max(1,n);mud=sum(bool(row.get('mud_failure')) for row in rows);fx_rows.append({'role':role,'trials':n,'better_or_equal_rate':round(better_equal,4),'mud_failures':mud,'pass':n>=30 and better_equal>=.90 and mud==0})
    dnc_addresses={str(row.get('address')) for row in dnc if str(row.get('status','')).upper() in ('PASS','FAIL','UNKNOWN')};dnc_pass_addresses={str(row.get('address')) for row in dnc if str(row.get('status','')).upper()=='PASS'};dnc_fail=sum(str(row.get('status','')).upper()=='FAIL' for row in dnc)
    gates={'device_identity_complete':not any(error.startswith('missing_device_') for error in errors),'voice_family_quotas_complete':all(row['trials']>=30 for row in voice_rows),'voice_auto_gates_pass':all(row['auto_eligible'] for row in voice_rows),'dnc_23_addresses_covered':len(dnc_addresses)>=23,'dnc_all_23_pass':len(dnc_pass_addresses)>=23 and dnc_fail==0,'fx_role_quotas_complete':all(row['trials']>=30 for row in fx_rows),'fx_gates_pass':all(row['pass'] for row in fx_rows),'no_critical_playback_failures':not critical}
    return {'schema':'PA800_HARDWARE_CAMPAIGN_EVALUATION_V1','input_records':len(records),'errors':errors,'voice_families':voice_rows,'fx_roles':fx_rows,'dnc':{'records':len(dnc),'unique_addresses':len(dnc_addresses),'pass_addresses':len(dnc_pass_addresses),'failures':dnc_fail,'status_counts':dict(Counter(str(row.get('status','')).upper() for row in dnc))},'critical_failure_record_indices':critical,'gates':gates,'pass':not errors and all(gates.values())}