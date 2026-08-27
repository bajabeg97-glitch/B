"""Phrase and ensemble-aware performance direction with shadow-first authority."""
from __future__ import annotations

from collections import defaultdict
import statistics

from ..models import Change
from ..utils import clamp
from ..neural.corpus_router import route_authority

SECTION_OFFSETS={'INTRO':-2,'VERSE_OR_BODY':0,'CHORUS':3,'SOLO':2,'BREAK':-3,'ENDING':-1,'WHOLE_SONG':0,'STYLE_WHOLE_UNLABELED':0,'Variation 1':-2,'Variation 2':-1,'Variation 3':1,'Variation 4':2,'Fill 1':2,'Fill 2':2,'Intro 1':-2,'Intro 2':-1,'Intro 3':0,'Ending 1':-1,'Ending 2':0,'Ending 3':1}
FUNCTION_OFFSETS={'LEAD':1,'COUNTER_LINE':1,'RIFF_OSTINATO':1,'HARMONIC_COMP':-1,'PAD_BACKGROUND':-2,'FOUNDATION_DRUM':0,'FOUNDATION_PERC':0,'FOUNDATION_BASS':0,'ORNAMENT_FX':0,'UNKNOWN':0}


def _median(values,default=0.0):return float(statistics.median(values)) if values else float(default)


def _percentile(values,q):
    if not values:return 0.0
    values=sorted(values);pos=(len(values)-1)*q;lo=int(pos);hi=min(len(values)-1,lo+1);fraction=pos-lo
    return values[lo]*(1-fraction)+values[hi]*fraction


def _iqr(values):return _percentile(values,.75)-_percentile(values,.25)


def segment_phrases(notes,tpb):
    arr=sorted(notes,key=lambda n:(n.onset,n.note,n.off));tpb=max(1,tpb)
    if not arr:return []
    iois=[b.onset-a.onset for a,b in zip(arr,arr[1:]) if b.onset>a.onset];threshold=max(tpb,int(_median(iois,tpb)*2.5));phrases=[];current=[arr[0]]
    for note in arr[1:]:
        previous=current[-1];gap=note.onset-previous.off
        if gap>threshold:phrases.append(current);current=[note]
        else:current.append(note)
    phrases.append(current);return phrases


def _section_for_tick(sections,tick):
    for section in sections:
        if int(section.get('start_tick',0))<=tick<int(section.get('end_tick',tick+1)):return section
    return sections[-1] if sections else {'index':0,'label':'WHOLE_SONG','confidence':0,'evidence_level':'E0','start_tick':0,'end_tick':tick+1}


