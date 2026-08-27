"""Generate adversarial real-SMF fixtures for Section & Narrative V3."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import mido


ROOT=Path(__file__).resolve().parents[1]
TPB=192
BAR=TPB*4
SCENARIOS=[
    ('SEC3-001','explicit chorus marker versus unrelated text'),
    ('SEC3-002','layer build versus velocity-only loudness'),
    ('SEC3-003','repeated chorus material versus accidental dense bar'),
    ('SEC3-004','one-bar break versus quiet continuing pattern'),
    ('SEC3-005','pickup into marked verse versus unmarked opening'),
    ('SEC3-006','note overlap across boundary versus completed tail'),
    ('SEC3-007','multi-signal contrast versus transposition-only change'),
    ('SEC3-008','harmonic-rhythm build versus harmony-only change'),
    ('SEC3-009','return of opening material versus one-way development'),
    ('SEC3-010','velocity-only false build rejection'),
    ('SEC3-011','explicit ending marker versus generic text'),
    ('SEC3-012','serialized Style Element/CV versus unlabeled Style'),
]


def _notes(start_bar,end_bar,pitches=(60,),subdivisions=(0,),velocity=80,duration=96):
    rows=[]
    for bar in range(start_bar,end_bar):
        for sub in subdivisions:
            start=bar*BAR+int(sub*BAR/16);pitch=pitches[(bar+sub)%len(pitches)];vel=velocity(bar,sub) if callable(velocity) else velocity;rows.append((start,duration,pitch,vel))
    return rows


def _track(name,channel,notes,program=0,msb=0,lsb=0,markers=()):
    track=mido.MidiTrack();track.extend([mido.MetaMessage('track_name',name=name,time=0),mido.Message('control_change',channel=channel,control=0,value=msb,time=0),mido.Message('control_change',channel=channel,control=32,value=lsb,time=0),mido.Message('program_change',channel=channel,program=program,time=0)]);events=[]
    for start,duration,pitch,velocity in notes:
        events.extend([(start,2,mido.Message('note_on',channel=channel,note=pitch,velocity=velocity,time=0)),(start+max(1,duration),0,mido.Message('note_off',channel=channel,note=pitch,velocity=0,time=0))])
    for tick,kind,text in markers:events.append((tick,1,mido.MetaMessage(kind,text=text,time=0)))
    last=0
    for tick,_order,msg in sorted(events,key=lambda row:(row[0],row[1],getattr(row[2],'note',-1))):msg.time=tick-last;track.append(msg);last=tick
    return track


def _base(mid,bars=8,velocity=82):
    drums=_notes(0,bars,(36,),(0,8),velocity,24);bass=_notes(0,bars,(36,38,40,38),(0,),72,120);mid.tracks.extend([_track('Drums',9,drums,0,120,0),_track('Bass',1,bass,33)])


def _case(identifier,positive):
    mid=mido.MidiFile(type=1,ticks_per_beat=TPB);mid.tracks.append(mido.MidiTrack());mid.tracks[0].append(mido.MetaMessage('time_signature',numerator=4,denominator=4,time=0));index=int(identifier.split('-')[1])
    if index==1:
        _base(mid);markers=[(4*BAR,'marker','Chorus')] if positive else [(4*BAR,'text','make this louder')];mid.tracks.append(_track('Piano Comp',0,_notes(0,8,(60,64,67),(0,4,8,12),76,120),0,121,3,markers))
    elif index==2:
        velocity=(lambda bar,_sub:108 if bar>=4 else 62) if not positive else 78;_base(mid,8,velocity);pad=_notes(4,8,(48,55,60),(0,8),66,600) if positive else [];mid.tracks.append(_track('Strings Pad',2,pad,48,121,2))
    elif index==3:
        _base(mid,16);bars=[(4,8),(12,16)] if positive else [(4,5)];pad=[]
        for left,right in bars:pad+=_notes(left,right,(48,55,60),(0,4,8,12),72,160)
        mid.tracks.append(_track('Chorus Pad',2,pad,89))
    elif index==4:
        notes=_notes(0,8,(36,38,40,38),(0,),72 if positive else (lambda bar,_sub:18 if bar==4 else 72),120)
        if positive:notes=[row for row in notes if row[0]//BAR!=4]
        mid.tracks.append(_track('Bass',1,notes,33))
    elif index==5:
        _base(mid);pickup=[(BAR-TPB,96,72,76),(BAR-TPB//2,96,74,82)];markers=[(BAR,'marker','Verse 1')] if positive else [];mid.tracks.append(_track('Lead Melody',0,pickup+_notes(1,8,(76,74,72,79),(0,8),84,96),73,0,0,markers))
    elif index==6:
        _base(mid);duration=TPB*2 if positive else TPB-12;pad=[(4*BAR-TPB,duration,55,68)];markers=[(4*BAR,'marker','Bridge')];mid.tracks.append(_track('Pad',2,pad,89,0,0,markers))
    elif index==7:
        _base(mid);first=_notes(0,4,(60,64,67),(0,8),76,100);second=_notes(4,8,(61,65,68),(2,6,10,14) if positive else (0,8),76,100);mid.tracks.append(_track('Piano',0,first+second,0,121,3))
        if positive:mid.tracks.append(_track('Counter Line',3,_notes(4,8,(72,74),(4,12),70,80),71))
    elif index==8:
        _base(mid);first=_notes(0,4,(48,55,60),(0,),72,500);second=_notes(4,8,(50,53,57,60),(0,4,8,12) if positive else (0,),72,140 if positive else 500);mid.tracks.append(_track('Harmony',0,first+second,0,121,3))
        if positive:mid.tracks.append(_track('Strings',2,_notes(4,8,(60,67),(0,8),64,500),48,121,2))
    elif index==9:
        _base(mid,12);pad=_notes(4,8,(48,55,60),(0,8),68,500)
        if not positive:pad+=_notes(8,12,(50,57,62),(2,10),68,500)
        mid.tracks.append(_track('Pad',2,pad,89))
    elif index==10:
        velocity=(lambda bar,_sub:112 if bar>=4 else 58) if positive else 78;_base(mid,8,velocity);mid.tracks.append(_track('Piano',0,_notes(0,8,(60,64,67),(0,8),velocity,100),0,121,3))
    elif index==11:
        _base(mid);markers=[(6*BAR,'marker','Outro')] if positive else [(6*BAR,'text','fade maybe')];mid.tracks.append(_track('Lead',0,_notes(0,8,(72,74,76),(0,8),82,100),73,0,0,markers))
    elif index==12:
        name1='Variation 1 ACC1 CV1' if positive else 'ACC Part A';name2='Fill 1 ACC1 CV1' if positive else 'ACC Part B';mid.tracks.extend([_track(name1,11,_notes(0,2,(60,64,67),(0,8),78,100),24,121,8),_track(name2,12,_notes(0,1,(62,65,69),(0,4,8,12),88,80),24,121,8)])
    return mid


def generate_case(identifier,polarity,path):
    mid=_case(identifier,polarity=='positive');mid.tracks[0].append(mido.MetaMessage('text',text=f'SECTION_NARRATIVE_STRESS {identifier} {polarity}',time=0));mid.save(path);return Path(path)


def generate(output):
    output=Path(output);output.mkdir(parents=True,exist_ok=True);rows=[]
    for identifier,description in SCENARIOS:
        for polarity in ('positive','negative'):
            path=generate_case(identifier,polarity,output/f'{identifier}_{polarity}.mid');rows.append({'scenario_id':identifier,'description':description,'polarity':polarity,'file':path.name,'content_type':'style' if identifier=='SEC3-012' else 'song','bytes':path.stat().st_size,'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'expected_mutations':0,'expected_authority':False})
    report={'schema':'PA800_SECTION_NARRATIVE_STRESS_MANIFEST_V1','scenario_count':len(SCENARIOS),'midi_case_count':len(rows),'positive_cases':len(SCENARIOS),'negative_cases':len(SCENARIOS),'cases':rows};(output/'SECTION_NARRATIVE_STRESS_MANIFEST.json').write_text(json.dumps(report,indent=2,ensure_ascii=False)+'\n',encoding='utf-8');return report


def main(argv=None):
    parser=argparse.ArgumentParser();parser.add_argument('--output',default=str(ROOT/'SECTION_NARRATIVE_STRESS_2.5.3'));args=parser.parse_args(argv);report=generate(args.output);(ROOT/'SECTION_NARRATIVE_STRESS_MANIFEST.json').write_text(json.dumps(report,indent=2,ensure_ascii=False)+'\n',encoding='utf-8');print(json.dumps({key:value for key,value in report.items() if key!='cases'},indent=2));return 0


if __name__=='__main__':raise SystemExit(main())