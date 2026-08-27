"""Generate the canonical positive/negative MIDI stress corpus for Intent V3."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path

import mido


ROOT=Path(__file__).resolve().parents[1]
ROADMAP=ROOT/'ROADMAP_INSTRUMENT_INTENT_AUTOMATION_2.5_TO_3.0.md'
ROW_RE=re.compile(r'^\| ([A-Z]{2,3}-\d{3}) \| (.*?) \| (.*?) \|$',re.MULTILINE)


def scenario_rows(path=ROADMAP):
    text=Path(path).read_text(encoding='utf-8')
    return [{'scenario_id':match.group(1),'description':match.group(2),'expected':match.group(3)} for match in ROW_RE.finditer(text)]


def _track(name,channel,program=0,msb=0,lsb=0):
    track=mido.MidiTrack();track.extend([mido.MetaMessage('track_name',name=name,time=0),mido.Message('control_change',channel=channel,control=0,value=msb,time=0),mido.Message('control_change',channel=channel,control=32,value=lsb,time=0),mido.Message('program_change',channel=channel,program=program,time=0)])
    return track


def _notes(track,channel,pitches,count=8,step=96,duration=72,velocity=80,spread=0):
    for index in range(count):
        pitch=pitches[index%len(pitches)];track.append(mido.Message('note_on',channel=channel,note=pitch,velocity=max(1,min(127,velocity+(index%3-1)*7)),time=0 if index==0 else max(0,step-duration)))
        if spread and index%3==0:
            for extra in (4,7):track.append(mido.Message('note_on',channel=channel,note=min(127,pitch+extra),velocity=max(1,velocity-extra),time=spread))
            track.append(mido.Message('note_off',channel=channel,note=pitch+4,velocity=0,time=max(0,duration-spread*2)));track.append(mido.Message('note_off',channel=channel,note=pitch+7,velocity=0,time=0));track.append(mido.Message('note_off',channel=channel,note=pitch,velocity=0,time=0))
        else:track.append(mido.Message('note_off',channel=channel,note=pitch,velocity=0,time=duration))


def _intent_case(mid,positive,index):
    track=_track('Lead Melody' if positive else 'PAD',0,73);_notes(track,0,[72,74,76,79,81] if positive else [48,55,60],count=8,step=96,duration=72 if positive else 180,spread=0 if positive else 2);mid.tracks.append(track)
    if index%3==0:
        bass=_track('Bass Foundation',1,33);_notes(bass,1,[36,36,38,40],count=8,velocity=70);mid.tracks.append(bass)


def _drum_case(mid,positive,index):
    track=_track('Drums' if positive else 'Melodic Channel 10',9,0,120 if positive else 0,0)
    pitches=[36,38,42,38] if positive else [60,64,67,72];_notes(track,9,pitches,count=12,step=48,duration=12,velocity=110 if positive else 70)
    if positive and index%2==0:track.extend([mido.Message('note_on',channel=9,note=38,velocity=18,time=2),mido.Message('note_off',channel=9,note=38,velocity=0,time=4)])
    mid.tracks.append(track)


def _bass_case(mid,positive,index):
    drums=_track('Drums',9,0,120,0);bass=_track('Bass',1,33)
    for beat in range(8):
        drums.extend([mido.Message('note_on',channel=9,note=36,velocity=110,time=0 if beat==0 else 84),mido.Message('note_off',channel=9,note=36,velocity=0,time=12)])
        delay=12 if positive else (70 if beat%2 else 0);bass.extend([mido.Message('note_on',channel=1,note=[36,38,35,36][beat%4],velocity=76,time=delay if beat==0 else max(0,96-72+delay)),mido.Message('note_off',channel=1,note=[36,38,35,36][beat%4],velocity=0,time=max(1,72-delay))])
    if index%5==4:bass.extend([mido.Message('note_on',channel=1,note=24,velocity=12,time=1),mido.Message('note_off',channel=1,note=24,velocity=0,time=8)])
    mid.tracks.extend([drums,bass])


def _guitar_case(mid,positive,index):
    track=_track('Guitar Strum' if positive else 'Guitar Line',0,24,121,8)
    if positive:
        for chord in ((48,52,55),(50,53,57),(52,55,59),(53,57,60)):
            for offset,pitch in enumerate(chord):track.append(mido.Message('note_on',channel=0,note=pitch,velocity=92-offset*8,time=offset*4))
            for offset,pitch in enumerate(chord):track.append(mido.Message('note_off',channel=0,note=pitch,velocity=0,time=72 if offset==0 else 0))
    else:_notes(track,0,[60,62,64,65],count=12,step=48,duration=36,velocity=80)
    mid.tracks.append(track)


def _piano_case(mid,positive,index):
    track=_track('Piano Comp' if positive else 'Piano Melody',0,0,121,3)
    if index%4==1:track.append(mido.Message('control_change',channel=0,control=64,value=127,time=0))
    _notes(track,0,[60,62,65,67] if not positive else [48,53,55,50],count=8,step=96,duration=80 if not positive else 180,velocity=78,spread=2 if positive else 0)
    if index%4==1:track.append(mido.Message('control_change',channel=0,control=64,value=0,time=0))
    mid.tracks.append(track)


def _expressive_case(mid,positive,index):
    program=(16,56,71,21,80)[index%5];name=('Organ','Brass','Clarinet','Accordion','Synth Lead')[index%5];track=_track(name,0,program,121,1)
    if positive:
        track.extend([mido.Message('control_change',channel=0,control=1,value=20,time=0),mido.Message('control_change',channel=0,control=1,value=100,time=96),mido.Message('pitchwheel',channel=0,pitch=2048,time=24)])
    _notes(track,0,[60,62,64,67,65],count=10,step=72,duration=70 if positive else 24,velocity=75)
    mid.tracks.append(track)


def _section_case(mid,positive,index):
    bass=_track('Bass',1,33);_notes(bass,1,[36,38,40,41],count=24,step=96,duration=72,velocity=70);mid.tracks.append(bass)
    lead=_track('Lead Melody',0,73);_notes(lead,0,[72,74,76,79],count=8 if positive else 24,step=96,duration=72,velocity=88 if positive else 105);mid.tracks.append(lead)
    if positive:
        pad=_track('Chorus Pad',2,89);pad.append(mido.MetaMessage('marker',text='Chorus',time=1536));_notes(pad,2,[48,55,60],count=12,step=96,duration=180,velocity=68,spread=2);mid.tracks.append(pad)


def _ensemble_case(mid,positive,index):
    a=_track('Lead A',0,73);b=_track('Counter B',1,71)
    _notes(a,0,[72,74,76],count=6,step=192 if positive else 96,duration=48,velocity=82)
    b.append(mido.MetaMessage('text',text='answer',time=96 if positive else 0));_notes(b,1,[76,74,72],count=6,step=192 if positive else 96,duration=48,velocity=76)
    mid.tracks.extend([a,b])


def _automation_case(mid,positive,index):
    name='Reliable Piano' if positive else ('Solo PAD' if index%2 else 'Mystery');track=_track(name,0,0,121 if positive else 120,3 if positive else 0)
    if not positive and index%3==0:track.extend([mido.Message('control_change',channel=0,control=32,value=8,time=0),mido.Message('program_change',channel=0,program=24,time=0)])
    if not positive and index%3==1:track.append(mido.Message('control_change',channel=0,control=1,value=127,time=0))
    _notes(track,0,[60,64,67] if positive else [60],count=12 if positive else 2,step=96,duration=72,velocity=82,spread=2 if positive else 0);mid.tracks.append(track)


def _io_case(mid,positive,index):
    track=_track('IO Extreme',index%16,0)
    if index==0:track.extend([mido.Message('note_on',channel=index%16,note=0,velocity=1,time=0),mido.Message('note_off',channel=index%16,note=0,velocity=0,time=0),mido.Message('note_on',channel=index%16,note=127,velocity=127,time=1000000 if positive else 1),mido.Message('note_off',channel=index%16,note=127,velocity=0,time=1)])
    else:
        if index==4:track.append(mido.Message('sysex',data=(1,2,3,4),time=0))
        _notes(track,index%16,[60,60,64,67],count=16 if positive else 4,step=1 if positive else 96,duration=0 if index==2 else 48,velocity=80)
    mid.tracks.append(track)


BUILDERS={'INT':_intent_case,'DRM':_drum_case,'BAS':_bass_case,'GTR':_guitar_case,'PNO':_piano_case,'EXP':_expressive_case,'SEC':_section_case,'ENS':_ensemble_case,'AUT':_automation_case,'IO':_io_case}


def generate_case(scenario_id,polarity,path):
    prefix=scenario_id.split('-')[0];index=int(scenario_id.split('-')[1])-1;mid=mido.MidiFile(type=1,ticks_per_beat=192);BUILDERS[prefix](mid,polarity=='positive',index);mid.tracks[0].insert(1,mido.MetaMessage('text',text=f'INTENT_STRESS {scenario_id} {polarity}',time=0));mid.save(path);return Path(path)


def generate(output):
    output=Path(output);output.mkdir(parents=True,exist_ok=True);rows=[]
    for scenario in scenario_rows():
        for polarity in ('positive','negative'):
            name=f"{scenario['scenario_id']}_{polarity}.mid";path=generate_case(scenario['scenario_id'],polarity,output/name);digest=hashlib.sha256(path.read_bytes()).hexdigest()
            rows.append({**scenario,'polarity':polarity,'file':name,'bytes':path.stat().st_size,'sha256':digest,'expected_mutations':0,'expected_authority':False})
    manifest={'schema':'PA800_INSTRUMENT_INTENT_STRESS_V1','roadmap':'ROADMAP_INSTRUMENT_INTENT_AUTOMATION_2.5_TO_3.0.md','scenario_count':len(rows)//2,'midi_case_count':len(rows),'positive_cases':sum(row['polarity']=='positive' for row in rows),'negative_cases':sum(row['polarity']=='negative' for row in rows),'cases':rows}
    (output/'INSTRUMENT_INTENT_STRESS_MANIFEST.json').write_text(json.dumps(manifest,indent=2,ensure_ascii=False)+'\n',encoding='utf-8');return manifest


def main(argv=None):
    default=ROOT/'INSTRUMENT_INTENT_STRESS_2.5.0';parser=argparse.ArgumentParser();parser.add_argument('--output',default=str(default));args=parser.parse_args(argv);report=generate(args.output)
    if Path(args.output).resolve()==default.resolve():(ROOT/'INSTRUMENT_INTENT_STRESS_MANIFEST.json').write_text(json.dumps(report,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
    print(json.dumps({key:value for key,value in report.items() if key!='cases'},indent=2));return 0 if report['scenario_count']==55 and report['midi_case_count']==110 else 1


if __name__=='__main__':raise SystemExit(main())