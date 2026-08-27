import json

from pa800_optimizer.analysis.factory_usage_batch import aggregate_usage_reports,load_and_aggregate,write_batch_outputs


def meter(total,exact,unknown=0,mutated=0):
    blocked=unknown
    return {'factory_usage_meter':{'schema':'PA800_FACTORY_USAGE_METER_V1','notes_total':total,'classification_counts':{'EXACT_SOUND':exact,'UNKNOWN':unknown},'stage_counts':{'total':total,'available':exact,'resolved':exact,'used':exact,'mutated':mutated,'blocked':blocked},'by_family':[{'family':'PIANO','total':exact,'available':exact,'resolved':exact,'used':exact,'mutated':mutated,'blocked':0,'EXACT_SOUND':exact},{'family':'UNKNOWN','total':unknown,'available':0,'resolved':0,'used':0,'mutated':0,'blocked':unknown,'UNKNOWN':unknown}],'blocked_mutation_count':0,'pass':True}}


def test_batch_aggregation_preserves_100_percent_classification():
    result=aggregate_usage_reports([('a.json',meter(10,8,2,3)),('b.json',meter(5,5,0,1))])
    assert result['pass']
    assert result['files_total']==2 and result['notes_total']==15
    assert result['classification_counts']=={'EXACT_SOUND':13,'UNKNOWN':2}
    assert result['invariants']['classification_equals_total']


def test_batch_writer_emits_machine_readable_json_and_csv(tmp_path):
    source=tmp_path/'report.json';source.write_text(json.dumps(meter(4,4)),encoding='utf-8')
    result=load_and_aggregate([source]);json_path=tmp_path/'usage.json';csv_path=tmp_path/'usage.csv';write_batch_outputs(result,json_path,csv_path)
    assert json.loads(json_path.read_text(encoding='utf-8'))['pass']
    assert csv_path.read_text(encoding='utf-8').splitlines()[0]=='family,total,available,resolved,used,mutated,blocked,coverage_percent'


def test_batch_aggregation_rejects_missing_usage_meter():
    result=aggregate_usage_reports([('bad.json',{})])
    assert not result['pass'] and result['invalid_reports']==['bad.json']