"""Evaluate every canonical Intent V3 MIDI fixture through the real analyzer."""
from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

from pa800_optimizer.understanding_cli import analyze_file


ROOT=Path(__file__).resolve().parents[1]


def evaluate(folder):
    folder=Path(folder);manifest=json.loads((folder/'INSTRUMENT_INTENT_STRESS_MANIFEST.json').read_text(encoding='utf-8'));rows=[]
    for case in manifest.get('cases',[]):
        path=folder/case['file'];first=analyze_file(path,'auto');second=analyze_file(path,'auto');intent=first.get('instrument_intent',{});summary=intent.get('summary',{})
        checks={
            'schema':intent.get('schema')=='PA800_INSTRUMENT_INTENT_V3',
            'analysis_only':intent.get('analyzer_only') is True and intent.get('authority_granted') is False and int(intent.get('mutations',-1))==0,
            'no_automation_apply':int((intent.get('automation') or {}).get('applied_actions',-1))==0,
            'event_attribution':float(summary.get('event_attribution_percent',0))==100.0,
            'deterministic_digest':intent.get('intent_digest')==second.get('instrument_intent',{}).get('intent_digest'),
            'has_notes':int(summary.get('notes',0))>0,
        }
        rows.append({'scenario_id':case['scenario_id'],'polarity':case['polarity'],'file':case['file'],'intent_digest':intent.get('intent_digest'),'track_labels':[row.get('label') for row in intent.get('track_intents',[])],'unknown_tracks':summary.get('unknown_tracks'),'checks':checks,'pass':all(checks.values())})
    pair_digests={}
    for row in rows:pair_digests.setdefault(row['scenario_id'],{})[row['polarity']]=row['intent_digest']
    pair_separation={key:value.get('positive')!=value.get('negative') and set(value)=={'positive','negative'} for key,value in pair_digests.items()}
    failures=[row for row in rows if not row['pass']];categories=Counter(row['scenario_id'].split('-')[0] for row in rows)
    report={'schema':'PA800_INSTRUMENT_INTENT_STRESS_RESULT_V1','fixture_schema':manifest.get('schema'),'scenario_count':manifest.get('scenario_count'),'midi_case_count':len(rows),'category_case_counts':dict(sorted(categories.items())),'passed_cases':len(rows)-len(failures),'failed_cases':len(failures),'pair_separation_passed':sum(pair_separation.values()),'pair_separation_total':len(pair_separation),'all_pairs_separated':bool(pair_separation) and all(pair_separation.values()),'mutations':0,'authority_granted':False,'rows':rows,'pass':len(rows)==110 and not failures and len(pair_separation)==55 and all(pair_separation.values())}
    return report


def main(argv=None):
    parser=argparse.ArgumentParser();parser.add_argument('--folder',default=str(ROOT/'INSTRUMENT_INTENT_STRESS_2.5.0'));parser.add_argument('--output',default=str(ROOT/'INSTRUMENT_INTENT_STRESS_RESULT.json'));args=parser.parse_args(argv);report=evaluate(args.folder);Path(args.output).write_text(json.dumps(report,indent=2,ensure_ascii=False)+'\n',encoding='utf-8');print(json.dumps({key:value for key,value in report.items() if key!='rows'},indent=2));return 0 if report['pass'] else 1


if __name__=='__main__':raise SystemExit(main())