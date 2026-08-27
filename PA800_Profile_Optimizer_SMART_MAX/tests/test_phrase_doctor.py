from pa800_optimizer.analysis.phrase_doctor import _analyze_phrase_doctor
from pa800_optimizer.models import NoteEvent


def test_phrase_doctor_flags_a_velocity_spike_without_mutating_notes():
    notes=[NoteEvent(0,0,60+i,70 if i!=2 else 120,i*192,i*192+144,i*2,i*2+1,i) for i in range(5)]
    song_map={'phrases':[{'id':'phrase:0','track':0,'channel':1,'start_tick':0,'end_tick':912}]}
    result=_analyze_phrase_doctor(notes,song_map,192)
    assert result['analyzer_only'] and result['authority_granted'] is False and result['mutations']==0
    assert any(row['kind']=='VELOCITY_ANOMALY' for row in result['findings'])
    assert all(row['requested_action']=='SUGGEST' and row['candidate_delta'] is None for row in result['findings'])