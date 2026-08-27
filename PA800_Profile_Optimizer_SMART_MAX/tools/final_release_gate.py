"""Truthful final gate: local certification is distinct from physical Pa800 proof."""
from __future__ import annotations

import argparse,json
from datetime import datetime,timezone
from pathlib import Path


def _json(path):
    try:return json.loads(Path(path).read_text(encoding='utf-8-sig'))
    except Exception:return {}


def evaluate_final_gate(root,hardware_evaluation=None):
    root=Path(root);identity=_json(root/'BUILD_ID.json');factory=_json(root/'FACTORY_RELEASE_MANIFEST.json');forensic=_json(root/'NEURAL_FORENSIC_REGRESSION_RESULT.json');stress=_json(root/'COMPLETE_STRESS_RESULT.json');hardware=_json(hardware_evaluation) if hardware_evaluation else {}
    software_checks={'build_identity_present':bool(identity.get('build_id')),'factory_release_clean':factory.get('errors')==[],'complete_stress_pass':stress.get('pass') is True,'neural_forensic_pass':forensic.get('pass') is True and int(forensic.get('cases',0))>=14,'neural_authority_bounded':set((forensic.get('model_acceptance') or {}).get('allowed_outputs') or [])=={'timing','gate'} and (forensic.get('model_acceptance') or {}).get('authority_granted') is False}
    software_pass=all(software_checks.values());hardware_pass=hardware.get('pass') is True and all((hardware.get('gates') or {}).values());release_class='HARDWARE_CERTIFIED' if software_pass and hardware_pass else ('SOFTWARE_CERTIFIED_HARDWARE_PENDING' if software_pass else 'BLOCKED')
    return {'schema':'PA800_FINAL_RELEASE_GATE_V1','created_utc':datetime.now(timezone.utc).isoformat(),'pass':software_pass,'release_class':release_class,'software_checks':software_checks,'software_certified':software_pass,'hardware_status':'PASS' if hardware_pass else 'EXTERNAL_REQUIRED','hardware_auto_authority':hardware_pass,'hardware_evaluation':str(hardware_evaluation) if hardware_evaluation else None,'build_id':identity.get('build_id'),'neural_forensic_cases':forensic.get('cases')}


def main(argv=None):
    parser=argparse.ArgumentParser();parser.add_argument('--root',default=str(Path(__file__).resolve().parents[1]));parser.add_argument('--hardware-evaluation');parser.add_argument('--output',default='FINAL_RELEASE_GATE.json');args=parser.parse_args(argv);result=evaluate_final_gate(args.root,args.hardware_evaluation);Path(args.output).write_text(json.dumps(result,indent=2,ensure_ascii=False)+'\n',encoding='utf-8');print(json.dumps(result,indent=2));return 0 if result['pass'] else 1


if __name__=='__main__':raise SystemExit(main())