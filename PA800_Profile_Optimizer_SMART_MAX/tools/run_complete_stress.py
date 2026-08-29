"""Run the release suite with resumable public-function execution tracing."""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

try:
    from tools.public_api_stress import ROOT,build_manifest
except ModuleNotFoundError:
    project_root=Path(__file__).resolve().parents[1]
    if str(project_root) not in sys.path:
        sys.path.insert(0,str(project_root))
    from tools.public_api_stress import ROOT,build_manifest


# Only tests that consume COMPLETE_STRESS_RESULT.json / release_audit pass.
# API-surface tests in test_complete_stress_matrix.py must run in the producer
# so DIRECT_TEST_REFERENCE functions actually appear in the execution trace.
META_RELEASE_TESTS={'tests/test_release_integrity.py'}

def _tests():
    # Stress produces the evidence consumed by meta release tests. Running those
    # inside the producer is circular, so they execute only after finalization.
    return [line.strip() for line in (ROOT/'RELEASE_TESTS.txt').read_text(encoding='utf-8').splitlines() if line.strip() and not line.startswith('#') and line.strip() not in META_RELEASE_TESTS]


def _run_tests(tests):
    with tempfile.TemporaryDirectory(prefix='pa800-complete-stress-') as tmp:
        trace=Path(tmp)/'trace.json'
        env={**os.environ,'PA800_PUBLIC_API_TRACE_OUT':str(trace),'PA800_COMPLETE_STRESS_RUNNING':'1','PYTHONPATH':os.pathsep.join([str(ROOT/'test_support'),str(ROOT),os.environ.get('PYTHONPATH','')])}
        completed=subprocess.run([sys.executable,'-m','pytest','-q','-p','tools.public_api_trace_plugin','--basetemp',str(Path(tmp)/'pytest'),*tests],cwd=ROOT,text=True,capture_output=True,env=env)
        execution=json.loads(trace.read_text(encoding='utf-8')) if trace.is_file() else {'hits':[],'pytest_exitstatus':completed.returncode}
    return {'tests':tests,'returncode':completed.returncode,'stdout':completed.stdout,'stderr':completed.stderr,'hits':sorted(set(execution.get('hits',[])))}


def _final_report(manifest,shards):
    hits=set();stdout=[];stderr=[];pytest_returncode=0
    for shard in shards:
        hits.update(shard.get('hits',[]));stdout.append(shard.get('stdout',''));stderr.append(shard.get('stderr',''))
        if int(shard.get('returncode',0))!=0:pytest_returncode=int(shard.get('returncode',1))
    functions=[]
    for row in manifest['functions']:
        key=row['module']+':'+row['qualname'];dynamic=key in hits;accounted=dynamic or row['coverage_mode'] in ('CLI_CONTRACT','GUI_EXTERNAL','HARDWARE_EXTERNAL','PC_EXTERNAL','RELEASE_CONTRACT')
        functions.append({**row,'dynamic_hit':dynamic,'accounted':accounted})
    dynamic_hits=sum(row['dynamic_hit'] for row in functions);accounted=sum(row['accounted'] for row in functions);total=len(functions);ratio=dynamic_hits/max(1,total)
    return {'schema':'PA800_COMPLETE_STRESS_RESULT_V2','execution_mode':'RESUMABLE_SHARDED_TRACE','pytest_returncode':pytest_returncode,'pytest_stdout':'\n'.join(stdout),'pytest_stderr':'\n'.join(stderr),'inventory':manifest['inventory'],'dynamic_hits':dynamic_hits,'dynamic_hit_ratio':round(ratio,4),'accounted_functions':accounted,'unaccounted_functions':total-accounted,'functions':functions,'shards_completed':len(shards),'pass':pytest_returncode==0 and accounted==total and ratio>=.50}


def run(output):
    manifest=build_manifest();result=_run_tests(_tests());report=_final_report(manifest,[result]);Path(output).write_text(json.dumps(report,indent=2,ensure_ascii=False)+'\n',encoding='utf-8');return report


def run_shard(state_path,shard_index,shard_count):
    tests=_tests();shard_tests=[test for index,test in enumerate(tests) if index%shard_count==shard_index]
    state_path=Path(state_path)
    state=json.loads(state_path.read_text(encoding='utf-8')) if state_path.is_file() else {'schema':'PA800_COMPLETE_STRESS_STATE_V1','shard_count':shard_count,'shards':{}}
    if int(state.get('shard_count',shard_count))!=shard_count:raise ValueError('Stress state shard_count mismatch')
    result=_run_tests(shard_tests);state['shards'][str(shard_index)]=result
    state_path.write_text(json.dumps(state,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
    return result


def finalize(state_path,output):
    manifest=build_manifest();state=json.loads(Path(state_path).read_text(encoding='utf-8'));count=int(state['shard_count']);missing=[index for index in range(count) if str(index) not in state.get('shards',{})]
    if missing:raise RuntimeError('Missing stress shards: %s'%missing)
    shards=[state['shards'][str(index)] for index in range(count)];report=_final_report(manifest,shards);Path(output).write_text(json.dumps(report,indent=2,ensure_ascii=False)+'\n',encoding='utf-8');return report


def main(argv=None):
    parser=argparse.ArgumentParser();parser.add_argument('--output',default=str(ROOT/'COMPLETE_STRESS_RESULT.json'));parser.add_argument('--state',default=str(ROOT/'COMPLETE_STRESS_STATE.json'));parser.add_argument('--shard-index',type=int);parser.add_argument('--shard-count',type=int,default=8);parser.add_argument('--finalize',action='store_true');args=parser.parse_args(argv)
    if args.finalize:report=finalize(args.state,args.output)
    elif args.shard_index is not None:
        if not 0<=args.shard_index<args.shard_count:parser.error('shard-index must be in range')
        shard=run_shard(args.state,args.shard_index,args.shard_count);print(json.dumps({'shard':args.shard_index,'tests':len(shard['tests']),'returncode':shard['returncode'],'hits':len(shard['hits'])},indent=2));return 0 if shard['returncode']==0 else 1
    else:report=run(args.output)
    print(json.dumps({key:value for key,value in report.items() if key not in ('functions','pytest_stdout','pytest_stderr')},indent=2));return 0 if report['pass'] else 1


if __name__=='__main__':raise SystemExit(main())
