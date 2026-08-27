from collections import Counter, defaultdict, deque


VELOCITY_KINDS={'velocity','velocity_conductor','performance_velocity','velocity_budget','baja_percussion_40pct'}


def _freeze(value):
    if isinstance(value,(list,tuple)): return tuple(_freeze(x) for x in value)
    if isinstance(value,dict): return tuple(sorted((k,_freeze(v)) for k,v in value.items()))
    return value


def _scan(mid):
    out={
        'smf_type':mid.type,'ticks_per_beat':mid.ticks_per_beat,'tracks':len(mid.tracks),'track_ends':[],
        'notes':Counter(),'note_on_count':0,'note_off_count':0,'note_integrity':True,
        'note_records':{},'immutable':[],'banks':[],'programs':[],'fx':[],
        'articulations':[],'expression':[],'address_sequence':[],
    }
    active=defaultdict(deque);note_occ=defaultdict(int);event_occ=defaultdict(int)
    pending_address_refs=defaultdict(lambda:[None,None]);committed_address_refs=defaultdict(lambda:[None,None,None])
    for ti,tr in enumerate(mid.tracks):
        tick=0
        for ordinal,msg in enumerate(tr):
            tick+=msg.time;ch=getattr(msg,'channel',None)
            if msg.type=='note_on' and msg.velocity>0:
                base=(ti,ch,msg.note);occurrence=note_occ[base];note_occ[base]+=1;key=(*base,occurrence)
                out['notes'][(ti,ch,msg.note)]+=1;out['note_on_count']+=1
                out['note_records'][key]={'track':ti,'channel':ch,'note':msg.note,'occurrence':occurrence,'onset':tick,'off':None,'velocity':msg.velocity,'on_ordinal':ordinal,'off_ordinal':None,'on_type':'note_on','off_type':None,'off_velocity':None,'sound_context_ref':tuple(committed_address_refs[(ti,ch)])}
                active[(ti,ch,msg.note)].append(key);continue
            if msg.type in ('note_off','note_on') and (msg.type=='note_off' or msg.velocity==0):
                out['note_off_count']+=1;q=active[(ti,ch,msg.note)]
                if not q:out['note_integrity']=False
                else:
                    key=q.popleft();row=out['note_records'][key];row.update({'off':tick,'off_ordinal':ordinal,'off_type':msg.type,'off_velocity':getattr(msg,'velocity',None)})
                    if tick<row['onset']:out['note_integrity']=False
                continue
            if msg.type=='control_change' and msg.control in (0,32):
                base=(ti,ch,msg.control);occurrence=event_occ[('bank',*base)];event_occ[('bank',*base)]+=1
                pending_address_refs[(ti,ch)][0 if msg.control==0 else 1]=occurrence
                out['banks'].append((ti,ch,msg.control,occurrence,tick,msg.value));out['address_sequence'].append((ti,ch,tick,'bank',msg.control,occurrence));continue
            if msg.type=='program_change':
                base=(ti,ch);occurrence=event_occ[('program',*base)];event_occ[('program',*base)]+=1
                refs=pending_address_refs[(ti,ch)];committed_address_refs[(ti,ch)]=[refs[0],refs[1],occurrence]
                out['programs'].append((ti,ch,occurrence,tick,msg.program));out['address_sequence'].append((ti,ch,tick,'program',occurrence));continue
            if msg.type=='control_change' and msg.control in (91,93):
                base=(ti,ch,msg.control);occurrence=event_occ[('fx',*base)];event_occ[('fx',*base)]+=1
                out['fx'].append((ti,ch,msg.control,occurrence,tick,msg.value));continue
            if msg.type=='control_change' and msg.control in (80,81):
                base=(ti,ch,msg.control);occurrence=event_occ[('articulation',*base)];event_occ[('articulation',*base)]+=1
                out['articulations'].append((ti,ch,msg.control,occurrence,tick,ordinal,msg.value));continue
            if msg.type=='control_change' and msg.control==11:
                base=(ti,ch,msg.control);occurrence=event_occ[('expression',*base)];event_occ[('expression',*base)]+=1
                out['expression'].append((ti,ch,msg.control,occurrence,tick,msg.value));continue
            data=msg.dict();data.pop('time',None)
            out['immutable'].append((ti,tick,msg.type,_freeze(data)))
        out['track_ends'].append(tick)
    if any(active.values()):out['note_integrity']=False
    return out


def _row_value(row,name,default=None):
    return row.get(name,default) if isinstance(row,dict) else getattr(row,name,default)


