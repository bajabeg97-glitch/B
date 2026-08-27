"""Run all Section & Narrative V3 adversarial fixtures twice."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from pa800_optimizer.understanding_cli import analyze_file


ROOT=Path(__file__).resolve().parents[1]


def evaluate(folder):
    folder=Path(folder);manifest=json.loads((folder/'SECTION_NARRATIVE_STRESS_MANIFEST.json').read_text(encoding='utf-8'));rows=[]
    for case in manifest['cases']:
        first=analyze_file(folder/case['file'],case['content_type']);second=analyze_file(folder/case['file'],case['content_type']);section=first.get('section_narrative',{});checks={'schema':section.get('schema')=='PA800_SECTION_NARRATIVE_V3','analysis_only':section.get('analyzer_only') is True and section.get('authority_granted') is False and section.get('mutations')==0,'no_apply':(section.get('automation') or {}).get('applied_actions')==0,'deterministic':section.get('digest')==second.get('section_narrative',{}).get('digest'),'has_sections':int((section.get('summary') or {}).get('sections',0))>0,'intent_integration':first.get('instrument_intent',{}).get('section_model',{}).get('digest')==section.get('digest')}
        rows.append({'scenario_id':case['scenario_id'],'polarity':case['polarity'],'file':case['file'],'digest':section.get('digest'),'labels':[row.get('label') for row in section.get('sections',[])],'transitions':[row.get('relationship') for row in section.get('transitions',[])],'summary':section.get('summary',{}),'checks':checks,'pass':all(checks.values())})
    pairs={}
    for row in rows:pairs.setdefault(row['scenario_id'],{})[row['polarity']]=row['digest']
    separated={key:set(value)=={'positive','negative'} and value['positive']!=value['negative'] for key,value in pairs.items()};failures=[row for row in rows if not row['pass']]
    return {'schema':'PA800_SECTION_NARRATIVE_STRESS_RESULT_V1','fixture_schema':manifest.get('schema'),'scenario_count':len(pairs),'midi_case_count':len(rows),'passed_cases':len(rows)-len(failures),'failed_cases':len(failures),'pair_separation_passed':sum(separated.values()),'pair_separation_total':len(separated),'all_pairs_separated':all(separated.values()),'mutations':0,'authority_granted':False,'rows':rows,'pass':len(rows)==24 and not failures and len(separated)==12 and all(separated.values())}


def main(argv=None):
    parser=argparse.ArgumentParser();parser.add_argument('--folder',default=str(ROOT/'SECTION_NARRATIVE_STRESS_2.5.3'));parser.add_argument('--output',default=str(ROOT/'SECTION_NARRATIVE_STRESS_RESULT.json'));args=parser.parse_args(argv);report=evaluate(args.folder);Path(args.output).write_text(json.dumps(report,indent=2,ensure_ascii=False)+'\n',encoding='utf-8');print(json.dumps({key:value for key,value in report.items() if key!='rows'},indent=2));return 0 if report['pass'] else 1


if __name__=='__main__':raise SystemExit(main())