"""Certify deterministic masked-event learning without granting MIDI authority."""
from __future__ import annotations
import argparse,json,math
from pathlib import Path
from pa800_optimizer.neural.event_contract import encode_neural_contract
from pa800_optimizer.neural.self_supervised_encoder import encode_contract,evaluate_self_supervised_encoder,load_encoder_model,save_encoder_model,train_self_supervised_encoder
from tools.run_neural_dataset_certification import certify as certify_dataset

ROOT=Path(__file__).resolve().parents[1]

def _cosine(left,right):
    dot=sum(a*b for a,b in zip(left,right));den=math.sqrt(sum(a*a for a in left)*sum(b*b for b in right));return dot/den if den else 1.0

def certify(output):
    output=Path(output);dataset=certify_dataset(ROOT/'NEURAL_DATASET_STRESS_3.2.0');sources=ROOT/'NEURAL_DATASET_STRESS_3.2.0'/'sources';contracts=[encode_neural_contract(path,include_source_bytes=False) for path in sorted(sources.glob('*.mid'))];first=train_self_supervised_encoder(contracts);second=train_self_supervised_encoder(contracts);evaluation=evaluate_self_supervised_encoder(contracts,first);save_encoder_model(first,output);loaded=load_encoder_model(output);embeddings={contract['source']['filename']:encode_contract(contract,loaded) for contract in contracts};original=embeddings['GTR-001_positive.mid']['embedding'];transposed=embeddings['GTR-001_transposed.mid']['embedding'];cosine=_cosine(original,transposed);split_groups={split:{contract['source_group_id'] for contract in contracts if first['split_by_file'][contract['source']['filename']]==split} for split in ('train','validation','test')};protected=[contract for contract in contracts if all(row['protected'] for row in contract['note_tokens'])];checks={'dataset_v2':dataset['pass'],'deterministic_training':first['model_digest']==second['model_digest'],'model_roundtrip':loaded['model_digest']==first['model_digest'],'non_empty_grouped_splits':all(split_groups.values()),'zero_group_leakage':not((split_groups['train']&split_groups['validation'])|(split_groups['train']&split_groups['test'])|(split_groups['validation']&split_groups['test'])),'validation_improves_baseline':evaluation['validation_improves_baseline'],'test_improves_baseline':evaluation['test_improves_baseline'],'transposition_invariance':cosine>=.999999,'protected_sources_present':len(protected)>=2,'finite_embeddings':all(all(math.isfinite(value) for value in row['embedding']) for row in embeddings.values()),'authority':first['authority_granted'] is False and evaluation['authority_granted'] is False and all(row['authority_granted'] is False for row in embeddings.values())}
    report={'schema':'PA800_NEURAL_ENCODER_CERTIFICATION_V1','release':'3.3.0-alpha1','sources':len(contracts),'unique_source_groups':len({contract['source_group_id'] for contract in contracts}),'split_groups':{key:len(value) for key,value in split_groups.items()},'model_digest':first['model_digest'],'hidden_size':first['hidden_size'],'epochs':first['epochs'],'loss_history':first['loss_history'],'evaluation':evaluation,'transposition_cosine':round(cosine,9),'protected_sources':len(protected),'checks':checks,'trained_on_synthetic_proxy':True,'trained_model':True,'production_ready':False,'mutations':0,'authority_granted':False,'pass':all(checks.values())};(ROOT/'NEURAL_ENCODER_CERTIFICATION_RESULT.json').write_text(json.dumps(report,indent=2,ensure_ascii=False)+'\n',encoding='utf-8');return report

def main(argv=None):
    parser=argparse.ArgumentParser();parser.add_argument('--output',default=str(ROOT/'NEURAL_ENCODER_MODEL_3.3.0.json'));args=parser.parse_args(argv);report=certify(args.output);print(json.dumps(report,indent=2));return 0 if report['pass'] else 1

if __name__=='__main__':raise SystemExit(main())