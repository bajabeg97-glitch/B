import copy
from pathlib import Path
import mido
from pa800_optimizer.neural.event_contract import decode_unchanged_contract,encode_neural_contract,validate_neural_contract

def _midi(path,transpose=0,controller=False):
    mid=mido.MidiFile(type=1,ticks_per_beat=192);track=mido.MidiTrack();mid.tracks.append(track);track.extend([mido.MetaMessage('track_name',name='Piano Comp',time=0),mido.Message('control_change',channel=0,control=0,value=121,time=0),mido.Message('control_change',channel=0,control=32,value=3,time=0),mido.Message('program_change',channel=0,program=0,time=0)])
    if controller:track.append(mido.Message('control_change',channel=0,control=64,value=127,time=0))
    for chord in ((60,64,67),(62,65,69),(64,67,71),(65,69,72)):
        for pitch in chord:track.append(mido.Message('note_on',channel=0,note=pitch+transpose,velocity=72+(pitch%9),time=0))
        for index,pitch in enumerate(chord):track.append(mido.Message('note_off',channel=0,note=pitch+transpose,velocity=0,time=96 if index==0 else 0))
    if controller:track.append(mido.Message('control_change',channel=0,control=64,value=0,time=0))
    mid.save(path);return path

def test_contract_is_lossless_and_fully_attributed(tmp_path):
    source=_midi(tmp_path/'source.mid');contract=encode_neural_contract(source);validation=validate_neural_contract(contract);output=tmp_path/'decoded.mid';decoded=decode_unchanged_contract(contract,output)
    assert validation['pass'] and decoded['pass'] and source.read_bytes()==output.read_bytes()
    assert contract['summary']['event_attribution_percent']==100.0 and len(contract['note_tokens'])==12
    assert contract['summary']['phrases']>=1 and contract['phrases']
    assert all(row['phrase_id'] and row['phrase_note_count']>=1 for row in contract['note_tokens'])
    assert contract['phrase_contract']['context']=='WHOLE_PHRASE_UP_TO_8_BARS'
    assert contract['authority_granted'] is False and contract['mutations']==0

def test_contract_tamper_is_rejected(tmp_path):
    contract=encode_neural_contract(_midi(tmp_path/'source.mid'));tampered=copy.deepcopy(contract);tampered['note_tokens'][0]['velocity']=127
    assert not validate_neural_contract(tampered)['pass']

def test_source_group_is_transposition_and_velocity_invariant(tmp_path):
    one=encode_neural_contract(_midi(tmp_path/'one.mid',0));two=encode_neural_contract(_midi(tmp_path/'two.mid',5));assert one['source_group_id']==two['source_group_id']

def test_sensitive_controller_protects_channel_notes(tmp_path):
    contract=encode_neural_contract(_midi(tmp_path/'pedal.mid',controller=True));assert contract['note_tokens'] and all(row['protected'] for row in contract['note_tokens']);assert all('CC64' in row['protected_dependencies'] for row in contract['note_tokens'])
