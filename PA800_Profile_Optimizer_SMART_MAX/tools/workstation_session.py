"""Inspect and operate a PA800 Workstation session from the command line."""
from __future__ import annotations
import argparse,json
from pa800_optimizer.workstation import WorkstationSession


def main(argv=None):
    parser=argparse.ArgumentParser();parser.add_argument('session');parser.add_argument('action',choices=['status','undo','redo','attach-audio']);parser.add_argument('--audio');args=parser.parse_args(argv);session=WorkstationSession(args.session)
    if args.action=='undo':session.undo()
    elif args.action=='redo':session.redo()
    elif args.action=='attach-audio':
        if not args.audio:parser.error('--audio is required for attach-audio')
        session.attach_audio(args.audio)
    print(json.dumps({'active_variant':session.active_variant(),'session':session.data},indent=2,ensure_ascii=False))


if __name__=='__main__':main()