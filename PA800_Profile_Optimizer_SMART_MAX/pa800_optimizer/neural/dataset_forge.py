"""Deterministic, provenance-aware clean/corrupt MIDI dataset construction."""
from __future__ import annotations

import hashlib
import json
import shutil
from collections import defaultdict
from pathlib import Path

from ..core.midi_io import absolute_track,rebuild_track
from ..profiles.registry import ProfileRegistry
from .event_contract import encode_neural_contract,public_contract

SCHEMA='PA800_NEURAL_DATASET_V2'
# Velocity defects belong to the profile-only velocity certification dataset,
# never to the neural rhythm/pattern dataset.
CORRUPTION_TYPES=('ONSET_SPIKE','GATE_TRUNCATE','GATE_OVERLAP','DUPLICATE_HIT','CHORD_DESYNC','GROOVE_DRIFT')


def _sha256(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def assign_group_split(source_group_id):
    bucket=int(source_group_id[:8],16)%100
    return 'train' if bucket<80 else ('validation' if bucket<90 else 'test')


def balanced_group_splits(source_group_ids):
    """Assign complete source groups to deterministic non-empty dataset splits."""
    groups=sorted(set(source_group_ids),key=lambda value:hashlib.sha256(value.encode()).hexdigest());count=len(groups)
    if count<3:return {group:assign_group_split(group) for group in groups}
    validation=max(1,round(count*.15));test=max(1,round(count*.15));train=max(1,count-validation-test)
    while train+validation+test>count and train>1:train-=1
    mapping={}
    for index,group in enumerate(groups):mapping[group]='train' if index<train else ('validation' if index<train+validation else 'test')
    return mapping


def _eligible(contract):return [row for row in contract['note_tokens'] if not row['protected']]


def _groups(tokens):
    result=defaultdict(list)
    for token in tokens:result[token['simultaneous_group_id']].append(token)
    return result


def _select_plan(contract,corruption_type):
    tokens=_eligible(contract);groups=_groups(tokens)
    if not tokens:return None
    if corruption_type=='CHORD_DESYNC':
        candidates=[rows for rows in groups.values() if len(rows)>=2]
        return sorted(candidates,key=lambda rows:(-len(rows),rows[0]['simultaneous_group_id']))[0] if candidates else None
    if corruption_type in ('ONSET_SPIKE','GATE_TRUNCATE','GATE_OVERLAP','DUPLICATE_HIT'):
        return [max(tokens,key=lambda row:(row['duration'],row['note_key']))]
    if corruption_type=='GROOVE_DRIFT':
        channels=defaultdict(list)
        for token in tokens:channels[(token['track'],token['channel'])].append(token)
        candidates=[sorted(rows,key=lambda row:(row['onset'],row['pitch'],row['occurrence'])) for rows in channels.values() if len(rows)>=4]
        return sorted(candidates,key=lambda rows:(-len(rows),rows[0]['track'],rows[0]['channel']))[0][:8] if candidates else None
    return None


def _event_map(mid):
    tracks=[absolute_track(track) for track in mid.tracks]
    maps=[{index:row for row in track for index in [row[1]]} for track in tracks]
    return tracks,maps


def _mask(token,field,old,new):return {'note_key':token['note_key'],'track':token['track'],'channel':token['channel'],'pitch':token['pitch'],'occurrence':token['occurrence'],'field':field,'old':old,'new':new}


def _apply_corruption(source,contract,corruption_type,plan,output):
    import mido
    mid=mido.MidiFile(source,clip=False);tracks,maps=_event_map(mid);mask=[];tpb=max(1,mid.ticks_per_beat)
    if corruption_type=='ONSET_SPIKE':
        token=plan[0];delta=max(1,tpb//3);on=maps[token['track']][token['on_event_index']];off=maps[token['track']][token['off_event_index']];old=on[0];on[0]+=delta;off[0]+=delta;mask.append(_mask(token,'onset',old,on[0]));mask.append(_mask(token,'off',token['off'],off[0]))
    elif corruption_type=='GATE_TRUNCATE':
        token=plan[0];off=maps[token['track']][token['off_event_index']];new=token['onset']+max(1,token['duration']//4);old=off[0];off[0]=new;mask.append(_mask(token,'off',old,new))
    elif corruption_type=='GATE_OVERLAP':
        token=plan[0];off=maps[token['track']][token['off_event_index']];new=off[0]+max(tpb//2,token['duration']);old=off[0];off[0]=new;mask.append(_mask(token,'off',old,new))
    elif corruption_type=='DUPLICATE_HIT':
        token=plan[0];track=tracks[token['track']];on=maps[token['track']][token['on_event_index']][2];off=maps[token['track']][token['off_event_index']][2];next_index=max((row[1] for row in track),default=0)+1;start=token['onset']+max(1,tpb//32);end=start+max(1,min(token['duration'],tpb//8));track.extend([[start,next_index,on.copy(time=0)],[end,next_index+1,off.copy(time=0)]]);mask.append(_mask(token,'duplicate_hit',0,1))
    elif corruption_type=='CHORD_DESYNC':
        token=max(plan,key=lambda row:row['pitch']);delta=max(1,tpb//8);on=maps[token['track']][token['on_event_index']];off=maps[token['track']][token['off_event_index']];old=on[0];on[0]+=delta;off[0]+=delta;mask.append(_mask(token,'onset',old,on[0]));mask.append(_mask(token,'off',token['off'],off[0]))
    elif corruption_type=='GROOVE_DRIFT':
        for index,token in enumerate(plan):
            delta=(index+1)*max(1,tpb//48);on=maps[token['track']][token['on_event_index']];off=maps[token['track']][token['off_event_index']];old=on[0];on[0]+=delta;off[0]+=delta;mask.append(_mask(token,'onset',old,on[0]));mask.append(_mask(token,'off',token['off'],off[0]))
    else:raise ValueError('Unknown corruption type: '+corruption_type)
    for index,track in enumerate(tracks):mid.tracks[index]=rebuild_track(track)
    output=Path(output);output.parent.mkdir(parents=True,exist_ok=True);mid.save(output)
    return mask


def forge_source(source,output,contract=None,corruption_types=CORRUPTION_TYPES,license_id='UNSPECIFIED',provenance='UNSPECIFIED'):
    source=Path(source);output=Path(output);contract=contract or encode_neural_contract(source);split=assign_group_split(contract['source_group_id']);cases=[]
    protected=[row for row in contract['note_tokens'] if row['protected']]
    hard_negatives=[{'note_key':row['note_key'],'protected_dependencies':row['protected_dependencies'],'expected_action':'PRESERVE','source_sha256':contract['source']['sha256'],'source_group_id':contract['source_group_id']} for row in protected]
    for corruption_type in corruption_types:
        plan=_select_plan(contract,corruption_type)
        if not plan:continue
        case_id=hashlib.sha256((contract['source']['sha256']+'|'+corruption_type).encode()).hexdigest()[:20];folder=output/case_id;folder.mkdir(parents=True,exist_ok=True);clean=folder/'clean.mid';corrupt=folder/'corrupt.mid';shutil.copy2(source,clean);mask=_apply_corruption(source,contract,corruption_type,plan,corrupt)
        cases.append({'case_id':case_id,'corruption_type':corruption_type,'defect_label':corruption_type,'repairability':'BOUNDED_EVENT_REPAIR','split':split,'source_file':source.name,'source_sha256':contract['source']['sha256'],'source_group_id':contract['source_group_id'],'clean_file':clean.relative_to(output).as_posix(),'clean_sha256':_sha256(clean),'corrupt_file':corrupt.relative_to(output).as_posix(),'corrupt_sha256':_sha256(corrupt),'change_mask':mask,'changed_note_keys':sorted({row['note_key'] for row in mask}),'protected_note_keys':sorted(row['note_key'] for row in protected),'license':license_id,'provenance':provenance,'authority_granted':False})
    return {'schema':'PA800_NEURAL_SOURCE_FORGE_V2','source_contract':public_contract(contract),'cases':cases,'hard_negatives':hard_negatives,'protected_only':bool(contract['note_tokens']) and not _eligible(contract),'authority_granted':False,'mutations_to_source':0}


def forge_dataset(sources,output,license_id='UNSPECIFIED',provenance='UNSPECIFIED',dataset_use='TRAINING'):
    output=Path(output);output.mkdir(parents=True,exist_ok=True);seen={};source_rows=[];cases=[];hard_negatives=[];registry=None
    for source in sorted(map(Path,sources),key=lambda path:path.as_posix()):
        raw=source.read_bytes();digest=hashlib.sha256(raw).hexdigest()
        if digest in seen:
            source_rows.append({'file':source.name,'sha256':digest,'duplicate_of':seen[digest],'included':False});continue
        if registry is None:registry=ProfileRegistry()
        seen[digest]=source.name;contract=encode_neural_contract(source,registry=registry,_source_bytes=raw);result=forge_source(source,output/'cases',contract,license_id=license_id,provenance=provenance);cases.extend(result['cases']);hard_negatives.extend(result['hard_negatives']);source_rows.append({'file':source.name,'sha256':digest,'source_group_id':contract['source_group_id'],'split':assign_group_split(contract['source_group_id']),'notes':len(contract['note_tokens']),'protected_notes':sum(row['protected'] for row in contract['note_tokens']),'protected_only':result['protected_only'],'included':True})
    split_map=balanced_group_splits(row['source_group_id'] for row in source_rows if row.get('included'))
    for row in source_rows:
        if row.get('included'):row['split']=split_map[row['source_group_id']]
    for row in cases:row['split']=split_map[row['source_group_id']]
    manifest={'schema':SCHEMA,'dataset_use':dataset_use,'license':license_id,'provenance':provenance,'sources':source_rows,'cases':cases,'hard_negatives':hard_negatives,'summary':{'input_files':len(source_rows),'unique_sources':sum(row['included'] for row in source_rows),'duplicates_rejected':sum(not row['included'] for row in source_rows),'cases':len(cases),'hard_negatives':len(hard_negatives),'protected_only_sources':sum(row.get('protected_only',False) for row in source_rows),'corruption_types':sorted({row['corruption_type'] for row in cases}),'splits':{split:sum(row['split']==split for row in cases) for split in ('train','validation','test')},'source_group_splits':{split:sum(value==split for value in split_map.values()) for split in ('train','validation','test')}},'mutations_to_original_sources':0,'authority_granted':False}
    manifest['dataset_digest']=hashlib.sha256(json.dumps({key:value for key,value in manifest.items() if key!='dataset_digest'},sort_keys=True,separators=(',',':')).encode()).hexdigest();(output/'DATASET_MANIFEST.json').write_text(json.dumps(manifest,indent=2,ensure_ascii=False)+'\n',encoding='utf-8');return manifest


def audit_dataset_manifest(manifest_or_path):
    manifest=json.loads(Path(manifest_or_path).read_text(encoding='utf-8')) if isinstance(manifest_or_path,(str,Path)) else manifest_or_path;errors=[];cases=manifest.get('cases') or [];sources=manifest.get('sources') or [];hard=manifest.get('hard_negatives') or []
    if manifest.get('schema')!=SCHEMA:errors.append('schema')
    if manifest.get('authority_granted') is not False or manifest.get('mutations_to_original_sources')!=0:errors.append('authority')
    if manifest.get('dataset_use')=='TRAINING' and (manifest.get('license') in ('',None,'UNSPECIFIED') or manifest.get('provenance') in ('',None,'UNSPECIFIED')):errors.append('missing_training_provenance')
    group_splits=defaultdict(set);source_splits=defaultdict(set)
    for row in cases:group_splits[row.get('source_group_id')].add(row.get('split'));source_splits[row.get('source_sha256')].add(row.get('split'))
    leakage={key:sorted(value) for key,value in group_splits.items() if len(value)>1};source_conflicts={key:sorted(value) for key,value in source_splits.items() if len(value)>1}
    if leakage:errors.append('source_group_split_leakage')
    if source_conflicts:errors.append('source_sha_split_leakage')
    if len(group_splits)>=3 and any(not any(row.get('split')==split for row in cases) for split in ('train','validation','test')):errors.append('empty_required_split')
    if len({row.get('corrupt_sha256') for row in cases})!=len(cases):errors.append('duplicate_corrupt_output')
    for row in cases:
        if not row.get('change_mask'):errors.append('empty_change_mask:'+str(row.get('case_id')))
        if set(row.get('changed_note_keys') or [])&set(row.get('protected_note_keys') or []):errors.append('protected_note_changed:'+str(row.get('case_id')))
        if row.get('authority_granted') is not False:errors.append('case_authority:'+str(row.get('case_id')))
    if any(row.get('expected_action')!='PRESERVE' or not row.get('protected_dependencies') for row in hard):errors.append('invalid_hard_negative')
    included=[row for row in sources if row.get('included')]
    if len({row.get('sha256') for row in included})!=len(included):errors.append('source_dedup_failure')
    return {'schema':'PA800_NEURAL_DATASET_AUDIT_V2','pass':not errors,'errors':errors,'cases':len(cases),'hard_negatives':len(hard),'source_groups':len(group_splits),'group_split_leakage':leakage,'source_split_conflicts':source_conflicts,'unique_corrupted_files':len({row.get('corrupt_sha256') for row in cases}),'corruption_types':sorted({row.get('corruption_type') for row in cases}),'authority_granted':False}
