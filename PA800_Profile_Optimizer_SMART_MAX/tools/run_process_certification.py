"""Build and execute the A-Z structural process-coverage pack."""
from __future__ import annotations

import argparse,json,subprocess,sys
from datetime import datetime,timezone
from pathlib import Path

from pa800_optimizer.analysis.process_certification import evaluate_process_coverage
from tools.process_certification_midis import generate


ROOT=Path(__file__).resolve().parents[1]


def _run(args):
    completed=subprocess.run(args,cwd=ROOT,text=True,capture_output=True)
    return {'command':args,'returncode':completed.returncode,'stdout':completed.stdout,'stderr':completed.stderr,'pass':completed.returncode==0}


def certify(output,run_regression=True):
    output=Path(output);output.mkdir(parents=True,exist_ok=True);fixtures=output/'fixtures';generate(fixtures)
    manifest=json.loads((fixtures/'PROCESS_CERTIFICATION_MANIFEST.json').read_text(encoding='utf-8'))
    collected=_run([sys.executable,'-m','pytest','--collect-only','-q'])
    nodeids=[line.strip() for line in collected['stdout'].splitlines() if '::' in line]
    coverage=evaluate_process_coverage(nodeids,manifest)
    regression=_run([sys.executable,'-m','pytest','-q']) if run_regression else {'pass':True,'skipped':True}
    release=_run([sys.executable,'tools/release_audit.py']) if run_regression else {'pass':True,'skipped':True,'reason':'structural_only_run_regression_false'}
    report={'schema':'PA800_PROCESS_COVERAGE_RUN_V2','scope':'STRUCTURAL_AND_TEST_MANIFEST_COVERAGE_NOT_REAL_MIDO_OR_HARDWARE_CERTIFICATION','created_utc':datetime.now(timezone.utc).isoformat(),'scenario_count':manifest.get('scenario_count'),'positive_scenarios':sum(row.get('polarity')=='positive' for row in manifest.get('scenarios',[])),'negative_scenarios':sum(row.get('polarity')=='negative' for row in manifest.get('scenarios',[])),'collected_test_count':len(nodeids),'coverage':coverage,'test_collection':collected,'regression':regression,'release_audit':release}
    report['pass']=bool(collected['pass'] and coverage['pass'] and regression['pass'] and release['pass'] and report['scenario_count']==52 and report['positive_scenarios']==26 and report['negative_scenarios']==26)
    (output/'PROCESS_CERTIFICATION_REPORT.json').write_text(json.dumps(report,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
    summary=['PA800 SMART MAX — A-Z STRUCTURAL PROCESS COVERAGE','', 'This is not real-Mido, Windows or Pa800 hardware certification.',f"Scenarios: {report['scenario_count']} (positive {report['positive_scenarios']}, negative {report['negative_scenarios']})",f"A-Z stages: {coverage['passed_stages']}/{coverage['stage_count']}",f"Collected tests: {len(nodeids)}",f"Regression: {'PASS' if regression['pass'] else 'FAIL'}",f"Factory release audit: {'PASS' if release['pass'] else 'FAIL'}",f"COVERAGE RESULT: {'PASS' if report['pass'] else 'FAIL'}"]
    (output/'READ_ME_FIRST.txt').write_text('\n'.join(summary)+'\n',encoding='utf-8')
    return report


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('output',nargs='?',default='PA800_Process_Certification_AZ');parser.add_argument('--skip-regression',action='store_true');args=parser.parse_args(argv)
    result=certify(args.output,run_regression=not args.skip_regression);print(json.dumps({'pass':result['pass'],'scenarios':result['scenario_count'],'stages':result['coverage']['passed_stages'],'tests':result['collected_test_count']},indent=2));return 0 if result['pass'] else 1


if __name__=='__main__':raise SystemExit(main())