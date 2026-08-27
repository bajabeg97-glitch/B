"""Lossless MIDI/event representation for future neural proposal models."""
from __future__ import annotations

import base64
import hashlib
import json
import os
import tempfile
from collections import Counter,defaultdict
from bisect import bisect_right
import statistics
from pathlib import Path

from ..analysis.context import build_contexts,detect_content_type_details
from ..analysis.meter_map import _build_bar_spans
from ..core.midi_io import absolute_track,extract_notes,load_midi
from ..profiles.registry import ProfileRegistry

SCHEMA='PA800_NEURAL_EVENT_CONTRACT_V1'
SENSITIVE_CONTROLLERS={1,2,64,80,81}
PERMANENT_PRESERVE_FAMILIES={'SFX','SYNTH_FX','CYCLE','RANDOM','WAVE_SEQUENCE'}


def _sha256_bytes(data):return hashlib.sha256(data).hexdigest()


def _json_value(value):
    if isinstance(value,(bytes,bytearray,tuple)):return list(value)
    if isinstance(value,list):return [_json_value(item) for item in value]
    if isinstance(value,dict):return {str(key):_json_value(item) for key,item in value.items()}
    return value


def _message_payload(message):
    try:return _json_value(message.dict())
    except Exception:
        return {'type':message.type,'time':int(getattr(message,'time',0)),'repr':str(message)}


def _source_group_id(mid,notes,contexts):
    """Fingerprint musical shape while ignoring velocity and global transposition."""
    rows=[]
    by_track=defaultdict(list)
    for note in notes:by_track[(note.track_index,note.channel)].append(note)
    for key in sorted(by_track):
        group=sorted(by_track[key],key=lambda row:(row.onset,row.note,row.occurrence));base=min((row.note for row in group),default=0);first=min((row.onset for row in group),default=0);context=contexts.get(key)
        rows.append({'track':key[0],'channel':key[1],'family':getattr(context,'family','UNKNOWN'),'role':getattr(context,'role','UNKNOWN'),'shape':[[row.onset-first,row.off-row.onset,row.note-base] for row in group]})
    payload={'ticks_per_beat':mid.ticks_per_beat,'type':mid.type,'tracks':rows}
    return _sha256_bytes(json.dumps(payload,sort_keys=True,separators=(',',':')).encode())


def _controller_guards(mid):
    guarded=defaultdict(set)
    for track_index,track in enumerate(mid.tracks):
        for message in track:
            channel=getattr(message,'channel',None)
            if channel is None:continue
            if message.type=='control_change' and message.control in SENSITIVE_CONTROLLERS:guarded[(track_index,channel)].add('CC%d'%message.control)
            elif message.type=='pitchwheel':guarded[(track_index,channel)].add('PITCH_BEND')
            elif message.type in ('aftertouch','polytouch'):guarded[(track_index,channel)].add('AFTERTOUCH')
    return guarded


def _annotate_phrases(note_tokens,tpb):
    """Attach deterministic whole-phrase hierarchy to every neural token."""
    grouped=defaultdict(list)
    for token in note_tokens:grouped[(token['track'],token['channel'])].append(token)
    phrases=[]
    for key,rows in sorted(grouped.items()):
        rows.sort(key=lambda row:(row['onset'],row['pitch'],row['occurrence']));positive_gaps=[b['onset']-a['onset'] for a,b in zip(rows,rows[1:]) if b['onset']>a['onset']];typical=float(statistics.median(positive_gaps)) if positive_gaps else float(tpb);rest_boundary=max(int(tpb),int(round(typical*3.0)));chunks=[];current=[];start_bar=None;previous=None
        for row in rows:
            new_phrase=bool(current and ((previous is not None and row['onset']-previous['onset']>rest_boundary) or int(row['bar'])-int(start_bar)>=8))
            if new_phrase:chunks.append(current);current=[];start_bar=None
            if start_bar is None:start_bar=int(row['bar'])
            current.append(row);previous=row
        if current:chunks.append(current)
        for ordinal,chunk in enumerate(chunks):
            phrase_id='T%d:C%d:P%d'%(key[0],key[1],ordinal);pitches=[row['pitch'] for row in chunk];onsets=Counter(row['onset'] for row in chunk);intervals=[b-a for a,b in zip(pitches,pitches[1:])];repeated=sum(a==b for a,b in zip(pitches,pitches[1:]));ornaments=sum(abs(value)<=2 for value in intervals);start=chunk[0]['onset'];end=max(row['off'] for row in chunk);duration=max(1,end-start);direction=0 if not intervals else (sum(intervals)/max(1,sum(abs(value) for value in intervals)));summary={'phrase_id':phrase_id,'track':key[0],'channel':key[1],'phrase_index':ordinal,'start_tick':start,'end_tick':end,'start_bar':chunk[0]['bar'],'end_bar':chunk[-1]['bar'],'notes':len(chunk),'unique_onsets':len(onsets),'duration_beats':round(duration/max(1,tpb),6),'density_notes_per_beat':round(len(chunk)/(duration/max(1,tpb)),6),'pitch_span':max(pitches)-min(pitches),'contour_direction':round(direction,6),'repetition_fraction':round(repeated/max(1,len(chunk)-1),6),'ornament_fraction':round(ornaments/max(1,len(intervals)),6),'chord_note_fraction':round(sum(count for count in onsets.values() if count>1)/max(1,len(chunk)),6),'element':chunk[0].get('element'),'cv':chunk[0].get('cv'),'family':chunk[0].get('family'),'role':chunk[0].get('role')};phrases.append(summary)
            for index,row in enumerate(chunk):row.update({'phrase_id':phrase_id,'phrase_index':ordinal,'phrase_note_index':index,'phrase_note_count':len(chunk),'phrase_position':round(index/max(1,len(chunk)-1),6),'phrase_start':index==0,'phrase_end':index==len(chunk)-1})
    return phrases