def _phrase_row(index,phrase,function_row,section):
    values=[n.velocity for n in phrase];first=_median(values[:max(1,len(values)//3)]);last=_median(values[-max(1,len(values)//3):]);function=function_row.get('function','UNKNOWN');label=section.get('label','WHOLE_SONG');offset=SECTION_OFFSETS.get(label,0)+FUNCTION_OFFSETS.get(function,0);offset=max(-4,min(4,offset))
    return {'phrase_index':index,'start_tick':phrase[0].onset,'end_tick':max(n.off for n in phrase),'notes':len(phrase),'function':function,'section_index':section.get('index'),'section_label':label,'section_evidence':section.get('evidence_level','E0'),'velocity_median':round(_median(values),3),'velocity_iqr_before':round(_iqr(values),3),'velocity_contour_delta':round(last-first,3),'recommended_velocity_offset':offset,'reason':['section_energy_'+label.lower(),'function_'+function.lower()],'timing_suggestion_only':True,'gate_suggestion_only':True}


def _nearest_offset(reference,target):
    if not reference or not target:return None
    ref=sorted({n.onset for n in reference});offsets=[]
    for note in target:
        nearest=min(ref,key=lambda tick:abs(note.onset-tick));offsets.append(note.onset-nearest)
    return _median(offsets) if offsets else None


def _solo_ornaments(phrase,tpb):
    """Describe existing solo ornaments without changing pitch or note count."""
    arr=sorted(phrase,key=lambda note:(note.onset,note.note,note.occurrence));rows=[];covered=set();tpb=max(1,int(tpb))
    for start in range(max(0,len(arr)-3)):
        run=[arr[start]]
        for note in arr[start+1:]:
            previous=run[-1]
            if note.onset-previous.onset>tpb//3 or not 1<=abs(note.note-previous.note)<=2:break
            run.append(note)
        if len(run)>=4 and all(run[index].note==run[index+2].note for index in range(len(run)-2)):
            ids=tuple(note.on_index for note in run)
            if not any(index in covered for index in ids):
                covered.update(ids);rows.append({'kind':'TRILL','start_tick':run[0].onset,'end_tick':run[-1].off,'notes':len(run),'interval_semitones':abs(run[1].note-run[0].note),'gold_route':route_authority('ORNAMENT'),'correction':'PRESERVE_PITCH_BOUNDED_SPACING'})
    for index,note in enumerate(arr):
        if note.on_index in covered:continue
        previous=arr[index-1] if index else None;nxt=arr[index+1] if index+1<len(arr) else None
        if nxt and note.duration<=max(1,tpb//8) and 1<=abs(nxt.note-note.note)<=4 and nxt.onset-note.onset<=tpb//3:kind='GRACE_NOTE'
        elif previous and previous.note==note.note and note.onset-previous.onset<=tpb//3:kind='REPEATED_ORNAMENT'
        elif previous and nxt and previous.note==nxt.note and 1<=abs(note.note-previous.note)<=2 and note.duration<=tpb//4:kind='MORDENT_TURN'
        else:continue
        rows.append({'kind':kind,'start_tick':note.onset,'end_tick':note.off,'notes':1,'gold_route':route_authority('ORNAMENT'),'correction':'PRESERVE_PITCH_BOUNDED_TIMING_GATE'})
    return rows


def _existing_cc11(mid,key):
    tick=0;occurrence=0;rows=[]
    for index,message in enumerate(mid.tracks[key[0]]):
        tick+=message.time
        if message.type=='control_change' and message.channel==key[1] and message.control==11:
            rows.append({'index':index,'tick':tick,'occurrence':occurrence,'value':message.value});occurrence+=1
    return rows


def run_performance_director(mid,notes,contexts,musical_context,config,report):
    policy='off' if not config.enable_performance_director else 'apply' if config.apply_performance_director else 'shadow'
    if policy=='off':report.performance_director={'enabled':False,'policy':'off','applied_changes':0,'phrases':[],'interactions':[]};return
    function_rows={(row['track'],row['channel']-1):row for row in musical_context.get('track_functions',[])};sections=musical_context.get('sections',[]);by_key=defaultdict(list)
    for note in notes:by_key[(note.track_index,note.channel)].append(note)
    phrase_rows=[];applied=0;eligible=0;solo_rows=[];expression_mutations=[]
    for key,arr in sorted(by_key.items()):
        ctx=contexts.get(key);function_row=function_rows.get(key,{'function':'UNKNOWN','evidence_level':'E0'});phrases=segment_phrases(arr,mid.ticks_per_beat)
        solo=bool(function_row.get('function') in ('LEAD','COUNTER_LINE') or (ctx and (str(ctx.role).upper() in ('SOLO','LEAD','COUNTER') or str(ctx.family).upper() in ('REED','PIPE','ACCORDION_REED','SYNTH_LEAD','ETHNIC'))))
        ornaments=[row for phrase in phrases for row in _solo_ornaments(phrase,mid.ticks_per_beat)] if solo else []
        cc11=_existing_cc11(mid,key) if solo else [];expression_status='NOT_SOLO';expression_changes=0
        expression_authorized=bool(policy=='apply' and getattr(config,'factory_gold_max',False) and function_row.get('evidence_level')=='E2' and ctx and not ctx.identity.conflict)
        if solo:
            expression_status='NO_EXISTING_CC11_PRESERVE' if not cc11 else 'SHADOW_EXISTING_CC11'
            if cc11 and expression_authorized:
                center=_median([row['value'] for row in cc11]);span=max(1,cc11[-1]['tick']-cc11[0]['tick'])
                for event in cc11:
                    position=(event['tick']-cc11[0]['tick'])/span;shape=-2 if position<.15 else -3 if position>.85 else 3 if .45<=position<=.70 else 1
                    target=int(clamp(round(event['value']+(center-event['value'])*.08+shape),1,127));delta=max(-4,min(4,target-event['value']));new=int(clamp(event['value']+delta,1,127))
                    if new!=event['value']:
                        message=mid.tracks[key[0]][event['index']];mid.tracks[key[0]][event['index']]=message.copy(value=new);expression_changes+=1
                        expression_mutations.append({'track':key[0],'channel':key[1],'control':11,'occurrence':event['occurrence'],'tick':event['tick'],'old':event['value'],'new':new,'source':'gold_solo_expression_existing_cc11'})
                expression_status='APPLIED_EXISTING_CC11_CONTOUR' if expression_changes else 'ALREADY_SHAPED'
            elif cc11 and policy=='apply' and not expression_authorized:expression_status='BLOCKED_EXPRESSION_EVIDENCE_GATE'
            solo_rows.append({'track':key[0],'channel':key[1]+1,'sound':ctx.identity.name if ctx else None,'function':function_row.get('function'),'ornaments':ornaments,'ornament_count':len(ornaments),'trills':sum(row['kind']=='TRILL' for row in ornaments),'existing_cc11_events':len(cc11),'expression_changes':expression_changes,'expression_status':expression_status,'expression_route':route_authority('EXPRESSION_CC11'),'pitch_changes':0,'note_count_changes':0})
        for index,phrase in enumerate(phrases):
            section=_section_for_tick(sections,phrase[0].onset);row=_phrase_row(index,phrase,function_row,section);row.update({'track':key[0],'channel':key[1]+1,'sound':ctx.identity.name if ctx else None,'function_evidence':function_row.get('evidence_level','E0')})
            authorized=bool(policy=='apply' and function_row.get('evidence_level')=='E2' and section.get('evidence_level')=='E2' and ctx and not ctx.identity.conflict)
            row['apply_authorized']=authorized;changed=0;row['apply_status']='SHADOW_ONLY' if policy=='shadow' and row['recommended_velocity_offset'] else 'PRESERVE'
            if policy=='apply' and row['recommended_velocity_offset'] and not authorized:row['apply_status']='BLOCKED_EVIDENCE_GATE'
            if authorized and row['recommended_velocity_offset']:
                eligible+=1;track=mid.tracks[key[0]];mutable=[note for note in phrase if not note.protected];before=[note.velocity for note in mutable];proposed=[int(clamp(note.velocity+row['recommended_velocity_offset'],1,127)) for note in mutable];before_iqr=_iqr(before);after_iqr=_iqr(proposed);retention=1.0 if before_iqr<=0 else after_iqr/before_iqr
                row['iqr_retention']=round(retention,4)
                if retention+1e-9<float(getattr(config,'velocity_min_iqr_retention',.75)):row['apply_status']='BLOCKED_IQR_GUARD'
                else:
                    for note,new in zip(mutable,proposed):
                        if new!=note.velocity:
                            old=note.velocity;track[note.on_index]=track[note.on_index].copy(velocity=new);note.velocity=new;changed+=1;applied+=1
                            report.changes.append(Change(key[0],note.on_index,'performance_velocity',old,new,'section_function_phrase_offset',ctx.identity.name or ctx.family,channel=note.channel,note=note.note,occurrence=note.occurrence,protected=note.protected))
                    row['apply_status']='APPLIED' if changed else 'NO_CHANGE'
            values_after=[note.velocity for note in phrase];row['velocity_median_after']=round(_median(values_after),3);row['velocity_iqr_after']=round(_iqr(values_after),3);row['applied_changes']=changed;phrase_rows.append(row)
    functions=defaultdict(list)
    for key,arr in by_key.items():functions[function_rows.get(key,{}).get('function','UNKNOWN')].extend(arr)
    interactions=[];drum=functions.get('FOUNDATION_DRUM',[]);bass=functions.get('FOUNDATION_BASS',[]);perc=functions.get('FOUNDATION_PERC',[]);offset=_nearest_offset(drum,bass)
    if offset is not None:interactions.append({'kind':'DRUM_BASS_ONSET_RELATION','median_bass_minus_drum_ticks':round(offset,3),'median_offset_beats':round(offset/max(1,mid.ticks_per_beat),4),'recommendation':'REVIEW_ALIGNMENT' if abs(offset)>mid.ticks_per_beat*.08 else 'LOCKED','evidence_level':'E1','applied':False})
    perc_offset=_nearest_offset(drum,perc)
    if perc_offset is not None:interactions.append({'kind':'DRUM_PERC_ONSET_RELATION','median_perc_minus_drum_ticks':round(perc_offset,3),'median_offset_beats':round(perc_offset/max(1,mid.ticks_per_beat),4),'recommendation':'REVIEW_ALIGNMENT' if abs(perc_offset)>mid.ticks_per_beat*.08 else 'LOCKED','evidence_level':'E1','applied':False})
    lead=functions.get('LEAD',[]);background=functions.get('HARMONIC_COMP',[])+functions.get('PAD_BACKGROUND',[])
    if lead and background:
        margin=_median([n.velocity for n in lead])-_median([n.velocity for n in background]);interactions.append({'kind':'LEAD_BACKGROUND_VELOCITY_MARGIN','margin':round(margin,3),'recommendation':'RAISE_LEAD_OR_REDUCE_BACKGROUND' if margin<-3 else 'REDUCE_EXCESSIVE_LEAD' if margin>28 else 'BALANCED_RANGE','evidence_level':'E1','applied':False})
    report.performance_director={'schema':'PA800_PERFORMANCE_DIRECTOR_V1','enabled':True,'policy':policy,'shadow_first':True,'song_e1_mutation_allowed':False,'phrases':phrase_rows,'phrase_count':len(phrase_rows),'eligible_e2_phrases':eligible,'applied_changes':applied,'solo_tracks':solo_rows,'solo_track_count':len(solo_rows),'ornament_count':sum(row['ornament_count'] for row in solo_rows),'trill_count':sum(row['trills'] for row in solo_rows),'expression_event_mutations':expression_mutations,'expression_changes':len(expression_mutations),'expression_inserts':0,'interactions':interactions,'pass':policy!='apply' or all(row['applied_changes']==0 or row['apply_authorized'] for row in phrase_rows)}
