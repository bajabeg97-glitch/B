import mido

from pa800_optimizer.analysis.style_import_contract import analyze_style_import_contract
from pa800_optimizer.config import OptimizeConfig
from pa800_optimizer.workstation import apply_export_preset


def valid_style_smf():
    mid=mido.MidiFile(type=0,ticks_per_beat=192);track=mido.MidiTrack();mid.tracks.append(track);channel=8
    track.extend([mido.MetaMessage('marker',text='v1cv1',time=0),mido.MetaMessage('time_signature',numerator=4,denominator=4,time=0),mido.Message('control_change',channel=channel,control=0,value=121,time=0),mido.Message('control_change',channel=channel,control=32,value=13,time=0),mido.Message('program_change',channel=channel,program=33,time=0),mido.Message('control_change',channel=channel,control=11,value=100,time=0),mido.Message('note_on',channel=channel,note=40,velocity=80,time=0),mido.Message('note_off',channel=channel,note=40,velocity=0,time=96)])
    return mid


def test_official_marker_style_contract_accepts_strict_format_zero_file():
    result=analyze_style_import_contract(valid_style_smf())
    assert result['minimum_importable'] and result['strict_export_contract']
    assert result['markers'][0]['name']=='v1cv1'


def test_style_contract_rejects_uppercase_marker_outside_channel_and_cc():
    mid=valid_style_smf();mid.type=1;mid.tracks[0][0]=mido.MetaMessage('marker',text='V1CV1',time=0);mid.tracks[0].append(mido.Message('control_change',channel=0,control=7,value=100,time=0))
    result=analyze_style_import_contract(mid)
    assert not result['minimum_importable'] and not result['strict_export_contract']
    assert result['outside_style_channel_count']==1 and result['unsupported_event_count']==1


def test_incomplete_header_is_importable_minimum_but_not_strict_export_contract():
    mid=valid_style_smf();mid.tracks[0]=mido.MidiTrack([mid.tracks[0][0],mid.tracks[0][1],mid.tracks[0][-2],mid.tracks[0][-1]])
    result=analyze_style_import_contract(mid)
    assert result['minimum_importable'] and not result['strict_export_contract']


def test_style_export_preset_activates_import_contract_gate():
    cfg=apply_export_preset(OptimizeConfig.for_mode('live'),'style')
    assert cfg.content_type=='style' and cfg.require_style_import_contract