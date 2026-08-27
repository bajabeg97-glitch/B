#!/usr/bin/env python3
"""Create JSON/CSV Factory-usage dashboard data from optimizer reports."""
import argparse
from pathlib import Path

from pa800_optimizer.analysis.factory_usage_batch import load_and_aggregate,write_batch_outputs


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('reports',nargs='+',help='Optimizer JSON report files')
    parser.add_argument('--json',default='factory_usage_batch.json',help='Aggregate JSON output')
    parser.add_argument('--csv',default='factory_usage_by_family.csv',help='Per-family CSV output')
    args=parser.parse_args();result=load_and_aggregate(args.reports);write_batch_outputs(result,args.json,args.csv)
    print('Factory usage: files=%d notes=%d pass=%s JSON=%s CSV=%s'%(result['files_total'],result['notes_total'],result['pass'],Path(args.json),Path(args.csv)))
    raise SystemExit(0 if result['pass'] else 1)


if __name__=='__main__':main()