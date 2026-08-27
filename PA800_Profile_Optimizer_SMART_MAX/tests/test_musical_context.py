import copy,csv
import mido
from pa800_optimizer.analysis.musical_context import analyze_musical_context,classify_track_function,evidence_for_context
from pa800_optimizer.models import NoteEvent,SoundIdentity,TrackContext
from tests.helpers import make_mid
from tools.create_context_ground_truth import generate


def notes(track,channel,pitches,velocity=85,start=0,step=96,duration=72):
    return [NoteEvent(track,channel,pitch,velocity,start+i*step,start+i*step+duration,i*2,i*2+1) for i,pitch in enumerate(pitches)]


def test_track_function_uses_structural_foundation_roles():
    bass=TrackContext(0,8,'BASS',SoundIdentity(121,0,33,'Finger Bass GM','BASS'),family='BASS',resolution_status='EXACT_ADDRESS')
    row=classify_track_function(bass,notes(0,8,[36,38,40,41]),192)
    assert row['function']=='FOUNDATION_BASS' and row['evidence_level']=='E2' and row['confidence']>=.95


def test_pad_and_lead_are_musically_distinct():
    pad=TrackContext(0,0,'SONG',SoundIdentity(121,6,89,'Dark Pad','SYNTH_PAD'),family='SYNTH_PAD',resolution_status='EXACT_ADDRESS')
    pad_notes=[]
    for onset in (0,384,768,1152):
        for pitch in (48,55,60):pad_notes.append(NoteEvent(0,0,pitch,70,onset,onset+360,len(pad_notes),len(pad_notes)))
    lead=TrackContext(1,1,'SONG',SoundIdentity(121,0,73,'Flute GM','PIPE'),family='PIPE',track_name='Solo Lead',resolution_status='EXACT_ADDRESS')
    assert classify_track_function(pad,pad_notes,192)['function']=='PAD_BACKGROUND'
    assert classify_track_function(lead,notes(1,1,[72,74,76,79,81]),192)['function']=='LEAD'


def test_song_context_analysis_is_analyzer_only_and_finds_sections():
    mid=mido.MidiFile(type=1,ticks_per_beat=192);mid.tracks.extend([mido.MidiTrack(),mido.MidiTrack()])
    contexts={(0,0):TrackContext(0,0,'BASS',SoundIdentity(121,0,33,'Bass','BASS'),family='BASS',resolution_status='EXACT_ADDRESS'),(1,1):TrackContext(1,1,'SONG',SoundIdentity(121,0,73,'Flute','PIPE'),family='PIPE',track_name='Lead',resolution_status='EXACT_ADDRESS')}
    all_notes=notes(0,0,[36]*48,90,0,96,80)+notes(1,1,[72,74,76,77]*8,85,1536,96,72)
    before=copy.deepcopy(mid.tracks);result=analyze_musical_context(mid,all_notes,contexts,'song')
    assert result['analyzer_only'] and result['mutations']==0 and result['sections']
    assert result['function_counts']['FOUNDATION_BASS']==1 and result['function_counts']['LEAD']==1
    assert mid.tracks==before


def test_style_uses_serialized_element_cv_as_e2_section():
    mid=mido.MidiFile(type=1,ticks_per_beat=192);mid.tracks.append(mido.MidiTrack())
    ctx=TrackContext(0,8,'BASS',SoundIdentity(121,0,33,'Bass','BASS'),element='Variation 2',cv=1,family='BASS',resolution_status='EXACT_ADDRESS')
    result=analyze_musical_context(mid,notes(0,8,[36,38,40,41]),{(0,8):ctx},'style')
    assert result['sections'][0]['label']=='Variation 2' and result['sections'][0]['evidence_level']=='E2'
    assert evidence_for_context(ctx)=='E2'


def test_ground_truth_generator_writes_track_and_section_sheets(tmp_path):
    source=tmp_path/'source';source.mkdir();make_mid(str(source/'song.mid'),channel=0)
    track_csv,section_csv=generate(source,tmp_path/'ground.csv',10)
    assert list(csv.DictReader(track_csv.open(encoding='utf-8-sig')))
    assert list(csv.DictReader(section_csv.open(encoding='utf-8-sig')))