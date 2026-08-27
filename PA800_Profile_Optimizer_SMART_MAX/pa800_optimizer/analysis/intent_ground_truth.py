"""Ground-truth metrics and calibration gates for Instrument Intent V3."""
from __future__ import annotations

from collections import Counter,defaultdict


LABELS=('FOUNDATION_DRUM','FOUNDATION_PERC','FOUNDATION_BASS','HARMONIC_COMP','PAD_BACKGROUND','RIFF_OSTINATO','LEAD','COUNTER_LINE','ORNAMENT_FX','UNKNOWN')
SUPERCLASS={
    'FOUNDATION_DRUM':'FOUNDATION','FOUNDATION_PERC':'FOUNDATION','FOUNDATION_BASS':'FOUNDATION',
    'HARMONIC_COMP':'BACKGROUND','PAD_BACKGROUND':'BACKGROUND','RIFF_OSTINATO':'BACKGROUND',
    'LEAD':'FOREGROUND','COUNTER_LINE':'FOREGROUND','ORNAMENT_FX':'ORNAMENT','UNKNOWN':'UNKNOWN',
}
REQUIRED_COUNTS={'song':100,'style':100,'kar':30}
THRESHOLDS={'superclass_macro_f1':.90,'fine_macro_f1':.82,'unknown_precision':.95,'ece':.05}


def validate_intent_ground_truth(rows):
    errors=[];seen=set()
    for index,row in enumerate(rows):
        key=(row.get('source_sha256'),row.get('track'),row.get('channel'))
        if not row.get('source_sha256') or len(str(row.get('source_sha256')))!=64:errors.append(f'invalid_source_sha256_{index}')
        if key in seen:errors.append(f'duplicate_annotation_{index}')
        seen.add(key)
        if row.get('content_type') not in ('song','style','kar'):errors.append(f'invalid_content_type_{index}')
        if row.get('human_function') not in LABELS:errors.append(f'invalid_human_function_{index}')
        if row.get('predicted_function') not in LABELS:errors.append(f'invalid_predicted_function_{index}')
        confidence=row.get('prediction_confidence')
        if not isinstance(confidence,(int,float)) or not 0<=confidence<=1:errors.append(f'invalid_confidence_{index}')
        if row.get('split') not in ('train','validation','test'):errors.append(f'invalid_split_{index}')
        if not str(row.get('annotator','')).strip():errors.append(f'missing_annotator_{index}')
    return {'pass':not errors,'errors':errors,'rows':len(rows)}


def _class_metrics(rows,truth_key,predicted_key,labels):
    confusion=defaultdict(Counter);per_class={}
    for row in rows:confusion[row[truth_key]][row[predicted_key]]+=1
    for label in labels:
        tp=confusion[label][label];fp=sum(confusion[other][label] for other in labels if other!=label);fn=sum(confusion[label][other] for other in labels if other!=label)
        precision=tp/max(1,tp+fp);recall=tp/max(1,tp+fn);f1=0.0 if precision+recall==0 else 2*precision*recall/(precision+recall)
        per_class[label]={'support':sum(confusion[label].values()),'precision':round(precision,4),'recall':round(recall,4),'f1':round(f1,4)}
    supported=[row['f1'] for row in per_class.values() if row['support']>0]
    confusion_rows=[{'truth':truth,'predicted':prediction,'count':count} for truth in labels for prediction,count in sorted(confusion[truth].items())]
    return {'macro_f1':round(sum(supported)/max(1,len(supported)),4),'per_class':per_class,'confusion_matrix':confusion_rows}


def expected_calibration_error(rows,bins=10):
    bins=max(1,int(bins));total=len(rows);result=[];ece=0.0
    for index in range(bins):
        low=index/bins;high=(index+1)/bins;bucket=[row for row in rows if low<=float(row['prediction_confidence'])<high or (index==bins-1 and float(row['prediction_confidence'])==1.0)]
        if not bucket:continue
        confidence=sum(float(row['prediction_confidence']) for row in bucket)/len(bucket);accuracy=sum(row['human_function']==row['predicted_function'] for row in bucket)/len(bucket);weight=len(bucket)/max(1,total);ece+=weight*abs(accuracy-confidence)
        result.append({'low':round(low,3),'high':round(high,3),'count':len(bucket),'mean_confidence':round(confidence,4),'accuracy':round(accuracy,4),'gap':round(abs(accuracy-confidence),4)})
    return {'ece':round(ece,4),'bins':result,'bin_count':bins}


