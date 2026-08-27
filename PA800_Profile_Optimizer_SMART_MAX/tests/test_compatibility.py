import hashlib
import json
import zipfile
import pytest

import mido

from pa800_optimizer.compatibility import analyze_compatibility,analyze_timing_map,create_recovery_package
from pa800_optimizer.core.midi_io import collect_program_segments
from pa800_optimizer.config import OptimizeConfig
from pa800_optimizer.optimizer import Optimizer


def test_redundant_same_tempo_is_safe_but_conflict_is_not():
    mid=mido.MidiFile(type=1,ticks_per_beat=192)
    for tempo in (500000,500000):
        track=mido.MidiTrack();track.append(mido.MetaMessage('set_tempo',tempo=tempo,time=0));track.append(mido.MetaMessage('end_of_track',time=0));mid.tracks.append(track)
    audit=analyze_timing_map(mid);assert audit['safe'] and len(audit['tempo']['duplicates'])==1
    mid.tracks[1][0]=mido.MetaMessage('set_tempo',tempo=600000,time=0);audit=analyze_timing_map(mid)
    assert not audit['safe'] and audit['conflict_count']==1


def test_multi_program_channel_is_segmented_and_preserved():
    mid=mido.MidiFile(type=1,ticks_per_beat=192);track=mido.MidiTrack();mid.tracks.append(track)
    track.extend([mido.Message('control_change',channel=0,control=0,value=121,time=0),mido.Message('control_change',channel=0,control=32,value=3,time=0),mido.Message('program_change',channel=0,program=0,time=0),mido.Message('note_on',channel=0,note=60,velocity=90,time=0),mido.Message('note_off',channel=0,note=60,velocity=0,time=96),mido.Message('control_change',channel=0,control=32,value=13,time=96),mido.Message('program_change',channel=0,program=24,time=0),mido.Message('note_on',channel=0,note=67,velocity=90,time=0),mido.Message('note_off',channel=0,note=67,velocity=0,time=96)])
    result=collect_program_segments(mid);row=result['channels'][0]
    assert result['multi_program_channels']==1 and row['segment_count']==2 and row['multi_program']
    assert row['segments'][0]['address']==[121,3,0] and row['segments'][1]['address']==[121,13,24]


def test_kar_and_redundant_bank_exporter_profiles_are_reported(tmp_path):
    mid=mido.MidiFile(type=1,ticks_per_beat=192);track=mido.MidiTrack();mid.tracks.append(track)
    track.extend([mido.MetaMessage('lyrics',text='la',time=0),mido.Message('control_change',channel=0,control=0,value=121,time=0),mido.Message('control_change',channel=0,control=0,value=121,time=0),mido.Message('control_change',channel=0,control=32,value=3,time=0),mido.Message('program_change',channel=0,program=0,time=0)])
    report=analyze_compatibility(mid,tmp_path/'song.kar');ids={row['id'] for row in report['exporter_profiles']}
    assert {'KAR_LYRIC_CONTAINER','REDUNDANT_BANK_SETUP'}<=ids and report['safe_for_optimization']


def test_recovery_package_is_deterministic_and_keeps_original(tmp_path):
    source=tmp_path/'broken.kar';source.write_bytes(b'not a midi');output=tmp_path/'out.mid'
    first=create_recovery_package(source,output,'preflight','missing header');digest1=hashlib.sha256(first.read_bytes()).hexdigest();second=create_recovery_package(source,output,'preflight','missing header');digest2=hashlib.sha256(second.read_bytes()).hexdigest()
    assert digest1==digest2
    with zipfile.ZipFile(first) as archive:
        assert archive.read('ORIGINAL/broken.kar')==b'not a midi'
        report=json.loads(archive.read('RECOVERY_REPORT.json'));assert report['automatic_musical_repair_attempted'] is False and not report['preflight']['pass']


def test_optimizer_emits_recovery_package_for_unrecoverable_container(tmp_path):
    source=tmp_path/'broken.mid';source.write_bytes(b'broken');output=tmp_path/'optimized.mid'
    with pytest.raises(RuntimeError,match='RECOVERY_PACKAGE'):
        Optimizer(OptimizeConfig.for_mode('preserve')).optimize(source,output)
    assert not output.exists() and (tmp_path/'broken_PA800_RECOVERY.zip').is_file()