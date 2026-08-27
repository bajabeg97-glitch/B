"""Small deterministic masked-event neural encoder for infrastructure validation."""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import tempfile
from functools import lru_cache
from pathlib import Path

from .dataset_forge import balanced_group_splits

SCHEMA='PA800_SELF_SUPERVISED_ENCODER_V1'

# Runtime admission is intentionally stricter than the historical training
# acceptance threshold.  Acceptance answers "is this artifact structurally and
# statistically valid?"; admission answers "how much proposal influence may it
# have during an optimization run?".  The encoder never owns mutation authority.
RUNTIME_ADMISSION_HIGH=0.65
RUNTIME_ADMISSION_ADVISOR=0.45


def encoder_runtime_admission(model):
    """Return fail-closed runtime status without mutating the model artifact.

    ``confidence`` is the held-out reconstruction improvement stored by the
    acceptance process.  It is an evidence/admission score, not a calibrated
    probability of musical correctness.
    """
    acceptance=model.get('acceptance') or {}
    confidence=max(0.0,min(1.0,float(acceptance.get('confidence',0.0) or 0.0)))
    accepted=bool(acceptance.get('pass')) and model.get('authority_granted') is False
    if not accepted:
        mode='REJECT_TO_FACTORY_GOLD';inference_ready=False;proposal_allowed=False;factory_verify=True
    elif confidence>=RUNTIME_ADMISSION_HIGH:
        mode='ALLOW_WITH_FACTORY_VERIFY';inference_ready=True;proposal_allowed=True;factory_verify=True
    elif confidence>=RUNTIME_ADMISSION_ADVISOR:
        mode='ADVISOR_ONLY';inference_ready=True;proposal_allowed=True;factory_verify=True
    else:
        mode='REJECT_TO_FACTORY_GOLD';inference_ready=False;proposal_allowed=False;factory_verify=True
    return {
        'schema':'PA800_ENCODER_RUNTIME_ADMISSION_V1',
        'model_validated':accepted,
        'inference_ready':inference_ready,
        'mutation_authority':False,
        'proposal_allowed':proposal_allowed,
        'mode':mode,
        'confidence':round(confidence,6),
        'confidence_semantics':'held_out_reconstruction_improvement_not_calibrated_probability',
        'thresholds':{'proposal_with_factory_verify':RUNTIME_ADMISSION_HIGH,'advisor_only':RUNTIME_ADMISSION_ADVISOR},
        'factory_gold_verifier_required':factory_verify,
        'allowed_outputs':['timing','gate'],
        'forbidden_outputs':['velocity','pitch','voice','sound_kit','articulation','fx'],
        'authority_granted':False,
    }
# Velocity is intentionally absent.  PA800 velocity is owned exclusively by the
# deterministic sound/role profiles and their independent verifier.
BASE_FEATURES=('interval_prev','duration_beats','onset_delta_beats','position_sin','position_cos','group_size','voice_index','protected','family_hash','role_hash','channel')
PHRASE_FEATURES=('phrase_position','phrase_note_count','phrase_duration','phrase_density','phrase_pitch_span','phrase_contour','phrase_repetition','phrase_chord_fraction','phrase_ornament_fraction','bar_position','phrase_start','phrase_end','phrase_bar_span','lookback_interval_mean','lookahead_interval_mean','track_progress','element_hash','cv')
_FEATURE_INDEX={name:index for index,name in enumerate(BASE_FEATURES)}
_ARRAY_CACHE={}


def _numpy():
    try:import numpy as np;return np
    except Exception as exc:raise RuntimeError('Neural encoder requires the optional numpy dependency') from exc


@lru_cache(maxsize=256)
def _hash_feature(text):return (int(hashlib.sha256(str(text).encode()).hexdigest()[:8],16)%2001)/1000.0-1.0


