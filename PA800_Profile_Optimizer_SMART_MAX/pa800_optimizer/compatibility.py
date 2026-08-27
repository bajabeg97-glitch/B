"""Timing-map, exporter and multi-program compatibility diagnostics."""
from __future__ import annotations

from collections import defaultdict
import hashlib,json,zipfile
from pathlib import Path

from .core.midi_io import collect_program_segments
from .core.smf_preflight import preflight_smf


def _absolute_meta(mid,kind):
    rows=[]
    for ti,track in enumerate(mid.tracks):
        tick=0
        for index,msg in enumerate(track):
            tick+=int(msg.time)
            if msg.type==kind:
                if kind=='set_tempo':value=int(msg.tempo)
                else:value=(int(msg.numerator),int(msg.denominator),int(getattr(msg,'clocks_per_click',24)),int(getattr(msg,'notated_32nd_notes_per_beat',8)))
                rows.append({'track':ti,'event_index':index,'tick':tick,'value':value})
    return rows


def _map_audit(rows,default):
    by_tick=defaultdict(list)
    for row in rows:by_tick[row['tick']].append(row)
    conflicts=[];duplicates=[]
    for tick,group in sorted(by_tick.items()):
        values={json.dumps(row['value'],sort_keys=True) for row in group}
        if len(values)>1:conflicts.append({'tick':tick,'events':group})
        elif len(group)>1:duplicates.append({'tick':tick,'value':group[0]['value'],'count':len(group),'tracks':sorted({row['track'] for row in group})})
    return {'events':rows,'event_count':len(rows),'initial_explicit':any(row['tick']==0 for row in rows),'implicit_default':default if not any(row['tick']==0 for row in rows) else None,'duplicates':duplicates,'conflicts':conflicts,'safe':not conflicts}


def analyze_timing_map(mid):
    tempo=_map_audit(_absolute_meta(mid,'set_tempo'),500000);meter=_map_audit(_absolute_meta(mid,'time_signature'),[4,4,24,8])
    return {'tempo':tempo,'meter':meter,'safe':tempo['safe'] and meter['safe'],'conflict_count':len(tempo['conflicts'])+len(meter['conflicts'])}


def analyze_compatibility(mid,source_path=None):
    program=collect_program_segments(mid);timing=analyze_timing_map(mid);profiles=[]
    suffix=Path(source_path).suffix.lower() if source_path else ''
    lyric_events=sum(msg.type in ('lyrics','text') for track in mid.tracks for msg in track)
    if suffix=='.kar' or lyric_events:profiles.append({'id':'KAR_LYRIC_CONTAINER','evidence':['kar_extension' if suffix=='.kar' else 'lyric_meta_events'],'status':'SUPPORTED_PRESERVE'})
    if getattr(mid,'type',1)==0:profiles.append({'id':'GM_FORMAT0_SINGLE_TRACK','evidence':['smf_format_0'],'status':'SUPPORTED'})
    redundant=[]
    for ti,track in enumerate(mid.tracks):
        counts=defaultdict(lambda:{0:0,32:0,'pc':0})
        for msg in track:
            ch=getattr(msg,'channel',None)
            if ch is None:continue
            if msg.type=='control_change' and msg.control in (0,32):counts[ch][msg.control]+=1
            elif msg.type=='program_change':counts[ch]['pc']+=1
        for ch,row in counts.items():
            if row['pc']==1 and (row[0]>1 or row[32]>1):redundant.append({'track':ti,'channel':ch+1,'cc0':row[0],'cc32':row[32],'program_changes':1})
    if redundant:profiles.append({'id':'REDUNDANT_BANK_SETUP','evidence':redundant,'status':'SUPPORTED_SINGLE_VOICE_STATE'})
    if program['multi_program_channels']:profiles.append({'id':'MULTI_PROGRAM_CHANNEL','evidence':program['multi_program_channels'],'status':'PRESERVE_SEGMENTED_CHANNEL'})
    if any(row['track']>0 for row in timing['tempo']['events']):profiles.append({'id':'TEMPO_OUTSIDE_CONDUCTOR_TRACK','evidence':[row for row in timing['tempo']['events'] if row['track']>0],'status':'SUPPORTED_IF_MAP_UNAMBIGUOUS'})
    return {'schema':'PA800_COMPATIBILITY_V1','source_extension':suffix,'smf_format':getattr(mid,'type',None),'ticks_per_beat':getattr(mid,'ticks_per_beat',None),'timing_map':timing,'program_map':program,'exporter_profiles':profiles,'safe_for_optimization':timing['safe'],'requires_review':not timing['safe'] or bool(program['multi_program_channels']),'mutations':0}


def _zip_write(archive,name,data):
    info=zipfile.ZipInfo(name,date_time=(1980,1,1,0,0,0));info.compress_type=zipfile.ZIP_DEFLATED;info.external_attr=0o600<<16;archive.writestr(info,data)


def create_recovery_package(input_path,output_path,stage,error):
    source=Path(input_path);destination=Path(output_path).parent/(source.stem+'_PA800_RECOVERY.zip');destination.parent.mkdir(parents=True,exist_ok=True);raw=source.read_bytes()
    try:preflight=preflight_smf(source)
    except Exception as exc:preflight={'pass':False,'errors':['preflight_exception:'+repr(exc)]}
    report={'schema':'PA800_UNRECOVERABLE_RECOVERY_V1','input_name':source.name,'input_bytes':len(raw),'input_sha256':hashlib.sha256(raw).hexdigest(),'stage':str(stage),'error':str(error),'preflight':preflight,'automatic_musical_repair_attempted':False,'instructions':['Keep the original file unchanged.','Inspect the JSON preflight errors.','Re-export from the source sequencer or repair the SMF container with a byte-preserving specialist tool.','Run PA800 validation again after repair.']}
    payload=json.dumps(report,indent=2,ensure_ascii=False,sort_keys=True).encode('utf-8');readme=('PA800 UNRECOVERABLE RECOVERY PACKAGE\n\nNo guessed notes, tempo, meter or controller bytes were created.\nSee RECOVERY_REPORT.json and repair/re-export ORIGINAL/'+source.name+'.\n').encode('utf-8');tmp=destination.with_suffix('.zip.tmp')
    with zipfile.ZipFile(tmp,'w') as archive:
        _zip_write(archive,'RECOVERY_REPORT.json',payload);_zip_write(archive,'READ_ME_FIRST.txt',readme);_zip_write(archive,'ORIGINAL/'+source.name,raw)
    tmp.replace(destination);return destination