"""Audit a neural dataset manifest without training or mutating MIDI."""
from __future__ import annotations
import argparse,json
from pa800_optimizer.neural.dataset_forge import audit_dataset_manifest

def main(argv=None):
    parser=argparse.ArgumentParser();parser.add_argument('manifest');args=parser.parse_args(argv);report=audit_dataset_manifest(args.manifest);print(json.dumps(report,indent=2));return 0 if report['pass'] else 1

if __name__=='__main__':raise SystemExit(main())