def encode_neural_contract(source,content_type='auto',include_source_bytes=True,registry=None,_source_bytes=None):
    source=Path(source);raw=source.read_bytes() if _source_bytes is None else _source_bytes;mid=load_midi(source);registry=registry or ProfileRegistry();detection=detect_content_type_details(mid,content_type);contexts=build_contexts(mid,registry,detection['content_type']);notes=extract_notes(mid);guards=_controller_guards(mid)
    raw_events=[]
    for track_index,track in enumerate(mid.tracks):
        for absolute_tick,event_index,message in absolute_track(track):
            raw_events.append({'event_key':'T%d:E%d'%(track_index,event_index),'track':track_index,'event_index':event_index,'absolute_tick':absolute_tick,'delta_tick':int(message.time),'type':message.type,'is_meta':bool(message.is_meta),'message':_message_payload(message)})
    simultaneous=defaultdict(list)
    for note in notes:simultaneous[(note.track_index,note.channel,note.onset)].append(note)
    simultaneous_pitches={key:sorted(row.note for row in group) for key,group in simultaneous.items()}
    end_tick=max((note.off for note in notes),default=max(1,mid.ticks_per_beat*4));bars=_build_bar_spans(mid,end_tick);bar_starts=[row['start_tick'] for row in bars];note_tokens=[]
    for note in sorted(notes,key=lambda row:(row.track_index,row.onset,row.channel,row.note,row.occurrence)):
        context=contexts.get((note.track_index,note.channel));identity=getattr(context,'identity',None);dependencies=set(guards.get((note.track_index,note.channel),()))
        if context is None:dependencies.add('MISSING_CONTEXT')
        if identity is not None:
            if identity.conflict:dependencies.add('IDENTITY_CONFLICT')
            if identity.rx_named:dependencies.add('RX_IDENTITY')
            if identity.dnc_named:dependencies.add('DNC_IDENTITY')
        family=str(getattr(context,'family','UNKNOWN') or 'UNKNOWN').upper()
        if family in PERMANENT_PRESERVE_FAMILIES:dependencies.add('PERMANENT_PRESERVE_FAMILY')
        if note.velocity<=20:dependencies.add('LOW_VELOCITY_SPECIAL_CANDIDATE')
        group_key=(note.track_index,note.channel,note.onset);group=simultaneous[group_key];bar_index=max(0,min(len(bars)-1,bisect_right(bar_starts,note.onset)-1));bar=bars[bar_index];beat_ticks=max(1,int(round(mid.ticks_per_beat*4/bar['denominator'])));position_in_bar=max(0,note.onset-bar['start_tick'])
        note_tokens.append({'note_key':'T%d:C%d:N%d:O%d'%(note.track_index,note.channel,note.note,note.occurrence),'track':note.track_index,'channel':note.channel,'pitch':note.note,'velocity':note.velocity,'onset':note.onset,'off':note.off,'duration':note.duration,'on_event_index':note.on_index,'off_event_index':note.off_index,'occurrence':note.occurrence,'bar':bar_index,'beat':min(bar['numerator']-1,position_in_bar//beat_ticks),'position_in_bar':position_in_bar,'bar_ticks':bar['bar_ticks'],'position_in_beat':position_in_bar%beat_ticks,'beat_ticks':beat_ticks,'meter_numerator':bar['numerator'],'meter_denominator':bar['denominator'],'simultaneous_group_id':'T%d:C%d:K%d'%(note.track_index,note.channel,note.onset),'simultaneous_group_size':len(group),'voice_index':simultaneous_pitches[group_key].index(note.note),'family':family,'role':getattr(context,'role','UNKNOWN'),'element':getattr(context,'element',None),'cv':getattr(context,'cv',None),'bank_msb':getattr(identity,'msb',None),'bank_lsb':getattr(identity,'lsb',None),'program':getattr(identity,'program',None),'rx_dnc':bool(identity and (identity.rx_named or identity.dnc_named)),'protected_dependencies':sorted(dependencies),'protected':bool(dependencies),'allowed_actions':['PRESERVE'] if dependencies else ['ANALYZE','SYNTHETIC_CORRUPTION_CANDIDATE']})
    phrases=_annotate_phrases(note_tokens,mid.ticks_per_beat)
    contract={'schema':SCHEMA,'analyzer_only':True,'authority_granted':False,'mutations':0,'source':{'filename':source.name,'path':str(source),'sha256':_sha256_bytes(raw),'bytes':len(raw)},'midi':{'type':mid.type,'ticks_per_beat':mid.ticks_per_beat,'tracks':len(mid.tracks)},'content_detection':detection,'source_group_id':_source_group_id(mid,notes,contexts),'raw_events':raw_events,'note_tokens':note_tokens,'phrases':phrases,'phrase_contract':{'schema':'PA800_NEURAL_PHRASE_CONTRACT_V1','context':'WHOLE_PHRASE_UP_TO_8_BARS','velocity_features':False,'authority_granted':False},'summary':{'raw_events':len(raw_events),'notes':len(note_tokens),'phrases':len(phrases),'protected_notes':sum(row['protected'] for row in note_tokens),'event_attribution_percent':100.0}}
    if include_source_bytes:contract['source_bytes_b64']=base64.b64encode(raw).decode('ascii')
    contract['contract_digest']=neural_contract_digest(contract)
    return contract


def neural_contract_digest(contract):
    payload={key:value for key,value in contract.items() if key not in ('contract_digest','source_bytes_b64')}
    return _sha256_bytes(json.dumps(payload,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode())


def validate_neural_contract(contract):
    errors=[]
    if contract.get('schema')!=SCHEMA:errors.append('schema')
    if contract.get('authority_granted') is not False or contract.get('mutations')!=0:errors.append('authority')
    if contract.get('contract_digest')!=neural_contract_digest(contract):errors.append('contract_digest')
    raw_events=contract.get('raw_events') or [];notes=contract.get('note_tokens') or []
    if len({row.get('event_key') for row in raw_events})!=len(raw_events):errors.append('duplicate_event_key')
    if len({row.get('note_key') for row in notes})!=len(notes):errors.append('duplicate_note_key')
    if (contract.get('summary') or {}).get('raw_events')!=len(raw_events) or (contract.get('summary') or {}).get('notes')!=len(notes):errors.append('summary_count')
    phrases=contract.get('phrases') or []
    if phrases and (contract.get('summary') or {}).get('phrases')!=len(phrases):errors.append('phrase_summary_count')
    if phrases and any(not row.get('phrase_id') for row in notes):errors.append('phrase_token_attribution')
    encoded=contract.get('source_bytes_b64')
    if encoded:
        try:
            raw=base64.b64decode(encoded,validate=True)
            if _sha256_bytes(raw)!=(contract.get('source') or {}).get('sha256'):errors.append('source_hash')
        except Exception:errors.append('source_payload')
    return {'schema':'PA800_NEURAL_EVENT_CONTRACT_VALIDATION_V1','pass':not errors,'errors':errors,'raw_events':len(raw_events),'notes':len(notes),'protected_notes':sum(bool(row.get('protected')) for row in notes)}


def decode_unchanged_contract(contract,output):
    validation=validate_neural_contract(contract)
    if not validation['pass']:raise ValueError('Invalid neural contract: %s'%validation['errors'])
    encoded=contract.get('source_bytes_b64')
    if not encoded:raise ValueError('Contract has no lossless source payload')
    raw=base64.b64decode(encoded);output=Path(output);output.parent.mkdir(parents=True,exist_ok=True)
    handle,tmp=tempfile.mkstemp(prefix=output.name+'.',suffix='.tmp',dir=output.parent);os.close(handle)
    try:Path(tmp).write_bytes(raw);os.replace(tmp,output)
    finally:
        if Path(tmp).exists():Path(tmp).unlink()
    return {'pass':_sha256_bytes(output.read_bytes())==(contract.get('source') or {}).get('sha256'),'bytes':len(raw),'sha256':_sha256_bytes(raw),'mutations':0,'authority_granted':False}


def public_contract(contract):
    return {key:value for key,value in contract.items() if key not in ('source_bytes_b64',)}
