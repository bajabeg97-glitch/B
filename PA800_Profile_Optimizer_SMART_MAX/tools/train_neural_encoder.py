"""Train the analyzer-only encoder with interactive selection and session logs."""
from __future__ import annotations

import argparse
from datetime import datetime,timezone
import json
from pathlib import Path

from pa800_optimizer.neural.training_audit import audit_training_folder,public_training_audit,render_training_audit
from pa800_optimizer.neural.self_supervised_encoder import (
    finalize_encoder_acceptance,
    save_encoder_model,
    train_self_supervised_encoder,
)


def _utc():
    return datetime.now(timezone.utc).isoformat()


def _pick_folder():
    import tkinter as tk
    from tkinter import filedialog
    root=tk.Tk();root.withdraw()
    try:return filedialog.askdirectory(title='Odaberi licencirani MIDI/KAR folder za trening')
    finally:root.destroy()


class _TrainingLog:
    def __init__(self,folder):
        stamp=datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S_UTC')
        self.path=Path(folder)/('TRAIN_NEURAL_ENCODER_'+stamp+'.log')
        self.path.parent.mkdir(parents=True,exist_ok=True)

    def emit(self,event,**details):
        line='%s | %s | %s'%(_utc(),event,json.dumps(details,ensure_ascii=False,sort_keys=True,default=str))
        print(line,flush=True)
        with self.path.open('a',encoding='utf-8') as stream:stream.write(line+'\n')


def main(argv=None):
    parser=argparse.ArgumentParser()
    parser.add_argument('input_folder',nargs='?')
    parser.add_argument('--pick-folder',action='store_true')
    parser.add_argument('--output',required=True)
    parser.add_argument('--license',default='USER_PROVIDED_UNVERIFIED')
    parser.add_argument('--provenance',default='SELECTED_FOLDER_RECURSIVE')
    parser.add_argument('--corpus-kind',choices=('USER_PROVIDED','LICENSED_REAL','SYNTHETIC_PROXY'),default='USER_PROVIDED')
    parser.add_argument('--epochs',type=int,default=450)
    parser.add_argument('--hidden-size',type=int,default=24)
    parser.add_argument('--learning-rate',type=float,default=.035)
    parser.add_argument('--mask-rate',type=float,default=.35)
    parser.add_argument('--training-profile',choices=('BALANCED','MAX'),default='BALANCED')
    parser.add_argument('--log-dir',default='training_logs')
    parser.add_argument('--audit-only',action='store_true')
    parser.add_argument('--allow-active-overwrite',action='store_true')
    args=parser.parse_args(argv)
    folder=_pick_folder() if args.pick_folder else args.input_folder
    if not folder:raise SystemExit('Training folder was not selected')
    source=Path(folder)
    if not source.is_dir():raise SystemExit('Training folder does not exist: '+str(source))
    output=Path(args.output);output.parent.mkdir(parents=True,exist_ok=True);log=_TrainingLog(args.log_dir)
    active=(Path(__file__).resolve().parents[1]/'models'/'encoder.json').resolve()
    if not args.audit_only and output.resolve()==active and not args.allow_active_overwrite:raise SystemExit('Active neural model is immutable during training; write a candidate and activate it explicitly')
    try:
        audit=audit_training_folder(source,include_contracts=True);print(render_training_audit(audit),end='',flush=True)
        audit_path=log.path.with_suffix('.audit.json');audit_path.write_text(json.dumps(public_training_audit(audit),indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
        log.emit('DATASET_AUDIT',pass_=audit['pass'],discovered=audit['discovered_files'],accepted=audit['accepted_files'],rejected=audit['rejected_files'],splits=audit['splits'],group_split_leakage=audit['group_split_leakage'],audit=str(audit_path),audit_digest=audit['audit_digest'])
        if args.audit_only:return 0 if audit['pass'] else 2
        if not audit['pass']:raise SystemExit('Training folder audit failed; see detailed rejection reasons above')
        contracts=audit['_contracts'];paths=audit['accepted']
        if not 50<=args.epochs<=5000:raise ValueError('epochs must be between 50 and 5000')
        if not 8<=args.hidden_size<=128:raise ValueError('hidden-size must be between 8 and 128')
        if not 0.05<=args.mask_rate<=0.80:raise ValueError('mask-rate must be between 0.05 and 0.80')
        total_notes=sum(int(row.get('notes',0)) for row in paths);split_notes={split:sum(int(row.get('notes',0)) for row in paths if row.get('split')==split) for split in ('train','validation','test')}
        log.emit('TRAIN_START',training_profile=args.training_profile,input_folder=str(source.resolve()),sources=len(paths),total_notes=total_notes,split_notes=split_notes,epochs=args.epochs,hidden_size=args.hidden_size,input_features=51,base_output_features=11,phrase_features=18,context='HIERARCHICAL_WHOLE_PHRASE',maximum_phrase_bars=8,learning_rate=args.learning_rate,mask_rate=args.mask_rate,velocity_neural_input=False,velocity_neural_output=False,output=str(output),corpus_kind=args.corpus_kind,license=args.license,provenance=args.provenance,audit_digest=audit['audit_digest'])
        for index,(row,contract) in enumerate(zip(paths,contracts),1):log.emit('SOURCE_ENCODED',index=index,total=len(paths),file=row['file'],notes=row['notes'],source_group_id=contract.get('source_group_id'),split=row['split'])
        model=train_self_supervised_encoder(contracts,hidden_size=args.hidden_size,epochs=args.epochs,learning_rate=args.learning_rate,mask_rate=args.mask_rate,progress_callback=lambda row:log.emit('EPOCH',**row))
        log.emit('MODEL_CONTRACT',feature_names=model['feature_names'],context=model['context'],input_width=len(model['x_mean']),output_width=len(model['y_mean']),hidden_size=model['hidden_size'],velocity_isolated=True)
        model['license']=args.license;model['provenance']=args.provenance;model['trained_on_synthetic_proxy']=args.corpus_kind=='SYNTHETIC_PROXY'
        model,acceptance,evaluation=finalize_encoder_acceptance(contracts,model,audit);save_encoder_model(model,output);passed=acceptance['pass']
        result={'schema':'PA800_USER_TRAINING_RESULT_V1','created_utc':_utc(),'pass':passed,'training_profile':args.training_profile,'epochs':args.epochs,'hidden_size':args.hidden_size,'mask_rate':args.mask_rate,'total_notes':total_notes,'model':str(output),'model_digest':model['model_digest'],'sources':len(paths),'split_sources':{'train':model['training_sources'],'validation':model['validation_sources'],'test':model['test_sources']},'split_notes':split_notes,'loss_history':model['loss_history'],'evaluation':evaluation,'acceptance':acceptance,'corpus_kind':args.corpus_kind,'production_ready':bool(acceptance['pass']),'authority_granted':False,'dataset_audit':str(audit_path),'dataset_audit_digest':audit['audit_digest'],'rejected_sources':audit['rejected_files'],'log':str(log.path)}
        result_path=log.path.with_suffix('.result.json');result_path.write_text(json.dumps(result,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
        log.emit('EVALUATION',**evaluation['metrics']);log.emit('MODEL_ACCEPTANCE',**acceptance);log.emit('TRAIN_COMPLETE',pass_=passed,model=str(output),model_digest=model['model_digest'],result=str(result_path),authority_granted=False)
        print(json.dumps(result,indent=2,ensure_ascii=False));return 0 if passed else 1
    except Exception as exc:
        log.emit('TRAIN_FAILED',error=repr(exc));raise


if __name__=='__main__':raise SystemExit(main())
