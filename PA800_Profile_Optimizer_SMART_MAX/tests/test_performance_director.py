import mido
from pa800_optimizer.config import OptimizeConfig
from pa800_optimizer.engines.performance_director import run_performance_director,segment_phrases
from pa800_optimizer.models import NoteEvent,OptimizationReport,SoundIdentity,TrackContext


def make_notes(track=0,channel=0,start=0,vel=80):
    return [NoteEvent(track,channel,36+i%3,vel,start+i*96,start+i*96+72,i*2,i*2+1) for i in range(8)]


def test_phrase_segmentation_splits_large_silence():
    arr=make_notes()[:4]+make_notes(start=3000)[4:]
    assert len(segment_phrases(arr,192))==2


def test_song_e1_context_stays_shadow_even_when_apply_requested():
    mid=mido.MidiFile(type=1,ticks_per_beat=192);track=mido.MidiTrack();mid.tracks.append(track);arr=make_notes()
    for note in arr:track.append(mido.Message('note_on',channel=0,note=note.note,velocity=note.velocity,time=0));note.on_index=len(track)-1
    ctx=TrackContext(0,0,'BASS',SoundIdentity(121,0,33,'Bass','BASS'),family='BASS');musical={'track_functions':[{'track':0,'channel':1,'function':'FOUNDATION_BASS','evidence_level':'E2'}],'sections':[{'index':0,'label':'CHORUS','start_tick':0,'end_tick':5000,'evidence_level':'E1'}]};cfg=OptimizeConfig.for_mode('live');cfg.apply_performance_director=True;report=OptimizationReport('in','out');before=[m.velocity for m in track]
    run_performance_director(mid,arr,{(0,0):ctx},musical,cfg,report)
    assert [m.velocity for m in track]==before and report.performance_director['applied_changes']==0
    assert report.performance_director['song_e1_mutation_allowed'] is False
    assert report.performance_director['phrases'][0]['apply_status']=='BLOCKED_EVIDENCE_GATE'


def test_e2_style_phrase_can_apply_bounded_offset_and_protect_notes():
    mid=mido.MidiFile(type=1,ticks_per_beat=192);track=mido.MidiTrack();mid.tracks.append(track);arr=make_notes();arr[0].protected=True
    for note in arr:track.append(mido.Message('note_on',channel=0,note=note.note,velocity=note.velocity,time=0));note.on_index=len(track)-1
    ctx=TrackContext(0,0,'BASS',SoundIdentity(121,0,33,'Bass','BASS'),element='Variation 4',cv=1,family='BASS');musical={'track_functions':[{'track':0,'channel':1,'function':'FOUNDATION_BASS','evidence_level':'E2'}],'sections':[{'index':0,'label':'Variation 4','start_tick':0,'end_tick':5000,'evidence_level':'E2'}]};cfg=OptimizeConfig.for_mode('live');cfg.apply_performance_director=True;report=OptimizationReport('in','out')
    run_performance_director(mid,arr,{(0,0):ctx},musical,cfg,report)
    assert track[0].velocity==80 and all(msg.velocity==82 for msg in track[1:])
    assert report.performance_director['applied_changes']==7 and report.performance_director['pass']
    phrase=report.performance_director['phrases'][0]
    assert phrase['velocity_iqr_after']==phrase['velocity_iqr_before']
    assert phrase['timing_suggestion_only'] and phrase['gate_suggestion_only']


def test_interaction_report_contains_drum_bass_drum_perc_and_lead_margin():
    mid=mido.MidiFile(type=1,ticks_per_beat=192);mid.tracks.extend([mido.MidiTrack() for _ in range(5)]);all_notes=make_notes(0,0,vel=100)+make_notes(1,1,start=8,vel=90)+make_notes(2,2,start=4,vel=82)+make_notes(3,3,vel=95)+make_notes(4,4,vel=70)
    functions=['FOUNDATION_DRUM','FOUNDATION_BASS','FOUNDATION_PERC','LEAD','PAD_BACKGROUND'];contexts={};rows=[]
    for i,function in enumerate(functions):contexts[(i,i)]=TrackContext(i,i,'SONG',SoundIdentity(121,0,i,'Sound','UNKNOWN'),family='UNKNOWN');rows.append({'track':i,'channel':i+1,'function':function,'evidence_level':'E1'})
    musical={'track_functions':rows,'sections':[{'index':0,'label':'WHOLE_SONG','start_tick':0,'end_tick':5000,'evidence_level':'E1'}]};report=OptimizationReport('in','out');run_performance_director(mid,all_notes,contexts,musical,OptimizeConfig.for_mode('live'),report)
    kinds={row['kind'] for row in report.performance_director['interactions']}
    assert {'DRUM_BASS_ONSET_RELATION','DRUM_PERC_ONSET_RELATION','LEAD_BACKGROUND_VELOCITY_MARGIN'}<=kinds


def test_shadow_policy_never_changes_midi_even_with_e2_style_evidence():
    mid=mido.MidiFile(type=1,ticks_per_beat=192);track=mido.MidiTrack();mid.tracks.append(track);arr=make_notes(vel=76)
    for note in arr:track.append(mido.Message('note_on',channel=0,note=note.note,velocity=note.velocity,time=0));note.on_index=len(track)-1
    ctx=TrackContext(0,0,'ACC1',SoundIdentity(121,3,0,'Grand Piano','PIANO'),element='Variation 4',cv=1,family='PIANO')
    musical={'track_functions':[{'track':0,'channel':1,'function':'LEAD','evidence_level':'E2'}],'sections':[{'index':0,'label':'Variation 4','start_tick':0,'end_tick':5000,'evidence_level':'E2'}]}
    report=OptimizationReport('in','out');before=[msg.velocity for msg in track]
    run_performance_director(mid,arr,{(0,0):ctx},musical,OptimizeConfig.for_mode('live'),report)
    assert [msg.velocity for msg in track]==before
    assert report.performance_director['policy']=='shadow'
    assert report.performance_director['phrases'][0]['apply_status']=='SHADOW_ONLY'