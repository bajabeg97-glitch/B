import csv
import hashlib
import json
from pathlib import Path

from pa800_optimizer.analysis.intent_ground_truth import LABELS,calibration_gate,evaluate_intent_ground_truth,expected_calibration_error,validate_intent_ground_truth
from tools.create_instrument_intent_ground_truth import generate
from tools.evaluate_instrument_intent_ground_truth import evaluate_sheet
from tools.instrument_intent_stress_midis import generate_case


def _rows(wrong=False,confidence=1.0):
    rows=[];counts={'song':100,'style':100,'kar':30};index=0
    for content,total in counts.items():
        for file_index in range(total):
            truth=LABELS[index%len(LABELS)];predicted=LABELS[(index+1)%len(LABELS)] if wrong else truth;digest=hashlib.sha256(f'{content}-{file_index}'.encode()).hexdigest()
            rows.append({'source_sha256':digest,'content_type':content,'split':('test' if file_index%5==0 else 'validation' if file_index%5==1 else 'train'),'track':0,'channel':1,'human_function':truth,'predicted_function':predicted,'prediction_confidence':confidence,'annotator':'musician-a'});index+=1
    return rows


def test_perfect_complete_corpus_passes_calibration_but_never_grants_mutation_authority():
    result=evaluate_intent_ground_truth(_rows());gate=calibration_gate(result)
    assert result['status']=='PASS' and result['pass'] and result['coverage_complete']
    assert result['fine_roles']['macro_f1']==result['superclasses']['macro_f1']==1.0
    assert result['unknown_precision']==1.0 and result['calibration']['ece']==0.0
    assert gate['may_inform_suggestions'] and not gate['may_grant_mutation_authority'] and not gate['authority_granted']


def test_confident_wrong_predictions_fail_f1_and_calibration_gates():
    result=evaluate_intent_ground_truth(_rows(wrong=True,confidence=.99))
    assert result['status']=='FAIL' and not result['pass']
    assert not result['gates']['fine_macro_f1'] and not result['gates']['ece']
    assert calibration_gate(result)['may_inform_suggestions'] is False


def test_grouped_split_leakage_and_annotation_errors_are_explicit():
    rows=_rows();duplicate=dict(rows[0]);duplicate['split']='train';duplicate['track']=1;rows.append(duplicate)
    result=evaluate_intent_ground_truth(rows)
    assert not result['grouped_split_audit']['pass'] and not result['gates']['no_group_leakage']
    invalid=[dict(rows[0],source_sha256='bad',human_function='NOPE',prediction_confidence=2.0,annotator='')]
    validation=validate_intent_ground_truth(invalid);assert not validation['pass'] and len(validation['errors'])>=4


def test_empty_or_partial_sheet_is_external_required_and_template_has_blank_human_labels(tmp_path):
    empty=evaluate_intent_ground_truth([]);assert empty['status']=='EXTERNAL_REQUIRED' and not empty['coverage_complete'] and not empty['authority_granted']
    source=tmp_path/'midi';source.mkdir()
    generate_case('INT-001','positive',source/'one.mid');generate_case('INT-002','negative',source/'two.mid')
    sheet,manifest=generate(source,tmp_path/'truth.csv',limit=2);rows=list(csv.DictReader(sheet.open(encoding='utf-8-sig')))
    assert rows and all(row['human_function']==row['annotator']=='' for row in rows)
    assert json.loads(manifest.read_text())['schema']=='PA800_INSTRUMENT_INTENT_GROUND_TRUTH_TEMPLATE_V2'
    evaluation=evaluate_sheet(sheet);assert evaluation['status']=='EXTERNAL_REQUIRED' and evaluation['annotation_validation']['rows']==0


def test_ece_bins_are_bounded_and_weighted():
    rows=[{'human_function':'LEAD','predicted_function':'LEAD','prediction_confidence':.9},{'human_function':'LEAD','predicted_function':'COUNTER_LINE','prediction_confidence':.9},{'human_function':'UNKNOWN','predicted_function':'UNKNOWN','prediction_confidence':.2}]
    result=expected_calibration_error(rows,bins=5)
    assert 0<=result['ece']<=1 and sum(row['count'] for row in result['bins'])==3