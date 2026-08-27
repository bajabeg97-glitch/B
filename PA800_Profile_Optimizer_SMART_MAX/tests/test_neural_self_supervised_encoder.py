import copy
import json
from pathlib import Path
from pa800_optimizer.neural.event_contract import encode_neural_contract
from pa800_optimizer.neural.self_supervised_encoder import BASE_FEATURES,PHRASE_FEATURES,contract_feature_matrix,encode_contract,evaluate_self_supervised_encoder,load_encoder_model,predict_masked_features,save_encoder_model,train_self_supervised_encoder
from tools.run_neural_dataset_certification import certify as certify_dataset

def _contracts(tmp_path):
    certify_dataset(tmp_path/'dataset');return [encode_neural_contract(path,include_source_bytes=False) for path in sorted((tmp_path/'dataset'/'sources').glob('*.mid'))]

def test_feature_matrix_is_transposition_invariant(tmp_path):
    contracts=_contracts(tmp_path);by_name={row['source']['filename']:row for row in contracts};one,_=contract_feature_matrix(by_name['GTR-001_positive.mid']);two,_=contract_feature_matrix(by_name['GTR-001_transposed.mid']);assert one.shape==two.shape and one.shape[1]==len(BASE_FEATURES)*3+len(PHRASE_FEATURES) and (one==two).all()

def test_whole_phrase_tail_changes_phrase_context_not_legacy_context(tmp_path):
    contracts=_contracts(tmp_path);contract=max(contracts,key=lambda row:len(row['note_tokens']));changed=copy.deepcopy(contract);phrase_id=changed['note_tokens'][0]['phrase_id'];indices=[index for index,row in enumerate(changed['note_tokens']) if row['phrase_id']==phrase_id]
    assert len(indices)>3
    changed['note_tokens'][indices[-1]]['pitch']+=48
    whole,_=contract_feature_matrix(contract);other,_=contract_feature_matrix(changed);legacy,_=contract_feature_matrix(contract,phrase_aware=False);legacy_other,_=contract_feature_matrix(changed,phrase_aware=False)
    assert (whole[indices[0],:len(BASE_FEATURES)*3]==other[indices[0],:len(BASE_FEATURES)*3]).all()
    assert not (whole[indices[0],len(BASE_FEATURES)*3:]==other[indices[0],len(BASE_FEATURES)*3:]).all()
    assert (legacy[indices[0]]==legacy_other[indices[0]]).all()

def test_training_is_deterministic_and_grouped(tmp_path):
    contracts=_contracts(tmp_path);one=train_self_supervised_encoder(contracts,epochs=120);two=train_self_supervised_encoder(contracts,epochs=120);assert one['model_digest']==two['model_digest'];splits=set(one['split_by_file'].values());assert splits=={'train','validation','test'} and one['authority_granted'] is False;assert one['context']=='HIERARCHICAL_WHOLE_PHRASE' and one['phrase_feature_names']==list(PHRASE_FEATURES)

def test_training_reports_detailed_epoch_progress(tmp_path):
    contracts=_contracts(tmp_path);events=[];model=train_self_supervised_encoder(contracts,epochs=20,progress_callback=events.append)
    assert [row['epoch'] for row in events]==list(range(1,21))
    assert events==model['loss_history'] and all(row['masked_mse']>=0 for row in events)

def test_encoder_model_json_roundtrip_and_embedding(tmp_path):
    contracts=_contracts(tmp_path);model=train_self_supervised_encoder(contracts,epochs=120);path=save_encoder_model(model,tmp_path/'model.json');loaded=load_encoder_model(path);embedding=encode_contract(contracts[0],loaded);predictions=predict_masked_features(contracts[0],loaded,('duration_beats',));assert loaded['model_digest']==model['model_digest'] and embedding['dimensions']==model['hidden_size'] and embedding['authority_granted'] is False;assert len(predictions)==len(contracts[0]['note_tokens']) and set(predictions[0]['predicted'])=={'duration_beats'}

def test_masked_reconstruction_beats_mean_baseline(tmp_path):
    contracts=_contracts(tmp_path);model=train_self_supervised_encoder(contracts);evaluation=evaluate_self_supervised_encoder(contracts,model);assert evaluation['validation_improves_baseline'] and evaluation['test_improves_baseline'];assert evaluation['mutations']==0 and evaluation['authority_granted'] is False
