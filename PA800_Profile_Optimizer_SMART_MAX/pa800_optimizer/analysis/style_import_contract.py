"""Read-only Pa2X/Pa800 OS 2.x marker-separated Style SMF contract audit."""
from __future__ import annotations

import re
from collections import Counter

MARKER_RE=re.compile(r'^(?:v[1-4]cv[1-6]|[ife][1-2]cv[1-2])$')
STYLE_CHANNELS=set(range(8,16))
STYLE_RECORD_CCS={0,1,2,10,11,12,13,32,64,71,74,80,81,82}
ALLOWED_CHANNEL_TYPES={'note_on','note_off','program_change','pitchwheel','aftertouch','control_change'}


def analyze_style_import_contract(mid):
    events=[];markers=[];unsupported=[];outside_channels=[]
    for track_index,track in enumerate(mid.tracks):
        tick=0
        for event_index,msg in enumerate(track):
            tick+=int(getattr(msg,'time',0));events.append((tick,track_index,event_index,msg))
            if msg.type=='marker':markers.append({'tick':tick,'track':track_index,'event_index':event_index,'name':str(getattr(msg,'text',getattr(msg,'name','')))})
            channel=getattr(msg,'channel',None)
            if channel is None:continue
            if channel not in STYLE_CHANNELS:outside_channels.append({'tick':tick,'track':track_index,'channel':channel+1,'type':msg.type})
            if msg.type not in ALLOWED_CHANNEL_TYPES or (msg.type=='control_change' and int(msg.control) not in STYLE_RECORD_CCS):unsupported.append({'tick':tick,'track':track_index,'channel':channel+1,'type':msg.type,'control':getattr(msg,'control',None)})
    marker_rows=[]
    for marker in markers:
        tick=marker['tick'];same=[msg for event_tick,_track,_index,msg in events if event_tick==tick];controls=Counter(int(msg.control) for msg in same if msg.type=='control_change');programs=sum(msg.type=='program_change' for msg in same);time_signatures=sum(msg.type=='time_signature' for msg in same)
        row=dict(marker,valid_name=bool(MARKER_RE.fullmatch(marker['name'])),lowercase=marker['name']==marker['name'].lower(),header={'time_signature':time_signatures,'cc0':controls[0],'cc32':controls[32],'program_change':programs,'cc11':controls[11]})
        row['minimum_header']=time_signatures>0;row['complete_export_header']=all((time_signatures,controls[0],controls[32],programs,controls[11]));marker_rows.append(row)
    checks={'smf_format_0':int(getattr(mid,'type',-1))==0,'has_markers':bool(marker_rows),'marker_names_valid':bool(marker_rows) and all(row['valid_name'] and row['lowercase'] for row in marker_rows),'style_channels_only':not outside_channels,'style_record_events_only':not unsupported,'time_signature_at_each_marker':bool(marker_rows) and all(row['minimum_header'] for row in marker_rows),'complete_header_at_each_marker':bool(marker_rows) and all(row['complete_export_header'] for row in marker_rows)}
    minimum=all(checks[name] for name in ('smf_format_0','has_markers','marker_names_valid','style_channels_only','time_signature_at_each_marker'));strict=minimum and checks['style_record_events_only'] and checks['complete_header_at_each_marker']
    return {'schema':'PA800_STYLE_IMPORT_CONTRACT_V1','source_basis':'KORG_PA2X_PA800_IMPORT_EXPORT_SMF_OS_2_X','applicable':True,'checks':checks,'minimum_importable':minimum,'strict_export_contract':strict,'markers':marker_rows,'outside_style_channel_count':len(outside_channels),'outside_style_channel_samples':outside_channels[:32],'unsupported_event_count':len(unsupported),'unsupported_event_samples':unsupported[:32],'allowed_style_channels_1_based':list(range(9,17)),'allowed_record_ccs':sorted(STYLE_RECORD_CCS),'mutations':0}