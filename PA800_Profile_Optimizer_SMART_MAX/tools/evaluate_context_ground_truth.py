#!/usr/bin/env python3
"""Evaluate an optimizer report against a manually labeled context file."""
import argparse
import json
from pathlib import Path

from pa800_optimizer.analysis.context_ground_truth import evaluate_context_prediction


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('report');parser.add_argument('truth')
    parser.add_argument('--tolerance-ticks',type=int,default=192)
    parser.add_argument('--output',default='context_evaluation.json')
    args=parser.parse_args();report=json.loads(Path(args.report).read_text(encoding='utf-8'));truth=json.loads(Path(args.truth).read_text(encoding='utf-8'))
    result=evaluate_context_prediction(report,truth,args.tolerance_ticks);Path(args.output).write_text(json.dumps(result,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
    print('Context evaluation: tracks=%d accuracy=%.4f boundary_f1=%.4f pass=%s'%(result['track_function']['total'],result['track_function']['accuracy'],result['section_boundaries']['f1'],result['pass']))
    raise SystemExit(0 if result['pass'] else 1)


if __name__=='__main__':main()