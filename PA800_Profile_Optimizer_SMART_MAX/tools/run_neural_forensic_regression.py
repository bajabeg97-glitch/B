"""Run accepted neural timing/gate application across the certified corpus."""
from __future__ import annotations

import argparse,json,tempfile
from datetime import datetime,timezone
from pathlib import Path

from pa800_optimizer.analysis.neural_forensics import audit_neural_application
from pa800_optimizer.config import OptimizeConfig
from pa800_optimizer.neural.self_supervised_encoder import load_encoder_model,encoder_runtime_admission
from pa800_optimizer.optimizer import Optimizer
from tools.run_neural_dataset_certification import certify


def _config(model):
    cfg=OptimizeConfig.for_mode('natural');cfg.content_type='song';cfg.autopilot=False;cfg.enable_velocity=False;cfg.enable_velocity_conductor=False;cfg.enable_gate=False;cfg.enable_sound_kit_selector=False;cfg.enable_fx_intelligence=False;cfg.enable_articulation_director=False;cfg.enable_performance_director=True;cfg.apply_performance_director=False;cfg.enable_mix_fx_director=False;cfg.enable_timing=True;cfg.timing_strength=1.0;cfg.apply_trained_rhythm_model=True;cfg.trained_rhythm_model_path=str(model);cfg.trained_rhythm_only=True
    return cfg


def run(output):
    output=Path(output);rows=[]
    with tempfile.TemporaryDirectory(prefix='pa800-neural-forensic-') as temporary:
        root=Path(temporary);certify(root/'dataset');sources=sorted((root/'dataset'/'sources').glob('*.mid'))
        model_path=Path(__file__).resolve().parents[1]/'models'/'encoder.json'
        model=load_encoder_model(model_path,require_accepted=True);acceptance=model.get('acceptance') or {};evaluation=model.get('evaluation') or {};admission=encoder_runtime_admission(model)
        if not admission.get('proposal_allowed'):raise RuntimeError('Bundled forensic encoder is not runtime-admitted: '+repr(admission))
        optimizer=Optimizer(_config(model_path))
        for source in sources:
            target=root/'outputs'/source.name;target.parent.mkdir(parents=True,exist_ok=True);report=optimizer.optimize(source,target);audit=audit_neural_application(source,target,report);rows.append({'file':source.name,'pass':audit['pass'],'changes':len(report.changes),'timing_changes':sum(row.kind=='timing' for row in report.changes),'gate_changes':sum(row.kind=='gate' for row in report.changes),'audit':audit})
    result={'schema':'PA800_NEURAL_FORENSIC_REGRESSION_V2','created_utc':datetime.now(timezone.utc).isoformat(),'pass':bool(rows) and all(row['pass'] for row in rows),'cases':len(rows),'changed_cases':sum(row['changes']>0 for row in rows),'timing_changes':sum(row['timing_changes'] for row in rows),'gate_changes':sum(row['gate_changes'] for row in rows),'model_acceptance':acceptance,'runtime_admission':admission,'evaluation':evaluation,'rows':rows}
    output.write_text(json.dumps(result,indent=2,ensure_ascii=False)+'\n',encoding='utf-8');return result


def main(argv=None):
    parser=argparse.ArgumentParser();parser.add_argument('--output',default='NEURAL_FORENSIC_REGRESSION_RESULT.json');args=parser.parse_args(argv);result=run(args.output);print(json.dumps({key:value for key,value in result.items() if key!='rows'},indent=2));return 0 if result['pass'] else 1


if __name__=='__main__':raise SystemExit(main())