def _phrase_feature_matrix(contract,notes,tpb):
    """Whole-phrase aggregates aligned to note rows; velocity is absent."""
    np=_numpy();summaries={row.get('phrase_id'):row for row in contract.get('phrases') or []};by_phrase={};by_track={}
    for index,row in enumerate(notes):by_phrase.setdefault(row.get('phrase_id') or 'T%d:C%d:LEGACY'%(row['track'],row['channel']),[]).append(index);by_track.setdefault((row['track'],row['channel']),[]).append(index)
    track_end={key:max((notes[index]['off'] for index in indices),default=1) for key,indices in by_track.items()};result=np.zeros((len(notes),len(PHRASE_FEATURES)),dtype=float)
    for phrase_id,indices in by_phrase.items():
        rows=[notes[index] for index in indices];summary=summaries.get(phrase_id) or {};pitches=[row['pitch'] for row in rows];intervals=[b-a for a,b in zip(pitches,pitches[1:])];onsets={row['onset'] for row in rows};start=min((row['onset'] for row in rows),default=0);end=max((row['off'] for row in rows),default=start+1);duration=max(1,end-start);bar_values=[int(row.get('bar',0)) for row in rows];contour=float(summary.get('contour_direction',0 if not intervals else sum(intervals)/max(1,sum(abs(value) for value in intervals))));repetition=float(summary.get('repetition_fraction',sum(a==b for a,b in zip(pitches,pitches[1:]))/max(1,len(rows)-1)));ornament=float(summary.get('ornament_fraction',sum(abs(value)<=2 for value in intervals)/max(1,len(intervals))));chord=float(summary.get('chord_note_fraction',sum(sum(other['onset']==row['onset'] for other in rows)>1 for row in rows)/max(1,len(rows))))
        for position,index in enumerate(indices):
            row=notes[index];lookback=intervals[max(0,position-8):position];lookahead=intervals[position:min(len(intervals),position+8)];bar_ticks=max(1,int(row.get('bar_ticks',tpb*4)));track_key=(row['track'],row['channel'])
            result[index]=[position/max(1,len(rows)-1),min(1,len(rows)/64.0),min(1,(duration/float(tpb))/32.0),min(1,(len(rows)/(duration/float(tpb)))/8.0),min(1,(max(pitches)-min(pitches))/48.0),max(-1,min(1,contour)),max(0,min(1,repetition)),max(0,min(1,chord)),max(0,min(1,ornament)),max(0,min(1,float(row.get('position_in_bar',row.get('position_in_beat',0)))/bar_ticks)),float(position==0),float(position==len(rows)-1),min(1,(max(bar_values)-min(bar_values)+1)/8.0),max(-1,min(1,(sum(lookback)/max(1,len(lookback)))/24.0)),max(-1,min(1,(sum(lookahead)/max(1,len(lookahead)))/24.0)),max(0,min(1,row['onset']/max(1,track_end[track_key]))),_hash_feature(row.get('element') or 'NO_ELEMENT'),max(0,min(1,float(row.get('cv') or 0)/6.0))]
    return result


def _phrase_aware_model(model):
    return model.get('context')=='HIERARCHICAL_WHOLE_PHRASE' and model.get('phrase_feature_names')==list(PHRASE_FEATURES)


def contract_feature_matrix(contract,phrase_aware=True):
    """Return transposition-invariant note and whole-phrase features.

    New training uses complete phrase aggregates (up to eight bars). Passing
    phrase_aware=False reproduces the exact legacy 33-D input for old models.
    """
    np=_numpy();tpb=max(1,int((contract.get('midi') or {}).get('ticks_per_beat',192)));notes=sorted(contract.get('note_tokens') or [],key=lambda row:(row['track'],row['channel'],row['onset'],row['pitch'],row['occurrence']));base=[];previous={}
    for row in notes:
        key=(row['track'],row['channel']);prior=previous.get(key);interval=0 if prior is None else max(-24,min(24,row['pitch']-prior['pitch']))/24.0;delta=0 if prior is None else max(0,min(8*tpb,row['onset']-prior['onset']))/float(tpb);position=(row['position_in_beat']/float(tpb))*6.283185307179586
        base.append([interval,min(8.0,row['duration']/float(tpb))/8.0,min(8.0,delta)/8.0,float(np.sin(position)),float(np.cos(position)),min(8,row['simultaneous_group_size'])/8.0,min(8,row['voice_index'])/8.0,float(bool(row['protected'])),_hash_feature(row['family']),_hash_feature(row['role']),row['channel']/15.0]);previous[key]=row
    input_width=len(BASE_FEATURES)*3+(len(PHRASE_FEATURES) if phrase_aware else 0)
    if not base:return np.zeros((0,input_width),dtype=float),np.zeros((0,len(BASE_FEATURES)),dtype=float)
    base=np.asarray(base,dtype=float);width=len(BASE_FEATURES);context=np.zeros((len(base),width*3),dtype=float)
    context[:,width:width*2]=base
    if phrase_aware:
        groups={}
        for index,row in enumerate(notes):groups.setdefault(row.get('phrase_id') or 'T%d:C%d:LEGACY'%(row['track'],row['channel']),[]).append(index)
        for indices in groups.values():
            for left,right in zip(indices,indices[1:]):context[right,:width]=base[left];context[left,width*2:]=base[right]
        context=np.concatenate((context,_phrase_feature_matrix(contract,notes,tpb)),axis=1)
    else:
        # Exact legacy behavior retained so accepted 33-D models load and run
        # without retraining or changing their learned timing/gate semantics.
        context[1:,:width]=base[:-1];context[:-1,width*2:]=base[1:]
    return context,base


