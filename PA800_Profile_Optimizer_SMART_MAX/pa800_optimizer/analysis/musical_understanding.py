"""Analyzer-only musician-facing interpretation of MIDI structure.

The module turns measurements into bounded musical statements. Every inference
contains evidence, confidence and a limitation; uncertain ideas stay UNKNOWN.
It never mutates MIDI and grants no authority to the performance engines.
"""
from __future__ import annotations

from collections import Counter,defaultdict
import statistics


PITCH_NAMES=('C','C#','D','Eb','E','F','F#','G','Ab','A','Bb','B')


def _median(values,default=0.0):return float(statistics.median(values)) if values else float(default)


def _statement(domain,text,confidence,evidence='E1',support=None,limitation='MIDI structure does not prove audible intent.'):
    return {'domain':domain,'statement':text,'confidence':round(max(0.0,min(1.0,float(confidence))),3),'evidence_level':evidence,'support':support or {},'limitation':limitation}


def _phrase_rows(notes,tpb):
    notes=sorted(notes,key=lambda n:(n.onset,n.note,n.occurrence));tpb=max(1,int(tpb));phrases=[]
    if not notes:return phrases
    gap=max(tpb,int(round(_median([n.duration for n in notes],tpb)*1.5)));current=[notes[0]]
    for note in notes[1:]:
        if note.onset-current[-1].off>=gap:phrases.append(current);current=[note]
        else:current.append(note)
    phrases.append(current);rows=[]
    for index,arr in enumerate(phrases):
        velocities=[n.velocity for n in arr];third=max(1,len(arr)//3);start=_median(velocities[:third]);middle=_median(velocities[third:-third] or velocities);end=_median(velocities[-third:]);peak=max(velocities)
        if len(arr)<4:contour='UNKNOWN';confidence=.35
        elif middle>=start+5 and middle>=end+5:contour='ARCH';confidence=.68
        elif end>=start+7:contour='RISING';confidence=.62
        elif start>=end+7:contour='FALLING';confidence=.62
        else:contour='LEVEL_OR_SUBTLE';confidence=.55
        rows.append({'index':index,'start_tick':arr[0].onset,'end_tick':max(n.off for n in arr),'notes':len(arr),'pitch_min':min(n.note for n in arr),'pitch_max':max(n.note for n in arr),'velocity_start':round(start,2),'velocity_middle':round(middle,2),'velocity_end':round(end,2),'velocity_peak':peak,'dynamic_contour':contour,'confidence':confidence,'evidence_level':'E1'})
    return rows


def _melodic_narrative(notes_by_key,track_functions,tpb):
    rows=[]
    for key,function in sorted(track_functions.items()):
        if function.get('function') not in ('LEAD','COUNTER_LINE','RIFF_OSTINATO'):continue
        notes=sorted(notes_by_key.get(key,[]),key=lambda n:(n.onset,n.note,n.occurrence))
        if not notes:continue
        intervals=[b.note-a.note for a,b in zip(notes,notes[1:])];steps=sum(abs(value)<=2 for value in intervals);leaps=sum(abs(value)>=7 for value in intervals);direction=sum(1 if value>0 else -1 if value<0 else 0 for value in intervals)
        if len(notes)<4:contour='UNKNOWN';confidence=.35
        elif direction>=max(2,len(intervals)//3):contour='ASCENDING_TENDENCY';confidence=.61
        elif direction<=-max(2,len(intervals)//3):contour='DESCENDING_TENDENCY';confidence=.61
        elif max(n.note for n in notes[1:-1] or notes)>=max(notes[0].note,notes[-1].note)+5:contour='ARCH_OR_PEAK';confidence=.64
        else:contour='BALANCED_OR_WAVE';confidence=.52
        motifs=Counter(tuple(intervals[index:index+3]) for index in range(max(0,len(intervals)-2)));repeated=[{'intervals':list(pattern),'occurrences':count} for pattern,count in motifs.most_common(4) if count>=2]
        rows.append({'track':key[0],'channel':key[1]+1,'function':function.get('function'),'notes':len(notes),'range_semitones':max(n.note for n in notes)-min(n.note for n in notes),'median_pitch':round(_median([n.note for n in notes]),2),'stepwise_ratio':round(steps/max(1,len(intervals)),4),'large_leap_ratio':round(leaps/max(1,len(intervals)),4),'contour':contour,'contour_confidence':confidence,'repeated_interval_motifs':repeated,'phrase_count':len(_phrase_rows(notes,tpb)),'evidence_level':'E1','limitation':'Contour and motif repetition do not prove thematic importance.'})
    return {'tracks':rows,'mutations':0}


def _triad_name(pitches):
    pcs=set(int(p)%12 for p in pitches)
    patterns=((frozenset((0,4,7)),'MAJOR'),(frozenset((0,3,7)),'MINOR'),(frozenset((0,3,6)),'DIMINISHED'),(frozenset((0,4,8)),'AUGMENTED'),(frozenset((0,2,7)),'SUS2'),(frozenset((0,5,7)),'SUS4'))
    for root in range(12):
        normalized=frozenset((pc-root)%12 for pc in pcs)
        for pattern,label in patterns:
            if pattern<=normalized:return PITCH_NAMES[root]+'_'+label
    return 'UNCLASSIFIED'


def _harmony(notes,track_functions,tpb):
    # Vertical pitch collections can occur in comping, pads or arpeggiated
    # foreground writing.  We only exclude explicit rhythmic foundations; the
    # resulting label remains an observed pitch-class shape, never a claim of
    # functional harmony.
    harmonic_keys={key for key,row in track_functions.items() if row.get('function') not in ('FOUNDATION_DRUM','FOUNDATION_PERC','FOUNDATION_BASS','UNKNOWN')}
    candidates=[n for n in notes if (n.track_index,n.channel) in harmonic_keys]
    cluster_window=max(1,int(tpb)//16);clusters=[]
    for note in sorted(candidates,key=lambda n:(n.onset,n.note)):
        if not clusters or note.onset-clusters[-1]['start']>cluster_window:clusters.append({'start':note.onset,'onsets':[note.onset],'pitches':[note.note]})
        else:clusters[-1]['onsets'].append(note.onset);clusters[-1]['pitches'].append(note.note)
    chords=[]
    for cluster in clusters:
        pitches=cluster['pitches']
        if len(set(pitches))<3:continue
        chords.append({'tick':cluster['start'],'end_tick':max(cluster['onsets']),'pitches':sorted(set(pitches)),'pitch_classes':sorted({p%12 for p in pitches}),'bass_pitch':min(pitches),'label':_triad_name(pitches),'grouping':'SIMULTANEOUS' if len(set(cluster['onsets']))==1 else 'NEAR_ONSET_CLUSTER','cluster_window_ticks':cluster_window,'evidence_level':'E1'})
    transitions=[]
    for previous,current in zip(chords,chords[1:]):
        a=set(previous['pitch_classes']);b=set(current['pitch_classes']);common=len(a&b);cost=_median([min(min((pc-other)%12,(other-pc)%12) for other in b) for pc in a]) if a and b else None
        transitions.append({'from_tick':previous['tick'],'to_tick':current['tick'],'from_label':previous['label'],'to_label':current['label'],'common_pitch_classes':common,'bass_motion_semitones':current['bass_pitch']-previous['bass_pitch'],'pitch_class_voice_leading_cost':None if cost is None else round(cost,3),'relationship':'SMOOTH' if common>=2 or (cost is not None and cost<=1) else 'CONTRASTING','evidence_level':'E1'})
    pitch_counts=Counter(n.note%12 for n in candidates);total=sum(pitch_counts.values());top=pitch_counts.most_common(2)
    dominance=(top[0][1]/total) if total and top else 0;separation=((top[0][1]-top[1][1])/total) if len(top)>1 else dominance
    if total>=24 and dominance>=.24 and separation>=.06:
        center={'status':'CANDIDATE','pitch_class':top[0][0],'name':PITCH_NAMES[top[0][0]],'confidence':round(min(.72,.38+dominance+separation),3),'evidence_level':'E1'}
    else:center={'status':'UNKNOWN','pitch_class':None,'name':None,'confidence':0.0,'evidence_level':'E0','reason':'insufficient_or_ambiguous_pitch_class_evidence'}
    gaps=[b['tick']-a['tick'] for a,b in zip(chords,chords[1:]) if b['tick']>a['tick']]
    return {'tonal_center':center,'simultaneous_chords':chords[:128],'chord_count':len(chords),'unclassified_chords':sum(row['label']=='UNCLASSIFIED' for row in chords),'harmonic_rhythm_median_beats':None if not gaps else round(_median(gaps)/max(1,tpb),4),'voice_leading':transitions[:127],'method':'simultaneous/near-onset pitch-class inspection; no key or functional harmony is invented'}


def _groove(notes,track_functions,tpb):
    by_key=defaultdict(list)
    for note in notes:by_key[(note.track_index,note.channel)].append(note)
    drums=[key for key,row in track_functions.items() if row.get('function')=='FOUNDATION_DRUM']
    basses=[key for key,row in track_functions.items() if row.get('function')=='FOUNDATION_BASS']
    rows=[];threshold=max(1,int(tpb)//32)
    for bass in basses:
        bass_onsets=[n.onset for n in by_key[bass]]
        for drum in drums:
            drum_onsets=[n.onset for n in by_key[drum]]
            if not bass_onsets or not drum_onsets:continue
            residuals=[onset-min(drum_onsets,key=lambda value:abs(value-onset)) for onset in bass_onsets]
            lock=sum(abs(value)<=threshold for value in residuals)/len(residuals);median=_median(residuals);median_abs=_median([abs(value) for value in residuals])
            feel='LOCKED' if lock>=.75 else 'RELAXED_OR_INDEPENDENT' if lock<.40 else 'MIXED'
            rows.append({'bass':{'track':bass[0],'channel':bass[1]+1},'drum':{'track':drum[0],'channel':drum[1]+1},'pairs':len(residuals),'median_offset_ticks':round(median,3),'median_absolute_offset_ticks':round(median_abs,3),'near_anchor_ratio':round(lock,4),'relationship':feel,'confidence':round(min(.9,.45+len(residuals)/100+.25*abs(lock-.5)*2),3),'evidence_level':'E1','instruction':'PRESERVE_RELATIONSHIP' if feel in ('LOCKED','MIXED') else 'DO_NOT_FORCE_LOCK_WITHOUT_GROUND_TRUTH'})
    return {'relationships':rows,'method':'nearest observed Drum onset for every Bass onset','mutations':0}


def _arrangement(musical_context):
    sections=musical_context.get('sections',[]);ensemble=musical_context.get('ensemble_sections',[]);rows=[]
    for index,section in enumerate(sections):
        ens=next((row for row in ensemble if row.get('section_index')==section.get('index')),{})
        functions=Counter(part.get('function','UNKNOWN') for part in ens.get('parts',[]))
        rows.append({'section_index':section.get('index'),'label':section.get('label'),'active_tracks':section.get('active_tracks',0),'density_notes_per_beat':section.get('density_notes_per_beat'),'velocity_proxy':section.get('velocity_median_proxy'),'focus_function':(ens.get('focus') or {}).get('function'),'functions':dict(functions),'masking_risks':len(ens.get('masking_alerts',[]))})
    if len(rows)>=2:
        first,last=rows[0],rows[-1];max_tracks=max(row['active_tracks'] for row in rows);development='LAYER_GROWTH' if max_tracks>first['active_tracks'] else 'STABLE_OR_REDUCED_ORCHESTRATION'
    else:development='UNKNOWN'
    max_density=max((float(row.get('density_notes_per_beat') or 0) for row in rows),default=0);max_tracks=max((int(row.get('active_tracks') or 0) for row in rows),default=0);previous=None
    for row in rows:
        density=float(row.get('density_notes_per_beat') or 0)/max(.001,max_density);tracks=float(row.get('active_tracks') or 0)/max(1,max_tracks);velocity=float(row.get('velocity_proxy') or 0)/127;mask=min(1,row.get('masking_risks',0)/2);tension=.38*density+.27*tracks+.20*velocity+.15*mask;row['tension_proxy']=round(tension,4)
        if previous is None:trajectory='START'
        elif tension>=previous+.12:trajectory='BUILD'
        elif tension<=previous-.12:trajectory='RELEASE'
        else:trajectory='STABLE'
        row['trajectory_from_previous']=trajectory;previous=tension
    return {'sections':rows,'development':development,'tension_method':'density + active layers + velocity proxy + masking; descriptive, not emotional ground truth','mutations':0}


def _interaction(notes_by_key,track_functions,tpb):
    foreground=[key for key,row in track_functions.items() if row.get('function') in ('LEAD','COUNTER_LINE','RIFF_OSTINATO')];rows=[];tpb=max(1,int(tpb))
    activity={key:{n.onset//tpb for n in notes_by_key.get(key,[])} for key in foreground}
    for index,a in enumerate(foreground):
        for b in foreground[index+1:]:
            aw,bw=activity[a],activity[b];union=aw|bw
            if not union:continue
            overlap=len(aw&bw)/len(union);alternation=len((aw-bw)|(bw-aw))/len(union)
            if len(aw)>=2 and len(bw)>=2 and overlap<=.30 and alternation>=.70:relationship='CALL_RESPONSE_CANDIDATE';confidence=.68
            elif overlap>=.65:relationship='COUPLED_OR_COMPETING';confidence=.62
            else:relationship='MIXED_SPACE';confidence=.52
            rows.append({'a':{'track':a[0],'channel':a[1]+1,'function':track_functions[a].get('function')},'b':{'track':b[0],'channel':b[1]+1,'function':track_functions[b].get('function')},'active_windows_union':len(union),'overlap_ratio':round(overlap,4),'alternation_ratio':round(alternation,4),'relationship':relationship,'confidence':confidence,'evidence_level':'E1','limitation':'Beat-window alternation is not proof of intentional call and response.'})
    return {'relationships':rows,'window_beats':1,'mutations':0}


def analyze_musical_understanding(mid,notes,contexts,musical_context):
    function_rows=musical_context.get('track_functions',[]);track_functions={(row['track'],int(row['channel'])-1):row for row in function_rows};by_key=defaultdict(list)
    for note in notes:by_key[(note.track_index,note.channel)].append(note)
    narratives=[];observations=[];uncertainties=[]
    for key in sorted(contexts):
        ctx=contexts[key];function=track_functions.get(key,{});phrases=_phrase_rows(by_key.get(key,[]),mid.ticks_per_beat);confidence=float(function.get('confidence',0))
        if function.get('function')=='UNKNOWN':uncertainties.append({'domain':'track_function','track':key[0],'channel':key[1]+1,'reason':'insufficient evidence','required_action':'manual role label or ground truth'})
        narratives.append({'track':key[0],'channel':key[1]+1,'sound':ctx.identity.name,'family':ctx.family,'role':ctx.role,'function':function.get('function','UNKNOWN'),'function_confidence':confidence,'function_evidence':function.get('evidence_level','E0'),'phrases':phrases,'interpretation':('Carries '+function.get('function','UNKNOWN').lower().replace('_',' ')+' material.' if function.get('function')!='UNKNOWN' else 'Musical function is not proven.'),'mutations':0})
    melody=_melodic_narrative(by_key,track_functions,mid.ticks_per_beat);harmony=_harmony(notes,track_functions,mid.ticks_per_beat);groove=_groove(notes,track_functions,mid.ticks_per_beat);arrangement=_arrangement(musical_context);interaction=_interaction(by_key,track_functions,mid.ticks_per_beat)
    for row in groove['relationships']:
        observations.append(_statement('groove',f"Bass track {row['bass']['track']} and Drum track {row['drum']['track']} show a {row['relationship'].lower().replace('_',' ')} relationship.",row['confidence'],'E1',{'near_anchor_ratio':row['near_anchor_ratio'],'median_offset_ticks':row['median_offset_ticks']},'Nearest-onset correlation does not prove artistic causation.'))
    if arrangement['development']=='LAYER_GROWTH':observations.append(_statement('arrangement','Energy development is driven at least partly by adding active layers, not only by velocity.',.72,'E1',{'sections':len(arrangement['sections'])},'Section labels remain heuristic unless serialized by a Style.'))
    if harmony['tonal_center']['status']=='UNKNOWN':uncertainties.append({'domain':'harmony','reason':harmony['tonal_center'].get('reason'),'required_action':'provide chord/key ground truth; do not transpose or reharmonize'})
    for row in interaction['relationships']:
        observations.append(_statement('interaction',f"Tracks {row['a']['track']} and {row['b']['track']} show {row['relationship'].lower().replace('_',' ')} activity.",row['confidence'],'E1',{'overlap_ratio':row['overlap_ratio'],'alternation_ratio':row['alternation_ratio']},row['limitation']))
    suggestions=[]
    for section in musical_context.get('ensemble_sections',[]):
        if section.get('masking_alerts'):suggestions.append({'domain':'orchestration','section':section.get('section_label'),'action':'REVIEW_REGISTER_OR_DENSITY','reason':'overlapping active registers may mask each other','confidence':.62,'evidence_level':'E1','apply_authority':False})
        if section.get('status')=='FOCUS_UNCLEAR':suggestions.append({'domain':'focus','section':section.get('section_label'),'action':'IDENTIFY_INTENDED_LEAD_BEFORE_EDITING','reason':'background texture currently has highest salience','confidence':.58,'evidence_level':'E1','apply_authority':False})
    for relation in groove['relationships']:
        if relation['relationship'] in ('LOCKED','MIXED'):suggestions.append({'domain':'groove','action':'PRESERVE_DRUM_BASS_MICROTIMING','reason':'stable observed ensemble relationship','confidence':relation['confidence'],'evidence_level':'E1','apply_authority':False})
    for relation in interaction['relationships']:
        if relation['relationship']=='CALL_RESPONSE_CANDIDATE':suggestions.append({'domain':'interaction','action':'PRESERVE_ALTERNATING_SPACE','reason':'foreground parts appear to exchange activity instead of sounding continuously together','confidence':relation['confidence'],'evidence_level':'E1','apply_authority':False})
        elif relation['relationship']=='COUPLED_OR_COMPETING':suggestions.append({'domain':'interaction','action':'REVIEW_FOREGROUND_OVERLAP','reason':'foreground parts occupy many of the same beat windows','confidence':relation['confidence'],'evidence_level':'E1','apply_authority':False})
    summary=[]
    counts=musical_context.get('function_counts',{})
    if counts:summary.append('Detected musical functions: '+', '.join(f'{name}={count}' for name,count in sorted(counts.items()))+'.')
    if groove['relationships']:summary.append('Drum/Bass timing is described relationally and is not independently humanized.')
    if arrangement['development']!='UNKNOWN':summary.append('Arrangement development: '+arrangement['development'].lower().replace('_',' ')+'.')
    summary.append('No creative edit is authorized by this analysis alone.')
    return {'schema':'PA800_MUSICAL_UNDERSTANDING_V2','analyzer_only':True,'mutations':0,'authority_granted':False,'content_type':musical_context.get('content_type'),'musician_summary':' '.join(summary),'track_narratives':narratives,'melody':melody,'harmony':harmony,'groove':groove,'interaction':interaction,'arrangement':arrangement,'observations':observations,'suggestions':suggestions,'uncertainties':uncertainties,'limits':['SMF does not reveal audible timbre or undocumented Pa800 oscillator behavior.','Song section, emotional tension and harmonic function require ground truth before creative AUTO use.']}