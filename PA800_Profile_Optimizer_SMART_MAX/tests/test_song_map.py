import mido

from pa800_optimizer.analysis.song_map import _build_song_map
from pa800_optimizer.analysis.musical_context import analyze_musical_context
from pa800_optimizer.analysis.section_narrative import analyze_section_narrative
from pa800_optimizer.analysis.instrument_intent import analyze_instrument_intent
from pa800_optimizer.analysis.family_intent import analyze_family_intents
from pa800_optimizer.analysis.musical_understanding import analyze_musical_understanding
from pa800_optimizer.analysis.context import build_contexts
from pa800_optimizer.analysis.intent import classify_intents
from pa800_optimizer.core.midi_io import extract_notes
from pa800_optimizer.profiles.registry import ProfileRegistry
from pa800_optimizer.models import NoteEvent


def test_song_map_is_deterministic_and_only_describes_whole_song_context():
    mid=mido.MidiFile(type=1,ticks_per_beat=192);drums=mido.MidiTrack();bass=mido.MidiTrack();mid.tracks.extend([drums,bass])
    drums.extend([mido.MetaMessage('track_name',name='Drums',time=0),mido.Message('program_change',channel=9,program=0,time=0)])
    bass.extend([mido.MetaMessage('track_name',name='Bass',time=0),mido.Message('program_change',channel=0,program=33,time=0)])
    for _ in range(8):
        drums.extend([mido.Message('note_on',channel=9,note=36,velocity=90,time=0),mido.Message('note_off',channel=9,note=36,velocity=0,time=96)])
        bass.extend([mido.Message('note_on',channel=0,note=36,velocity=80,time=0),mido.Message('note_off',channel=0,note=36,velocity=0,time=96)])
    registry=ProfileRegistry();contexts=build_contexts(mid,registry,'song');notes=extract_notes(mid);classify_intents(notes,contexts,mid.ticks_per_beat)
    context=analyze_musical_context(mid,notes,contexts,'song');understanding=analyze_musical_understanding(mid,notes,contexts,context);narrative=analyze_section_narrative(mid,notes,contexts,context,understanding);family=analyze_family_intents(mid,notes,contexts,context,narrative);intent=analyze_instrument_intent(mid,notes,contexts,context,understanding,family,narrative)
    first=_build_song_map(notes,context,narrative,intent);second=_build_song_map(notes,context,narrative,intent)
    assert first==second and first['analyzer_only'] and first['authority_granted'] is False and first['mutations']==0
    assert first['summary']['phrases']>=2 and any(row['kind']=='DRUM_BASS_GROOVE_LOCK' for row in first['dependencies'])


def test_song_map_phrase_gap_uses_true_ppqn_for_compound_meter():
    notes=[NoteEvent(0,0,60,80,0,50,0,1),NoteEvent(0,0,62,80,250,300,2,3)]
    context={'track_functions':[{'track':0,'channel':1,'function':'LEAD'}]}
    narrative={'meter':{'numerator':6,'denominator':8,'bar_ticks':576,'ticks_per_beat':192},'sections':[{'index':0,'start_tick':0,'end_tick':576}]}
    result=_build_song_map(notes,context,narrative,{'summary':{}})
    assert result['summary']['phrases']==1