"""Generate exact Pa800 DNC controller/noise audition MIDIs and score sheet."""
from __future__ import annotations

import argparse,csv,json,re,shutil
from datetime import datetime,timezone
from pathlib import Path

import mido

from pa800_optimizer.manual import DncManualRegistry

ROOT=Path(__file__).resolve().parents[1]
FAMILY_ROOT={'BASS':40,'GUITAR':52,'PIANO':60,'ORGAN':60,'ENSEMBLE':60,'ACCORDION_REED':64,'BRASS':60,'REED':64,'PIPE':72,'SYNTH_FX':60}


def safe_name(text):return re.sub(r'[^A-Za-z0-9._-]+','_',text).strip('_')


def variants(profile):
    caps=set(profile.get('capabilities',[]));out=[('BASE',None,None)]
    if 'sc1' in caps:out.append(('SC1_CC80',80,127))
    if 'sc2' in caps:out.append(('SC2_CC81',81,127))
    if 'joystick_y_plus' in caps:out.append(('JOY_Y_PLUS_CC1',1,127))
    if 'joystick_y_minus' in caps:out.append(('JOY_Y_MINUS_CC2',2,127))
    if 'aftertouch' in caps:out.append(('AFTERTOUCH',None,100))
    if 'damper' in caps or 'damper_trigger' in caps or 'resonance_halo' in caps:out.append(('DAMPER_CC64',64,127))
    return out


def build_file(profile,path):
    mid=mido.MidiFile(type=1,ticks_per_beat=192);track=mido.MidiTrack();mid.tracks.append(track);root=FAMILY_ROOT.get(profile.get('family'),60);ch=0
    track.append(mido.MetaMessage('track_name',name='DNC AUDITION '+profile['name'],time=0));track.append(mido.MetaMessage('set_tempo',tempo=500000,time=0));track.append(mido.Message('control_change',channel=ch,control=0,value=profile['msb'],time=0));track.append(mido.Message('control_change',channel=ch,control=32,value=profile['lsb'],time=0));track.append(mido.Message('program_change',channel=ch,program=profile['program'],time=0))
    rows=[]
    for index,(label,cc,value) in enumerate(variants(profile)):
        track.append(mido.MetaMessage('marker',text=label,time=384 if index else 192))
        if label=='AFTERTOUCH':track.append(mido.Message('aftertouch',channel=ch,value=value,time=0))
        elif cc is not None:track.append(mido.Message('control_change',channel=ch,control=cc,value=value,time=0))
        track.append(mido.Message('note_on',channel=ch,note=root,velocity=88,time=0));track.append(mido.Message('note_off',channel=ch,note=root,velocity=0,time=190));track.append(mido.Message('note_on',channel=ch,note=root+3,velocity=94,time=2));track.append(mido.Message('note_off',channel=ch,note=root+3,velocity=0,time=192))
        if label=='AFTERTOUCH':track.append(mido.Message('aftertouch',channel=ch,value=0,time=0))
        elif cc is not None:track.append(mido.Message('control_change',channel=ch,control=cc,value=0,time=0))
        semantic_key='sc1' if cc==80 else 'sc2' if cc==81 else 'joystick_y_plus' if cc==1 else 'joystick_y_minus' if cc==2 else 'damper_trigger' if cc==64 else 'aftertouch' if label=='AFTERTOUCH' else ''
        rows.append({'sound':profile['name'],'address':'%s.%s.%s'%(profile['msb'],profile['lsb'],profile['program']),'variant':label,'documented_semantic':(profile.get('articulations') or {}).get(semantic_key,''),'heard_yes_no':'','difference_1_5':'','noise_articulation_description':'','safe_yes_no':'','comments':''})
    track.append(mido.MetaMessage('end_of_track',time=384));mid.save(str(path));return rows


def generate(output):
    registry=DncManualRegistry();output=Path(output);output.mkdir(parents=True,exist_ok=True);midi_dir=output/'MIDI';midi_dir.mkdir(exist_ok=True);all_rows=[];manifest=[]
    for profile in registry.data['sounds']:
        path=midi_dir/(safe_name(profile['name'])+'.mid');rows=build_file(profile,path);all_rows.extend(rows);manifest.append({'sound':profile['name'],'address':[profile['msb'],profile['lsb'],profile['program']],'capabilities':profile.get('capabilities',[]),'articulations':profile.get('articulations',{}),'file':str(path.relative_to(output)),'variants':[row['variant'] for row in rows]})
    fields=list(all_rows[0])
    with (output/'ARTICULATION_AUDITION_SCORE.csv').open('w',encoding='utf-8-sig',newline='') as stream:writer=csv.DictWriter(stream,fieldnames=fields);writer.writeheader();writer.writerows(all_rows)
    (output/'ARTICULATION_AUDITION_MANIFEST.json').write_text(json.dumps({'schema':'PA800_ARTICULATION_AUDITION_V1','created_utc':datetime.now(timezone.utc).isoformat(),'device':registry.data['device'],'sounds':manifest},indent=2,ensure_ascii=False),encoding='utf-8')
    (output/'READ_ME_FIRST.txt').write_text('PA800 DNC ARTICULATION AUDITION\n\nKoristi isti Pa800 OS/SET/mixer. Svaki MIDI sadrzi oznacene BASE/SC1/SC2/joystick/aftertouch/damper segmente samo ako manual potvrduje capability. Poslusaj redom, popuni CSV i ne koristi APPLY u produkciji dok rezultat nije potvrden. Key-off/RX noise proizvodi sam exact Sound na Note-Off; alat ne izmislja noise note.\n',encoding='utf-8')
    return output


def main(argv=None):
    ap=argparse.ArgumentParser();ap.add_argument('--output',default=str(ROOT/'articulation_audition'));ns=ap.parse_args(argv);out=generate(ns.output);archive=shutil.make_archive(str(out),'zip',root_dir=out);print('AUDITION_FOLDER:',out);print('SEND_THIS_ZIP:',archive)

if __name__=='__main__':main()