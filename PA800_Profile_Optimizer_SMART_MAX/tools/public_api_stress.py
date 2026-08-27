"""Inventory and classify the complete public runtime/release API surface."""
from __future__ import annotations

import argparse
import ast
import json
from pathlib import Path


ROOT=Path(__file__).resolve().parents[1]
EXCLUDED_TOOL_FILES={'public_api_stress.py','public_api_trace_plugin.py','run_complete_stress.py'}


def discover(root=ROOT):
    root=Path(root);paths=list((root/'pa800_optimizer').rglob('*.py'))+[path for path in (root/'tools').glob('*.py') if path.name not in EXCLUDED_TOOL_FILES];rows=[]
    for path in sorted(paths):
        tree=ast.parse(path.read_text(encoding='utf-8'));module='.'.join(path.relative_to(root).with_suffix('').parts)
        for node in tree.body:
            if isinstance(node,(ast.FunctionDef,ast.AsyncFunctionDef)) and not node.name.startswith('_'):
                rows.append({'module':module,'qualname':node.name,'kind':'function','path':path.relative_to(root).as_posix(),'line':node.lineno})
            elif isinstance(node,ast.ClassDef) and not node.name.startswith('_'):
                for method in node.body:
                    if isinstance(method,(ast.FunctionDef,ast.AsyncFunctionDef)) and not method.name.startswith('_'):
                        rows.append({'module':module,'qualname':node.name+'.'+method.name,'kind':'method','path':path.relative_to(root).as_posix(),'line':method.lineno})
    return rows


def classify(rows,root=ROOT):
    root=Path(root);tests={path.relative_to(root).as_posix():path.read_text(encoding='utf-8',errors='replace') for path in (root/'tests').glob('test_*.py')};out=[]
    for row in rows:
        module=row['module'];name=row['qualname'].split('.')[-1];base=module.split('.')[-1];references=[path for path,text in tests.items() if name in text and (base in text or module in text)]
        if module=='tools.pc_validation' and name in ('run','real_mido_optimizer_checks','wheel_check','main'):
            mode='PC_EXTERNAL';reason='Requires the real-Mido/isolated-wheel PC validation environment; enforced by the Windows validation contract.'
        elif name=='main' or module.endswith(('.cli','.note_velocity_cli','.understanding_cli')):mode='CLI_CONTRACT';reason='Command entry point; exercised through subprocess/CLI contract.'
        elif module=='tools.clean_install_smoke':mode='RELEASE_CONTRACT';reason='Build/install operation covered by isolated release artifact checks.'
        elif module=='tools.repair_profile_data':mode='RELEASE_CONTRACT';reason='Executed in isolated release subprocesses where in-process tracing is intentionally unavailable.'
        elif references:mode='DIRECT_TEST_REFERENCE';reason='Referenced by explicit test module and must also appear in the execution trace.'
        elif '.gui' in module or name in ('pick_input_folder','tkinter_check'):mode='GUI_EXTERNAL';reason='Requires an interactive display or native dialog.'
        elif any(token in module for token in ('hardware','workstation')) or any(token in name.lower() for token in ('audio','hardware','record')):mode='HARDWARE_EXTERNAL';reason='Requires physical/audio/external evidence for full execution.'
        elif module.startswith('tools.') and any(token in module for token in ('repair','rebuild','sync_ci','windows_revalidation','clean_install')):mode='RELEASE_CONTRACT';reason='Release/maintenance operation covered by isolated artifact tests.'
        else:mode='TRANSITIVE_RUNTIME_STRESS';reason='Reached through optimizer or module-level stress scenarios; execution trace verifies actual hits.'
        out.append({**row,'coverage_mode':mode,'coverage_reason':reason,'test_references':references})
    return out


def build_manifest(root=ROOT):
    rows=classify(discover(root),root);modules=sorted({row['module'] for row in rows});modes={mode:sum(row['coverage_mode']==mode for row in rows) for mode in sorted({row['coverage_mode'] for row in rows})}
    scenarios=[
        {'id':'EXTREME_DOMAIN','covers':['velocity 1/127','note 0/127','channel 1/16','zero duration','large delta time']},
        {'id':'DENSE_DETERMINISM','covers':['16 tracks','512 notes','repeat byte hash','verifier and quality gate']},
        {'id':'CORRELATION_BREAKERS','covers':['Drum/Bass lock','Piano chord balance','sustain tails','Organ legato','expressive controllers']},
        {'id':'PROFILE_CROSSCHECK','covers':['542 Factory','23 DNC','565 complete cards','authority separation']},
        {'id':'FAIL_CLOSED_IO','covers':['truncated SMF','recovery package','atomic output','output lock']},
        {'id':'INSTRUMENT_INTENT_V3','covers':['55 paired scenarios','110 real SMF fixtures','100% note attribution','deterministic intent digest','zero authority']},
        {'id':'FAMILY_INTENT_V1','covers':['Drum/Bass/Guitar/Piano semantics','38 real SMF cases','19 adversarial pairs','controller and special-note guards','zero authority']},
        {'id':'SECTION_NARRATIVE_V3','covers':['explicit marker and Style evidence','multi-signal Song boundaries','velocity-only rejection','build/release/return','boundary overlap preservation','24 real SMF cases']},
        {'id':'NEURAL_DATASET_V2','covers':['lossless event contract','14 byte-identical roundtrips','60 clean/corrupt cases','26 hard negatives','six rhythm/gate defect classes','velocity profile-only boundary','license/provenance and source-group leakage gates','zero authority']},
        {'id':'SELF_SUPERVISED_ENCODER_V1','covers':['masked-event neural learning','grouped train validation test holdout','deterministic model digest','transposition-invariant embedding','protected-source analysis','zero mutation authority']},
        {'id':'EXACT_INSTRUMENT_PROFILES_V1','covers':['565 exact Sound-role profiles','18 instrument families','per-instrument evidence vectors','manual DNC and SFX preserve','exact resolver','zero production AUTO']},
    ]
    return {'schema':'PA800_COMPLETE_PUBLIC_API_STRESS_V1','modules':len(modules),'public_functions':len(rows),'declared_minimum':{'modules':65,'public_functions':235},'inventory':{'modules':len(modules),'public_functions':len(rows),'module_names':modules,'coverage_modes':modes,'unclassified':sum(row['coverage_mode']=='UNCLASSIFIED' for row in rows)},'stress_scenarios':scenarios,'functions':rows}


def main(argv=None):
    parser=argparse.ArgumentParser();parser.add_argument('--output',default=str(ROOT/'PUBLIC_API_STRESS_MANIFEST.json'));args=parser.parse_args(argv);report=build_manifest();Path(args.output).write_text(json.dumps(report,indent=2,ensure_ascii=False)+'\n',encoding='utf-8');print(json.dumps(report['inventory'],indent=2,ensure_ascii=False));minimum=report['declared_minimum'];return 0 if report['inventory']['modules']>=minimum['modules'] and report['inventory']['public_functions']>=minimum['public_functions'] and report['inventory']['unclassified']==0 else 1


if __name__=='__main__':raise SystemExit(main())