def _leakage(rows):
    by_hash=defaultdict(set)
    for row in rows:by_hash[row['source_sha256']].add(row['split'])
    conflicts={digest:sorted(splits) for digest,splits in by_hash.items() if len(splits)>1}
    return {'pass':not conflicts,'conflicting_source_hashes':conflicts,'unique_files':len(by_hash)}


def evaluate_intent_ground_truth(rows):
    rows=list(rows);validation=validate_intent_ground_truth(rows);fine=_class_metrics(rows,'human_function','predicted_function',LABELS) if rows else {'macro_f1':0.0,'per_class':{},'confusion_matrix':[]}
    super_rows=[{**row,'human_superclass':SUPERCLASS[row['human_function']],'predicted_superclass':SUPERCLASS[row['predicted_function']]} for row in rows if row.get('human_function') in SUPERCLASS and row.get('predicted_function') in SUPERCLASS]
    super_labels=('FOUNDATION','BACKGROUND','FOREGROUND','ORNAMENT','UNKNOWN');super_metrics=_class_metrics(super_rows,'human_superclass','predicted_superclass',super_labels) if rows else {'macro_f1':0.0,'per_class':{},'confusion_matrix':[]}
    calibration=expected_calibration_error(rows);predicted_unknown=[row for row in rows if row.get('predicted_function')=='UNKNOWN'];unknown_precision=sum(row.get('human_function')=='UNKNOWN' for row in predicted_unknown)/max(1,len(predicted_unknown))
    files={(row['source_sha256'],row['content_type']) for row in rows if row.get('source_sha256')};counts={kind:sum(content==kind for _digest,content in files) for kind in REQUIRED_COUNTS};coverage=all(counts[key]>=value for key,value in REQUIRED_COUNTS.items());leakage=_leakage(rows) if rows else {'pass':True,'conflicting_source_hashes':{},'unique_files':0}
    metric_gates={'superclass_macro_f1':super_metrics['macro_f1']>=THRESHOLDS['superclass_macro_f1'],'fine_macro_f1':fine['macro_f1']>=THRESHOLDS['fine_macro_f1'],'unknown_precision':unknown_precision>=THRESHOLDS['unknown_precision'],'ece':calibration['ece']<=THRESHOLDS['ece'],'no_group_leakage':leakage['pass'],'valid_annotations':validation['pass']}
    status='EXTERNAL_REQUIRED' if not coverage else ('PASS' if all(metric_gates.values()) else 'FAIL')
    return {'schema':'PA800_INSTRUMENT_INTENT_GROUND_TRUTH_EVALUATION_V2','status':status,'authority_granted':False,'mutations':0,'annotation_validation':validation,'file_counts':counts,'required_file_counts':REQUIRED_COUNTS,'coverage_complete':coverage,'fine_roles':fine,'superclasses':super_metrics,'unknown_precision':round(unknown_precision,4),'unknown_predictions':len(predicted_unknown),'calibration':calibration,'grouped_split_audit':leakage,'thresholds':THRESHOLDS,'gates':metric_gates,'pass':status=='PASS'}


def calibration_gate(evaluation):
    """Return an explicit non-authority decision for downstream automation."""
    passed=bool(evaluation.get('pass')) and evaluation.get('status')=='PASS'
    return {'schema':'PA800_INTENT_CALIBRATION_GATE_V1','status':'CALIBRATED_ANALYZER' if passed else evaluation.get('status','FAIL'),'may_inform_suggestions':passed,'may_grant_mutation_authority':False,'authority_granted':False,'reason':'Ground truth calibrates confidence; mutation authority remains a separate E2/E3 decision.'}