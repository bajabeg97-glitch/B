"""Deterministic Factory proxy holdout for Voice Director ranking.

This measures profile reconstruction, not audible hardware preference.
"""
from __future__ import annotations

import argparse,json,statistics
from collections import defaultdict
from pathlib import Path

from pa800_optimizer.intelligence.sound_fx import SoundFxIntelligence,normalize_family
from pa800_optimizer.models import NoteEvent,SoundIdentity,TrackContext
from pa800_optimizer.profiles.registry import ProfileRegistry

ROOT=Path(__file__).resolve().parents[1]


def _center(block,default):return float((block or {}).get('ideal_center',default) or default)


def evaluate(registry=None):
    registry=registry or ProfileRegistry();engine=SoundFxIntelligence(registry);rows=[];families=defaultdict(list)
    for profile in registry.profiles:
        ok,_=registry.auto_candidate_allowed(profile)
        if not ok:continue
        ident=profile['identity'];address=(ident['msb'],ident['lsb'],ident['program']);family=normalize_family(ident.get('org_family'),ident.get('sound'));role=ident.get('role') or 'SONG'
        pitch=int(round(_center(profile.get('key'),60)));velocity=int(round(_center(profile.get('velocity'),85)));duration=max(1,int(round(_center(profile.get('duration_ticks'),96))))
        notes=[NoteEvent(0,0,max(0,min(127,pitch+(i%5)-2)),max(1,min(127,velocity+(i%7)-3)),i*120,i*120+duration,i*2,i*2+1) for i in range(24)]
        ctx=TrackContext(0,0,role,SoundIdentity(None,None,None,None,family),family=family,resolution_status='HOLDOUT')
        features={'ticks_per_beat':192,'controllers':{},'pitch_bend_events':0,'aftertouch_events':0,'existing_fx':{91:[],93:[]},'level_values':{7:[],11:[]}}
        ranked=sorted(((engine._score(candidate,ctx,notes,features),candidate) for candidate in engine.by_family.get(family,[])),key=lambda x:x[0],reverse=True)
        addresses=[]
        for score,candidate in ranked:
            ci=candidate['identity'];candidate_address=(ci['msb'],ci['lsb'],ci['program'])
            if candidate_address not in addresses:addresses.append(candidate_address)
            if len(addresses)>=3:break
        row={'family':family,'source_address':address,'source_sound':ident.get('sound'),'top1':bool(addresses and addresses[0]==address),'top3':address in addresses,'ranked_addresses':addresses};rows.append(row);families[family].append(row)
    summary={}
    for family,items in sorted(families.items()):summary[family]={'profiles':len(items),'top1_accuracy':round(sum(x['top1'] for x in items)/len(items),4),'top3_accuracy':round(sum(x['top3'] for x in items)/len(items),4)}
    return {'schema':'PA800_VOICE_FACTORY_PROXY_HOLDOUT_V1','warning':'Factory profile reconstruction proxy; not hardware/audio accuracy.','profiles':len(rows),'overall_top1_accuracy':round(sum(x['top1'] for x in rows)/len(rows),4) if rows else 0,'overall_top3_accuracy':round(sum(x['top3'] for x in rows)/len(rows),4) if rows else 0,'families':summary,'rows':rows}


def main(argv=None):
    ap=argparse.ArgumentParser();ap.add_argument('--output',default=str(ROOT/'VOICE_HOLDOUT_REPORT.json'));ns=ap.parse_args(argv);result=evaluate();Path(ns.output).write_text(json.dumps(result,indent=2,ensure_ascii=False),encoding='utf-8');print(json.dumps({k:v for k,v in result.items() if k!='rows'},indent=2,ensure_ascii=False))


if __name__=='__main__':main()