def _verify_note_changes(before,after,changes):
    if set(before)!=set(after):return False,[],{'reason':'note_identity_set_mismatch','missing_after':[list(key) for key in sorted(set(before)-set(after))[:16]],'new_after':[list(key) for key in sorted(set(after)-set(before))[:16]]}
    expected={key:{name:row[name] for name in ('onset','off','velocity')} for key,row in before.items()}
    ledger=[]
    for index,change in enumerate(changes or []):
        track=_row_value(change,'track');channel=_row_value(change,'channel');note=_row_value(change,'note');occurrence=_row_value(change,'occurrence');kind=_row_value(change,'kind');old=_row_value(change,'old');new=_row_value(change,'new')
        if None in (track,channel,note,occurrence):return False,ledger,{'reason':'incomplete_change_identity','change_index':index,'kind':kind}
        key=(int(track),int(channel),int(note),int(occurrence));current=expected.get(key)
        if current is None:return False,ledger,{'reason':'unknown_change_identity','change_index':index,'key':list(key),'kind':kind}
        if kind in VELOCITY_KINDS:
            if current['velocity']!=old or not 1<=int(new)<=127:return False,ledger,{'reason':'velocity_chain_mismatch','change_index':index,'key':list(key),'expected_old':current['velocity'],'reported_old':old,'new':new}
            field='velocity';current[field]=int(new)
        elif kind=='timing':
            if current['onset']!=old:return False,ledger,{'reason':'timing_chain_mismatch','change_index':index,'key':list(key),'expected_old':current['onset'],'reported_old':old,'new':new}
            shift=int(new)-int(old);current['onset']=int(new);current['off']=int(current['off'])+shift;field='onset+off'
        elif kind=='gate':
            if current['off']!=old:return False,ledger,{'reason':'gate_chain_mismatch','change_index':index,'key':list(key),'expected_old':current['off'],'reported_old':old,'new':new}
            current['off']=int(new);field='off'
        else:
            return False,ledger,{'reason':'unsupported_note_change_kind','change_index':index,'key':list(key),'kind':kind}
        ledger.append({'authority_id':'NOTE-%06d'%(index+1),'mutation':'NOTE_'+str(kind).upper(),'track':key[0],'channel':key[1],'note':key[2],'occurrence':key[3],'field':field,'old':old,'new':new,'reason':_row_value(change,'reason','')})
    for key,row in before.items():
        result=after[key];target=expected[key]
        if any(result[name]!=target[name] for name in ('onset','off','velocity')):return False,ledger,{'reason':'final_note_value_mismatch','key':list(key),'expected':{name:target[name] for name in ('onset','off','velocity')},'actual':{name:result[name] for name in ('onset','off','velocity')}}
        if any(result[name]!=row[name] for name in ('track','channel','note','occurrence','on_type','off_type','off_velocity')):return False,ledger,{'reason':'note_serialization_mismatch','key':list(key),'before':{name:row[name] for name in ('on_type','off_type','off_velocity')},'after':{name:result[name] for name in ('on_type','off_type','off_velocity')}}
        if row['off'] is not None and row['off']>row['onset'] and result['off']<=result['onset']:return False,ledger,{'reason':'non_positive_duration','key':list(key),'onset':result['onset'],'off':result['off']}
    return True,ledger,{'reason':'match'}


def _verify_address_events(before,after,targets):
    if [x[:-1] for x in before]!=[x[:-1] for x in after]:return False
    for b,a in zip(before,after):
        ti,ch,control,_occurrence,_tick,value=a;target=targets.get((ti,ch))
        if target is None:
            if a!=b:return False
        elif value!=(target[0] if control==0 else target[1]):return False
    return True


def _verify_program_events(before,after,targets):
    if [x[:-1] for x in before]!=[x[:-1] for x in after]:return False
    for b,a in zip(before,after):
        ti,ch,_occurrence,_tick,value=a;target=targets.get((ti,ch))
        if target is None:
            if a!=b:return False
        elif value!=target[2]:return False
    return True


def _verify_fx(before,after,allowed_channels,authorized_events):
    if [x[:-1] for x in before]!=[x[:-1] for x in after]:return False,[]
    if authorized_events is None:
        for b,a in zip(before,after):
            ti,ch,_control,_occurrence,_tick,value=a
            if (ti,ch) not in allowed_channels and a!=b:return False,[]
            if not 0<=value<=127:return False,[]
        return True,[]
    expected={x[:-1]:x[-1] for x in before};ledger=[]
    for index,row in enumerate(authorized_events):
        key=(int(row['track']),int(row['channel']),int(row['control']),int(row['occurrence']),int(row['tick']))
        if key not in expected or expected[key]!=int(row['old']):return False,ledger
        new=int(row['new'])
        if not 0<=new<=127:return False,ledger
        expected[key]=new;ledger.append({'authority_id':'FX-%06d'%(index+1),'mutation':'FX_SEND','track':key[0],'channel':key[1],'control':key[2],'occurrence':key[3],'tick':key[4],'old':int(row['old']),'new':new,'source':row.get('source','')})
    actual={x[:-1]:x[-1] for x in after}
    return actual==expected,ledger


def _verify_expression(before,after,authorized_events):
    if [row[:-1] for row in before]!=[row[:-1] for row in after]:return False,[]
    expected={row[:-1]:row[-1] for row in before};ledger=[]
    for index,row in enumerate(authorized_events or []):
        key=(int(row['track']),int(row['channel']),11,int(row['occurrence']),int(row['tick']))
        if key not in expected or expected[key]!=int(row['old']):return False,ledger
        new=int(row['new'])
        if not 0<=new<=127:return False,ledger
        expected[key]=new;ledger.append({'authority_id':'EXP-%06d'%(index+1),'mutation':'EXPRESSION_CC11','track':key[0],'channel':key[1],'control':11,'occurrence':key[3],'tick':key[4],'old':int(row['old']),'new':new,'source':row.get('source','')})
    return {row[:-1]:row[-1] for row in after}==expected,ledger


