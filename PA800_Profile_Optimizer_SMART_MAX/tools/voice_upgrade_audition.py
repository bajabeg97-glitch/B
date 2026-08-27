"""Generate Pa800 A/B files for every evidence-eligible same-program GM upgrade."""
from __future__ import annotations

import argparse,csv,json,re,shutil
from datetime import datetime,timezone
from pathlib import Path

import mido

from pa800_optimizer.intelligence.sound_fx import normalize_family
from pa800_optimizer.profiles.registry import ProfileRegistry

ROOT=Path(__file__).resolve().parents[1]


def safe_name(text):return re.sub(r'[^A-Za-z0-9._-]+','_',text).strip('_')


def _phrase(program):
    root=36 if 32<=program<=39 else 48 if 24<=program<=31 else 60
    return [root,root+4,root+7,root+12,root+7,root+4]


def corridors(registry):
    rows=[]
    gm=[p for p in registry.profiles if p['identity'].get('msb')==121 and p['identity'].get('lsb')==0]
    for source in gm:
        si=source['identity'];sf=normalize_family(si.get('org_family'),si.get('sound'))
        candidates=[]
        for target in registry.profiles:
            ti=target['identity'];address=(ti.get('msb'),ti.get('lsb'),ti.get('program'))
            if ti.get('program')!=si.get('program') or address==(121,0,si.get('program')):continue
            if normalize_family(ti.get('org_family'),ti.get('sound'))!=sf:continue
            ok,_reason=registry.auto_candidate_allowed(target)
            if ok:candidates.append(target)
        if not candidates:continue
        candidates.sort(key=lambda p:(p.get('support',{}).get('styles',0),p.get('support',{}).get('notes',0)),reverse=True)
        rows.append((source,candidates[0]))
    return rows


def build_pair(source,target,path):
    mid=mido.MidiFile(type=1,ticks_per_beat=192);track=mido.MidiTrack();mid.tracks.append(track);ch=0
    si=source['identity'];ti=target['identity'];notes=_phrase(int(si['program']))
    track.append(mido.MetaMessage('track_name',name='VOICE UPGRADE A B',time=0));track.append(mido.MetaMessage('set_tempo',tempo=500000,time=0))
    for index,(label,ident) in enumerate((('A_GM_SOURCE',si),('B_PA800_TARGET',ti))):
        track.append(mido.MetaMessage('marker',text=label+' '+str(ident.get('sound')),time=384 if index else 0))
        track.append(mido.Message('control_change',channel=ch,control=0,value=int(ident['msb']),time=0));track.append(mido.Message('control_change',channel=ch,control=32,value=int(ident['lsb']),time=0));track.append(mido.Message('program_change',channel=ch,program=int(ident['program']),time=0))
        for note in notes:
            track.append(mido.Message('note_on',channel=ch,note=note,velocity=88,time=48));track.append(mido.Message('note_off',channel=ch,note=note,velocity=0,time=144))
    track.append(mido.MetaMessage('end_of_track',time=384));mid.save(str(path))


def generate(output):
    registry=ProfileRegistry();output=Path(output);output.mkdir(parents=True,exist_ok=True);midi_dir=output/'MIDI';midi_dir.mkdir(exist_ok=True);manifest=[];score=[]
    for source,target in corridors(registry):
        si=source['identity'];ti=target['identity'];name='%03d_%s_TO_%s.mid'%(int(si['program']),safe_name(si.get('sound','GM')),safe_name(ti.get('sound','Pa800')));build_pair(source,target,midi_dir/name)
        row={'source_sound':si.get('sound'),'source_address':'121.0.%s'%si['program'],'target_sound':ti.get('sound'),'target_address':'%s.%s.%s'%(ti['msb'],ti['lsb'],ti['program']),'family':normalize_family(si.get('org_family'),si.get('sound')),'target_grade':target.get('support',{}).get('grade'),'target_styles':target.get('support',{}).get('styles'),'target_stability':registry.profile_stability(target),'target_better_yes_no':'','character_preserved_yes_no':'','level_match_1_5':'','comments':''};score.append(row);manifest.append(dict(row,file='MIDI/'+name))
    fields=list(score[0]) if score else []
    with (output/'VOICE_UPGRADE_SCORE.csv').open('w',encoding='utf-8-sig',newline='') as stream:
        if fields:writer=csv.DictWriter(stream,fieldnames=fields);writer.writeheader();writer.writerows(score)
    (output/'VOICE_UPGRADE_MANIFEST.json').write_text(json.dumps({'schema':'PA800_VOICE_UPGRADE_AUDITION_V1','created_utc':datetime.now(timezone.utc).isoformat(),'pairs':manifest},indent=2,ensure_ascii=False),encoding='utf-8')
    (output/'READ_ME_FIRST.txt').write_text('PA800 SAFE VOICE UPGRADE A/B\n\nSvaki MIDI prvo svira GM source, zatim Pa800 target istog Program broja. Slusaj na istom SET/mixer/master stanju. Popuni CSV. AUTO nikad ne mijenja programsku klasu, RX/DNC, konfliktne adrese niti Drum Kit.\n',encoding='utf-8')
    return output


def main(argv=None):
    ap=argparse.ArgumentParser();ap.add_argument('--output',default=str(ROOT/'voice_upgrade_audition'));ns=ap.parse_args(argv);out=generate(ns.output);archive=shutil.make_archive(str(out),'zip',root_dir=out);print('AUDITION_FOLDER:',out);print('SEND_THIS_ZIP:',archive)


if __name__=='__main__':main()