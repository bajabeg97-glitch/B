"""Ground-truth evaluator for analyzer-only track functions and sections."""
from __future__ import annotations

from collections import Counter,defaultdict


ALLOWED_FUNCTIONS={'FOUNDATION_DRUM','FOUNDATION_PERC','FOUNDATION_BASS','LEAD','COUNTER_LINE','HARMONIC_COMP','PAD_BACKGROUND','RIFF_OSTINATO','ORNAMENT_FX','UNKNOWN'}


def validate_ground_truth(truth):
    errors=[]
    if truth.get('schema')!='PA800_CONTEXT_GROUND_TRUTH_V1':errors.append('invalid_schema')
    if truth.get('content_type') not in ('song','style','kar'):errors.append('invalid_content_type')
    seen=set()
    for index,row in enumerate(truth.get('tracks') or []):
        key=(row.get('track'),row.get('channel'))
        if key in seen:errors.append('duplicate_track_%s_%s'%key)
        seen.add(key)
        if row.get('function') not in ALLOWED_FUNCTIONS:errors.append('invalid_track_function_%d'%index)
    previous=-1
    for index,row in enumerate(truth.get('sections') or []):
        start=row.get('start_tick');end=row.get('end_tick')
        if not isinstance(start,int) or not isinstance(end,int) or start<0 or end<=start:errors.append('invalid_section_range_%d'%index)
        elif start<previous:errors.append('unsorted_section_%d'%index)
        previous=start if isinstance(start,int) else previous
        if not str(row.get('label','')).strip():errors.append('missing_section_label_%d'%index)
    return {'pass':not errors,'errors':errors}


def _match_boundaries(predicted,truth,tolerance):
    candidates=[]
    for pi,p in enumerate(predicted):
        for ti,t in enumerate(truth):
            distance=abs(p-t)
            if distance<=tolerance:candidates.append((distance,pi,ti))
    used_p=set();used_t=set();matches=[]
    for distance,pi,ti in sorted(candidates):
        if pi not in used_p and ti not in used_t:
            used_p.add(pi);used_t.add(ti);matches.append({'predicted_tick':predicted[pi],'truth_tick':truth[ti],'error_ticks':distance})
    precision=len(matches)/max(1,len(predicted));recall=len(matches)/max(1,len(truth));f1=0.0 if precision+recall==0 else 2*precision*recall/(precision+recall)
    if not predicted and not truth:precision=recall=f1=1.0
    return {'matches':matches,'predicted_count':len(predicted),'truth_count':len(truth),'precision':round(precision,4),'recall':round(recall,4),'f1':round(f1,4),'tolerance_ticks':tolerance}


def evaluate_context_prediction(report,truth,boundary_tolerance_ticks=192):
    validation=validate_ground_truth(truth)
    musical=(report or {}).get('musical_context') or report or {}
    predicted_tracks={(int(row.get('track',-1)),int(row.get('channel',0))):row for row in musical.get('track_functions') or []}
    confusion=defaultdict(Counter);evaluated=[];correct=0;unknown=0
    for row in truth.get('tracks') or []:
        key=(int(row['track']),int(row['channel']));expected=row['function'];prediction=predicted_tracks.get(key,{});actual=prediction.get('function','MISSING')
        confusion[expected][actual]+=1;correct+=int(actual==expected);unknown+=int(actual=='UNKNOWN')
        evaluated.append({'track':key[0],'channel':key[1],'truth':expected,'predicted':actual,'confidence':prediction.get('confidence'),'correct':actual==expected})
    track_total=len(evaluated);track_accuracy=correct/max(1,track_total)
    predicted_sections=musical.get('sections') or [];truth_sections=truth.get('sections') or []
    predicted_boundaries=sorted({int(row['start_tick']) for row in predicted_sections if int(row.get('start_tick',0))>0})
    truth_boundaries=sorted({int(row['start_tick']) for row in truth_sections if int(row.get('start_tick',0))>0})
    boundary=_match_boundaries(predicted_boundaries,truth_boundaries,max(0,int(boundary_tolerance_ticks)))
    confusion_rows=[]
    for expected,row in sorted(confusion.items()):
        for actual,count in sorted(row.items()):confusion_rows.append({'truth':expected,'predicted':actual,'count':count})
    return {'schema':'PA800_CONTEXT_EVALUATION_V1','ground_truth_validation':validation,'files_evaluated':1,'track_function':{'total':track_total,'correct':correct,'accuracy':round(track_accuracy,4),'unknown_predictions':unknown,'unknown_rate':round(unknown/max(1,track_total),4),'confusion_matrix':confusion_rows,'rows':evaluated},'section_boundaries':boundary,'gates':{'track_accuracy_at_least_090':track_accuracy>=.90,'section_boundary_f1_at_least_085':boundary['f1']>=.85,'ground_truth_valid':validation['pass']},'pass':validation['pass'] and track_accuracy>=.90 and boundary['f1']>=.85}