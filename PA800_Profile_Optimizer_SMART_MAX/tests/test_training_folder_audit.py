import shutil

import mido

from pa800_optimizer.neural.training_audit import audit_training_folder,public_training_audit,render_training_audit


def _midi(path,pitch,duration=72):
    mid=mido.MidiFile(type=0,ticks_per_beat=96);track=mido.MidiTrack();mid.tracks.append(track)
    track.extend([mido.Message('note_on',channel=0,note=pitch,velocity=80,time=0),mido.Message('note_off',channel=0,note=pitch,velocity=0,time=duration)])
    mid.save(path)


def test_training_folder_audit_rejects_empty_corrupt_and_duplicate(tmp_path):
    for index,(pitch,duration) in enumerate(((60,48),(62,72),(64,96)),1):_midi(tmp_path/('valid%d.mid'%index),pitch,duration)
    shutil.copy2(tmp_path/'valid1.mid',tmp_path/'duplicate.mid');(tmp_path/'empty.mid').write_bytes(b'');(tmp_path/'broken.kar').write_bytes(b'not-midi')
    audit=audit_training_folder(tmp_path)
    assert audit['pass'] and audit['accepted_files']==3 and audit['rejected_files']==3
    assert audit['splits']=={'train':1,'validation':1,'test':1}
    assert audit['rejection_counts']=={'DUPLICATE_CONTENT':1,'EMPTY_FILE':1,'INVALID_MIDI':1}
    assert audit['group_split_leakage']=={} and audit['mutations_to_original_sources']==0
    assert '_contracts' not in public_training_audit(audit)
    rendered=render_training_audit(audit)
    assert '[REJECT]' in rendered and 'AUDIT RESULT: PASS' in rendered


def test_training_folder_audit_fails_when_split_requirements_are_not_met(tmp_path):
    _midi(tmp_path/'one.mid',60);_midi(tmp_path/'two.mid',62)
    audit=audit_training_folder(tmp_path)
    assert not audit['pass'] and audit['accepted_files']==2