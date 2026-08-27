"""Evaluate a completed Intent V3 annotation CSV and write calibration status."""
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

from pa800_optimizer.analysis.intent_ground_truth import calibration_gate,evaluate_intent_ground_truth


def load_completed_rows(path):
    with Path(path).open(encoding='utf-8-sig',newline='') as stream:raw=list(csv.DictReader(stream))
    rows=[]
    for row in raw:
        if not row.get('human_function') or not row.get('annotator'):continue
        rows.append({**row,'track':int(row['track']),'channel':int(row['channel']),'prediction_confidence':float(row['prediction_confidence'])})
    return rows


def evaluate_sheet(path):
    result=evaluate_intent_ground_truth(load_completed_rows(path));result['calibration_gate']=calibration_gate(result);return result


def main(argv=None):
    parser=argparse.ArgumentParser();parser.add_argument('csv',nargs='?',default='INSTRUMENT_INTENT_GROUND_TRUTH.csv');parser.add_argument('--output',default='INSTRUMENT_INTENT_GROUND_TRUTH_STATUS.json');args=parser.parse_args(argv);result=evaluate_sheet(args.csv) if Path(args.csv).is_file() else evaluate_intent_ground_truth([]);result['calibration_gate']=calibration_gate(result);Path(args.output).write_text(json.dumps(result,indent=2,ensure_ascii=False)+'\n',encoding='utf-8');print(json.dumps({key:value for key,value in result.items() if key not in ('fine_roles','superclasses')},indent=2));return 0 if result['status'] in ('PASS','EXTERNAL_REQUIRED') else 1


if __name__=='__main__':raise SystemExit(main())