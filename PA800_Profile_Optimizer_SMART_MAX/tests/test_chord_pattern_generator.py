import json

import mido
import pytest

from pa800_optimizer.neural.pattern_advisor import generate_chord_pattern,parse_chord_progression


def _template(path):
    mid=mido.MidiFile(type=1,ticks_per_beat=192)
    conductor=mido.MidiTrack();mid.tracks.append(conductor);conductor.extend([mido.MetaMessage('track_name',name='Conductor',time=0),mido.MetaMessage('time_signature',numerator=4,denominator=4,time=0),mido.MetaMessage('set_tempo',tempo=500000,time=0),mido.MetaMessage('end_of_track',time=1536)])
    drum=mido.MidiTrack();mid.tracks.append(drum);drum.extend([mido.MetaMessage('track_name',name='Variation 1 DRUM CV1',time=0),mido.Message('program_change',channel=9,program=0,time=0)])
    for index in range(8):drum.extend([mido.Message('note_on',channel=9,note=36 if index%2==0 else 38,velocity=100-index,time=192 if index else 0),mido.Message('note_off',channel=9,note=36 if index%2==0 else 38,velocity=0,time=24)])
    drum.append(mido.MetaMessage('end_of_track',time=1536-sum(msg.time for msg in drum)))
    bass=mido.MidiTrack();mid.tracks.append(bass);bass.extend([mido.MetaMessage('track_name',name='Variation 1 BASS CV1',time=0),mido.Message('program_change',channel=8,program=33,time=0)])
    for pitch,delay in ((36,0),(43,192),(36,552),(43,192)):bass.extend([mido.Message('note_on',channel=8,note=pitch,velocity=82,time=delay),mido.Message('note_off',channel=8,note=pitch,velocity=0,time=96)])
    bass.append(mido.MetaMessage('end_of_track',time=1536-sum(msg.time for msg in bass)))
    guitar=mido.MidiTrack();mid.tracks.append(guitar);guitar.extend([mido.MetaMessage('track_name',name='Variation 1 ACC1 CV1',time=0),mido.Message('program_change',channel=11,program=24,time=0)])
    for bar in range(2):
        for index,pitch in enumerate((48,52,55)):guitar.append(mido.Message('note_on',channel=11,note=pitch,velocity=76+index*3,time=3 if index else 0))
        for index,pitch in enumerate((48,52,55)):guitar.append(mido.Message('note_off',channel=11,note=pitch,velocity=0,time=180 if index==0 else 0))
        if bar==0:guitar.append(mido.MetaMessage('text',text='bar gap',time=582))
    guitar.append(mido.MetaMessage('end_of_track',time=max(0,1536-sum(msg.time for msg in guitar))))
    mid.save(path);return path


def _non_pitch_signature(path):
    mid=mido.MidiFile(path);rows=[]
    for track_index,track in enumerate(mid.tracks):
        tick=0
        for ordinal,msg in enumerate(track):
            tick+=msg.time;data=msg.dict();data.pop('time',None);data.pop('note',None);rows.append((track_index,ordinal,tick,msg.type,data))
    return rows


def test_chord_parser_supports_professional_qualities_repeats_and_slash_bass():
    rows=parse_chord_progression('C*2 | Am7 | Bbmaj7 | Gsus4 | C/E | D5')
    assert [row['label'] for row in rows]==['C','C','Am7','Bbmaj7','Gsus4','C/E','D5']
    with pytest.raises(ValueError):parse_chord_progression('C | Hm')


def test_generator_revoices_only_tonal_pitch_and_preserves_template_performance(tmp_path):
    source=_template(tmp_path/'template.mid');output=tmp_path/'generated.mid';report=generate_chord_pattern(source,output,'Dm | G7',content_type='style')
    assert output.is_file() and report['verifier']['pass'] and report['summary']['pitch_changed_notes']>0
    assert report['summary']['velocity_changes']==report['summary']['timing_changes']==report['summary']['gate_changes']==0
    assert _non_pitch_signature(source)==_non_pitch_signature(output)
    original=mido.MidiFile(source);generated=mido.MidiFile(output)
    source_drums=[msg.note for msg in original.tracks[1] if msg.type=='note_on' and msg.velocity>0];output_drums=[msg.note for msg in generated.tracks[1] if msg.type=='note_on' and msg.velocity>0]
    assert source_drums==output_drums
    assert [msg.velocity for track in original.tracks for msg in track if msg.type=='note_on' and msg.velocity>0]==[msg.velocity for track in generated.tracks for msg in track if msg.type=='note_on' and msg.velocity>0]
    sidecar=json.loads((tmp_path/'generated.mid.pattern.json').read_text(encoding='utf-8'));assert sidecar['authority']['neural']=='NOT_USED_NO_RETRAIN'