def _verify_articulations(before,after,authorized_insertions,note_records):
    before_count=Counter((ti,ch,tick,control,value) for ti,ch,control,_occ,tick,_ord,value in before)
    after_count=Counter((ti,ch,tick,control,value) for ti,ch,control,_occ,tick,_ord,value in after)
    additions=[];ledger=[]
    for index,item in enumerate(authorized_insertions or []):
        ti,ch,tick,control,value=item[:5];additions.append((ti,ch,tick,control,value))
        ledger.append({'authority_id':'ART-%06d'%(index+1),'mutation':'ARTICULATION_PULSE','track':ti,'channel':ch,'tick':tick,'control':control,'value':value,'note':item[5] if len(item)>5 else None,'occurrence':item[6] if len(item)>6 else None})
    if after_count!=before_count+Counter(additions):return False,ledger
    grouped=defaultdict(dict)
    for item in authorized_insertions or []:
        ti,ch,tick,control,value=item[:5];note=item[5] if len(item)>5 else None;occurrence=item[6] if len(item)>6 else None
        grouped[(ti,ch,tick,control,note,occurrence)][value]=True
    for ti,ch,tick,control,note,occurrence in grouped:
        if not {0,127}<=set(grouped[(ti,ch,tick,control,note,occurrence)]):return False,ledger
        on_ord=[row[5] for row in after if row[0]==ti and row[1]==ch and row[2]==control and row[4]==tick and row[6]==127]
        off_ord=[row[5] for row in after if row[0]==ti and row[1]==ch and row[2]==control and row[4]==tick and row[6]==0]
        if note is not None and occurrence is not None:
            target=note_records.get((ti,ch,note,occurrence));note_ord=[] if target is None or target['onset']!=tick else [target['on_ordinal']]
        else:
            note_ord=[row['on_ordinal'] for row in note_records.values() if row['track']==ti and row['channel']==ch and row['onset']==tick]
        if not any(a<n<b for a in on_ord for n in note_ord for b in off_ord):return False,ledger
    return True,ledger


def verify(before,after,authorized_sound_targets=None,authorized_fx_channels=None,authorized_articulation_insertions=None,authorized_note_changes=None,authorized_fx_events=None,authorized_expression_events=None):
    """Canonical verifier: only explicitly authorized field-level diffs pass."""
    targets={k:tuple(v) for k,v in (authorized_sound_targets or {}).items()};fx_channels=set(authorized_fx_channels or ())
    a=_scan(before);b=_scan(after)
    note_ok,note_ledger,note_diagnostics=_verify_note_changes(a['note_records'],b['note_records'],authorized_note_changes) if authorized_note_changes is not None else (True,[],{'reason':'not_requested'})
    fx_ok,fx_ledger=_verify_fx(a['fx'],b['fx'],fx_channels,authorized_fx_events)
    expression_ok,expression_ledger=_verify_expression(a['expression'],b['expression'],authorized_expression_events)
    articulation_ok,articulation_ledger=_verify_articulations(a['articulations'],b['articulations'],authorized_articulation_insertions or [],b['note_records'])
    checks={
        'smf_type':a['smf_type']==b['smf_type'],
        'ticks_per_beat':a['ticks_per_beat']==b['ticks_per_beat'],
        'tracks':a['tracks']==b['tracks'],'track_ends':a['track_ends']==b['track_ends'],
        'notes':a['notes']==b['notes'],'note_event_counts':a['note_on_count']==b['note_on_count'] and a['note_off_count']==b['note_off_count'],
        'note_integrity_before':a['note_integrity'],'note_integrity_after':b['note_integrity'],
        'canonical_note_diff':note_ok,'immutable_events':a['immutable']==b['immutable'],
        'semantic_event_order':all(a['note_records'][key]['sound_context_ref']==b['note_records'].get(key,{}).get('sound_context_ref') for key in a['note_records']),
        'address_event_order':a['address_sequence']==b['address_sequence'],
        'banks':_verify_address_events(a['banks'],b['banks'],targets),'programs':_verify_program_events(a['programs'],b['programs'],targets),
        'fx_sends':fx_ok,'expression_cc11':expression_ok,'articulation_events':articulation_ok,
    }
    checks['authorized_sound_channels']=len(targets);checks['authorized_fx_channels']=len(fx_channels);checks['authorized_articulation_events']=len(authorized_articulation_insertions or []);checks['authorized_note_changes']=len(authorized_note_changes or []);checks['authorized_fx_events']=len(authorized_fx_events or []);checks['authorized_expression_events']=len(authorized_expression_events or [])
    checks['mutation_ledger']=note_ledger+fx_ledger+expression_ledger+articulation_ledger
    checks['note_diff_diagnostics']=note_diagnostics
    checks['pass']=all(v for k,v in checks.items() if not k.startswith('authorized_') and k!='mutation_ledger')
    return checks