def grouped_contract_splits(contracts):
    mapping=balanced_group_splits(contract['source_group_id'] for contract in contracts)
    return {contract['source']['filename']:mapping[contract['source_group_id']] for contract in contracts}


def _model_digest(model):
    payload={key:value for key,value in model.items() if key!='model_digest'}
    return hashlib.sha256(json.dumps(payload,sort_keys=True,separators=(',',':')).encode()).hexdigest()


def train_self_supervised_encoder(contracts,hidden_size=24,epochs=450,learning_rate=.035,mask_rate=.35,seed=800,progress_callback=None):
    np=_numpy();contracts=list(contracts);split_by_file=grouped_contract_splits(contracts);rows={'train':[],'validation':[],'test':[]};targets={'train':[],'validation':[],'test':[]}
    for contract in contracts:
        x,y=contract_feature_matrix(contract,phrase_aware=True);split=split_by_file[contract['source']['filename']]
        if len(x):rows[split].append(x);targets[split].append(y)
    if not rows['train'] or not rows['validation'] or not rows['test']:raise ValueError('Grouped train/validation/test data is required')
    x_train=np.concatenate(rows['train']);y_train=np.concatenate(targets['train']);x_mean=x_train.mean(0);x_std=x_train.std(0);x_std[x_std<1e-8]=1;y_mean=y_train.mean(0);y_std=y_train.std(0);y_std[y_std<1e-8]=1;x_norm=(x_train-x_mean)/x_std;y_norm=(y_train-y_mean)/y_std;rng=np.random.default_rng(seed);w1=rng.normal(0,.12,(x_norm.shape[1],hidden_size));b1=np.zeros(hidden_size);w2=rng.normal(0,.12,(hidden_size,y_norm.shape[1]));b2=np.zeros(y_norm.shape[1]);current_offset=len(BASE_FEATURES);loss_history=[]
    for epoch in range(int(epochs)):
        mask=rng.random(y_norm.shape)<mask_rate
        mask[~mask.any(axis=1),epoch%y_norm.shape[1]]=True
        masked=x_norm.copy();masked_rows,masked_features=np.nonzero(mask);masked[masked_rows,current_offset+masked_features]=0.0
        hidden=np.tanh(masked@w1+b1);prediction=hidden@w2+b2;error=(prediction-y_norm)*mask;den=max(1,int(mask.sum()));loss=float((error*error).sum()/den);gradient=2*error/den;gw2=hidden.T@gradient;gb2=gradient.sum(0);gh=(gradient@w2.T)*(1-hidden*hidden);gw1=masked.T@gh;gb1=gh.sum(0)
        for gradient_array in (gw1,gb1,gw2,gb2):np.clip(gradient_array,-1,1,out=gradient_array)
        rate=learning_rate*(1.0-.65*epoch/max(1,epochs-1));w1-=rate*gw1;b1-=rate*gb1;w2-=rate*gw2;b2-=rate*gb2
        checkpoint=max(1,int(epochs)//20)
        if epoch==0 or epoch==epochs-1 or (epoch+1)%checkpoint==0:
            progress={'epoch':epoch+1,'epochs':int(epochs),'percent':round(100*(epoch+1)/max(1,int(epochs)),1),'masked_mse':round(loss,8),'learning_rate':round(rate,8)};loss_history.append(progress)
            if progress_callback:progress_callback(dict(progress))
    model={'schema':SCHEMA,'feature_names':list(BASE_FEATURES),'phrase_feature_names':list(PHRASE_FEATURES),'context':'HIERARCHICAL_WHOLE_PHRASE','phrase_context':{'maximum_bars':8,'features':len(PHRASE_FEATURES),'previous_next_scope':'SAME_PHRASE','velocity_features':False},'hidden_size':hidden_size,'epochs':epochs,'mask_rate':mask_rate,'seed':seed,'x_mean':x_mean.tolist(),'x_std':x_std.tolist(),'y_mean':y_mean.tolist(),'y_std':y_std.tolist(),'w1':w1.tolist(),'b1':b1.tolist(),'w2':w2.tolist(),'b2':b2.tolist(),'split_by_file':split_by_file,'loss_history':loss_history,'training_sources':sum(value=='train' for value in split_by_file.values()),'validation_sources':sum(value=='validation' for value in split_by_file.values()),'test_sources':sum(value=='test' for value in split_by_file.values()),'trained_on_synthetic_proxy':True,'analyzer_only':True,'mutations':0,'authority_granted':False}
    model['model_digest']=_model_digest(model);return model


def _arrays(model):
    digest=model.get('model_digest') or _model_digest(model);cached=_ARRAY_CACHE.get(digest)
    if cached is not None:return cached
    np=_numpy();cached=tuple(np.asarray(model[key],dtype=float) for key in ('x_mean','x_std','y_mean','y_std','w1','b1','w2','b2'))
    if len(_ARRAY_CACHE)>=8:_ARRAY_CACHE.pop(next(iter(_ARRAY_CACHE)))
    _ARRAY_CACHE[digest]=cached;return cached


def encode_contract(contract,model):
    np=_numpy();x,_target=contract_feature_matrix(contract,phrase_aware=_phrase_aware_model(model));x_mean,x_std,_ym,_ys,w1,b1,_w2,_b2=_arrays(model)
    if not len(x):embedding=np.zeros(model['hidden_size'])
    else:embedding=np.tanh(((x-x_mean)/x_std)@w1+b1).mean(0)
    return {'schema':'PA800_NEURAL_MUSIC_EMBEDDING_V1','source_group_id':contract['source_group_id'],'dimensions':len(embedding),'embedding':[round(float(value),9) for value in embedding],'model_digest':model['model_digest'],'mutations':0,'authority_granted':False}


def _predict_masked_array(contract,model,feature_names):
    np=_numpy();requested=tuple(feature_names);unknown=sorted(set(requested)-set(BASE_FEATURES))
    if unknown:raise ValueError('Unknown masked features: %s'%unknown)
    x,_target=contract_feature_matrix(contract,phrase_aware=_phrase_aware_model(model))
    requested_indices=tuple(_FEATURE_INDEX[name] for name in requested)
    if not len(x):return requested,np.zeros((0,len(requested)),dtype=float)
    x_mean,x_std,y_mean,y_std,w1,b1,w2,b2=_arrays(model);normalized=(x-x_mean)/x_std;offset=len(BASE_FEATURES)
    for index in requested_indices:normalized[:,offset+index]=0.0
    predicted=(np.tanh(normalized@w1+b1)@w2+b2)*y_std+y_mean
    return requested,predicted[:,requested_indices]


def predict_masked_features(contract,model,feature_names):
    """Predict selected current-note features without granting mutation authority."""
    requested,predicted=_predict_masked_array(contract,model,feature_names)
    return [{'predicted':{name:float(value) for name,value in zip(requested,predicted[row])}} for row in range(len(predicted))]


def evaluate_self_supervised_encoder(contracts,model,seed=1800):
    np=_numpy();x_mean,x_std,y_mean,y_std,w1,b1,w2,b2=_arrays(model);rng=np.random.default_rng(seed);metrics={}
    for split in ('train','validation','test'):
        xs=[];ys=[]
        for contract in contracts:
            if model['split_by_file'][contract['source']['filename']]!=split:continue
            x,y=contract_feature_matrix(contract,phrase_aware=_phrase_aware_model(model))
            if len(x):xs.append(x);ys.append(y)
        x=np.concatenate(xs);target=np.concatenate(ys);xn=(x-x_mean)/x_std;yn=(target-y_mean)/y_std;mask=rng.random(yn.shape)<model['mask_rate'];mask[~mask.any(axis=1),0]=True;masked=xn.copy();offset=len(BASE_FEATURES)
        masked_rows,masked_features=np.nonzero(mask);masked[masked_rows,offset+masked_features]=0
        prediction=np.tanh(masked@w1+b1)@w2+b2;den=max(1,int(mask.sum()));model_mse=float((((prediction-yn)*mask)**2).sum()/den);baseline_mse=float((((0-yn)*mask)**2).sum()/den);metrics[split]={'notes':len(x),'masked_values':int(mask.sum()),'model_mse':round(model_mse,8),'mean_baseline_mse':round(baseline_mse,8),'improvement':round((baseline_mse-model_mse)/max(1e-12,baseline_mse),6)}
    return {'schema':'PA800_SELF_SUPERVISED_ENCODER_EVALUATION_V1','metrics':metrics,'validation_improves_baseline':metrics['validation']['improvement']>0,'test_improves_baseline':metrics['test']['improvement']>0,'mutations':0,'authority_granted':False}


def finalize_encoder_acceptance(contracts,model,dataset_audit=None):
    """Attach a fail-closed acceptance record before explicit application."""
    contracts=list(contracts);evaluation=evaluate_self_supervised_encoder(contracts,model);metrics=evaluation['metrics'];reasons=[]
    source_keys={'train':'training_sources','validation':'validation_sources','test':'test_sources'}
    for split,key in source_keys.items():
        if int(model.get(key,0) or 0)<=0:reasons.append('empty_'+split+'_split')
    if not evaluation['validation_improves_baseline']:reasons.append('validation_does_not_improve_baseline')
    if not evaluation['test_improves_baseline']:reasons.append('test_does_not_improve_baseline')
    if dataset_audit is not None:
        if not dataset_audit.get('pass'):reasons.append('dataset_audit_failed')
        if dataset_audit.get('group_split_leakage'):reasons.append('dataset_group_leakage')
    confidence=max(0.0,min(1.0,float(metrics['validation']['improvement']),float(metrics['test']['improvement'])))
    minimum_confidence=.01
    if confidence<minimum_confidence:reasons.append('confidence_below_minimum')
    acceptance={'schema':'PA800_NEURAL_MODEL_ACCEPTANCE_V1','pass':not reasons,'reasons':reasons,'confidence':round(confidence,6),'validation_improvement':metrics['validation']['improvement'],'test_improvement':metrics['test']['improvement'],'minimum_confidence':minimum_confidence,'explicit_application_only':True,'allowed_outputs':['timing','gate'],'forbidden_outputs':['velocity','pitch','voice','sound_kit','articulation','fx'],'authority_granted':False}
    model['evaluation']=evaluation;model['acceptance']=acceptance;model['production_ready']=bool(acceptance['pass']);model['model_digest']=_model_digest(model)
    return model,acceptance,evaluation


def save_encoder_model(model,path):
    if model.get('model_digest')!=_model_digest(model):raise ValueError('Invalid model digest')
    Path(path).write_text(json.dumps(model,indent=2,ensure_ascii=False)+'\n',encoding='utf-8');return Path(path)


def validate_encoder_feature_contract(model):
    """Reject stale/pre-velocity-isolation models before NumPy broadcasting."""
    expected_features=list(BASE_FEATURES);phrase_aware=_phrase_aware_model(model);input_width=len(BASE_FEATURES)*3+(len(PHRASE_FEATURES) if phrase_aware else 0);output_width=len(BASE_FEATURES);errors=[]
    if model.get('feature_names')!=expected_features:errors.append('feature_names')
    if model.get('context')=='HIERARCHICAL_WHOLE_PHRASE' and not phrase_aware:errors.append('phrase_feature_names')
    if any('velocity' in str(name).lower() for name in model.get('feature_names',[])):errors.append('velocity_feature_forbidden')
    shapes={'x_mean':input_width,'x_std':input_width,'y_mean':output_width,'y_std':output_width,'b2':output_width}
    for key,size in shapes.items():
        if len(model.get(key) or [])!=size:errors.append('%s:%s!=%s'%(key,len(model.get(key) or []),size))
    w1=model.get('w1') or [];w2=model.get('w2') or [];hidden=int(model.get('hidden_size',0) or 0)
    if len(w1)!=input_width or any(len(row)!=hidden for row in w1):errors.append('w1_shape')
    if len(model.get('b1') or [])!=hidden:errors.append('b1_shape')
    if len(w2)!=hidden or any(len(row)!=output_width for row in w2):errors.append('w2_shape')
    return {'pass':not errors,'errors':errors,'input_width':input_width,'output_width':output_width,'phrase_aware':phrase_aware,'phrase_features':len(PHRASE_FEATURES) if phrase_aware else 0,'velocity_neural_input':False,'velocity_neural_output':False}


def migrate_legacy_velocity_encoder(path):
    """Prune the velocity input/output from an accepted 36-D legacy model.

    The remaining learned weights are preserved exactly. The original file is
    copied once beside the active model so migration is reversible.
    """
    path=Path(path);model=json.loads(path.read_text(encoding='utf-8'));old_features=list(model.get('feature_names') or []);velocity=[index for index,name in enumerate(old_features) if 'velocity' in str(name).lower()]
    if len(old_features)!=len(BASE_FEATURES)+1 or len(velocity)!=1 or any(name not in old_features for name in BASE_FEATURES):raise ValueError('Legacy model cannot be safely migrated: feature_names are not the recognized 36-D velocity contract')
    if not (model.get('acceptance') or {}).get('pass'):raise ValueError('Legacy model was not accepted; migration will not promote it')
    keep=[old_features.index(name) for name in BASE_FEATURES];old_width=len(old_features);input_keep=[block*old_width+index for block in range(3) for index in keep];legacy_digest=model.get('model_digest');backup=path.with_suffix(path.suffix+'.legacy36.backup')
    model['x_mean']=[model['x_mean'][index] for index in input_keep];model['x_std']=[model['x_std'][index] for index in input_keep];model['w1']=[model['w1'][index] for index in input_keep]
    for key in ('y_mean','y_std','b2'):model[key]=[model[key][index] for index in keep]
    model['w2']=[[row[index] for index in keep] for row in model['w2']];model['feature_names']=list(BASE_FEATURES)
    model['acceptance']['forbidden_outputs']=sorted(set(model['acceptance'].get('forbidden_outputs') or [])|{'velocity'})
    model['migration']={'schema':'PA800_ENCODER_VELOCITY_PRUNE_V1','from_input_width':old_width*3,'to_input_width':len(BASE_FEATURES)*3,'removed_feature':old_features[velocity[0]],'legacy_model_digest':legacy_digest,'weights_retrained':False,'timing_gate_weights_preserved':True,'velocity_neural_input':False,'velocity_neural_output':False}
    model['model_digest']=_model_digest(model);audit=validate_encoder_feature_contract(model)
    if not audit['pass']:raise ValueError('Migrated model failed feature contract: '+','.join(audit['errors']))
    if not backup.exists():shutil.copy2(path,backup)
    fd,tmp=tempfile.mkstemp(prefix=path.name+'.',suffix='.migration.tmp',dir=path.parent);os.close(fd)
    try:Path(tmp).write_text(json.dumps(model,indent=2,ensure_ascii=False)+'\n',encoding='utf-8');os.replace(tmp,path)
    finally:
        try:Path(tmp).unlink()
        except FileNotFoundError:pass
    return model


def load_encoder_model(path,require_accepted=False,migrate_legacy=False):
    model=json.loads(Path(path).read_text(encoding='utf-8'))
    if model.get('schema')!=SCHEMA or model.get('model_digest')!=_model_digest(model) or model.get('authority_granted') is not False:raise ValueError('Invalid encoder model')
    contract=validate_encoder_feature_contract(model)
    if not contract['pass'] and migrate_legacy:model=migrate_legacy_velocity_encoder(path);contract=validate_encoder_feature_contract(model)
    if not contract['pass']:raise ValueError('Incompatible encoder feature contract (expected %d velocity-free inputs): %s'%(contract['input_width'],','.join(contract['errors'])))
    if require_accepted and not (model.get('acceptance') or {}).get('pass'):raise ValueError('Neural model is not accepted for explicit application')
    return model
