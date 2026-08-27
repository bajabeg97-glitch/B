import mido
from collections import defaultdict, deque
from ..models import NoteEvent
from .smf_preflight import require_valid_smf

STYLE_ROLE_BY_CHANNEL={8:'BASS',9:'DRUM',10:'PERC',11:'ACC1',12:'ACC2',13:'ACC3',14:'ACC4',15:'ACC5'}

def load_midi(path,preflight=True):
    if preflight:require_valid_smf(path)
    return mido.MidiFile(path, clip=False)

def load_midi_with_recovery(path,preflight=True):
    """Strict load only: clipping malformed bytes can manufacture musical data."""
    if preflight:require_valid_smf(path)
    try:return mido.MidiFile(path,clip=False),[]
    except Exception as strict_error:
        raise RuntimeError('UNRECOVERABLE_STRICT_PARSE: unsafe MIDI byte clipping is disabled; %r' % strict_error) from strict_error
def save_midi(mid,path): mid.save(path)

def absolute_track(track):
    t=0; out=[]
    for idx,msg in enumerate(track):
        t+=msg.time; out.append([t,idx,msg.copy(time=msg.time)])
    return out

def rebuild_track(abs_events):
    # stable ordering: original index breaks same-tick ties
    abs_events.sort(key=lambda x:(max(0,int(x[0])),x[1]))
    prev=0; out=mido.MidiTrack()
    for at,idx,msg in abs_events:
        at=max(prev,int(round(at))); out.append(msg.copy(time=at-prev)); prev=at
    return out

def extract_notes(mid):
    all_notes=[]
    for ti,tr in enumerate(mid.tracks):
        abs_ev=absolute_track(tr); active=defaultdict(deque); occurrences=defaultdict(int)
        for pos,(at,idx,msg) in enumerate(abs_ev):
            if not hasattr(msg,'channel'): continue
            if msg.type=='note_on' and msg.velocity>0:
                key=(msg.channel,msg.note); occurrence=occurrences[key];occurrences[key]+=1
                active[key].append((at,idx,pos,msg.velocity,occurrence))
            elif msg.type in ('note_off','note_on') and (msg.type=='note_off' or msg.velocity==0):
                q=active[(msg.channel,msg.note)]
                if q:
                    on,oidx,opos,vel,occurrence=q.popleft(); all_notes.append(NoteEvent(ti,msg.channel,msg.note,vel,on,at,oidx,idx,occurrence))
    return all_notes

def collect_channel_state(mid):
    """Collect the committed MIDI sound identity for each used track/channel.

    Format 0/1 channel messages share one channel state across tracks. Bank
    Select is pending until a Program Change commits it; a trailing CC0/CC32
    must not relabel the currently sounding program.
    """
    track_text={};seen=set();events=[]
    for ti,track in enumerate(mid.tracks):
        tick=0;meta=[]
        for index,msg in enumerate(track):
            tick+=int(msg.time)
            if msg.type=='track_name' and msg.name:meta.append(msg.name)
            elif msg.type in ('text','marker','cue_marker') and getattr(msg,'text',''):meta.append(msg.text)
            ch=getattr(msg,'channel',None)
            if ch is not None:
                seen.add((ti,ch));events.append((tick,ti,index,msg))
        track_text[ti]=' | '.join(meta)
    events.sort(key=lambda row:(row[0],row[1],row[2]))
    pending=defaultdict(lambda:[None,None]);committed=defaultdict(lambda:[None,None,None]);addresses=defaultdict(set)
    for _tick,ti,_index,msg in events:
        ch=msg.channel;scope=(ti,ch) if mid.type==2 else ch
        if msg.type=='control_change' and msg.control==0:pending[scope][0]=msg.value
        elif msg.type=='control_change' and msg.control==32:pending[scope][1]=msg.value
        elif msg.type=='program_change':
            committed[scope]=[pending[scope][0],pending[scope][1],msg.program]
            addresses[scope].add(tuple(committed[scope]))
    states={}
    for ti,ch in sorted(seen):
        scope=(ti,ch) if mid.type==2 else ch
        value=committed[scope] if committed[scope][2] is not None else [pending[scope][0],pending[scope][1],None]
        states[(ti,ch)]={'msb':value[0],'lsb':value[1],'program':value[2],'track_name':track_text[ti],'multi_program':len(addresses[scope])>1}
    return states

def collect_program_segments(mid):
    """Return exact Bank/Program time segments without collapsing the channel."""
    channels=[]
    for ti,track in enumerate(mid.tracks):
        tick=0;bank=defaultdict(lambda:[None,None]);program_points=defaultdict(list);note_ticks=defaultdict(list);track_end=0
        for index,msg in enumerate(track):
            tick+=int(msg.time);track_end=tick;ch=getattr(msg,'channel',None)
            if ch is None:continue
            if msg.type=='control_change' and msg.control==0:bank[ch][0]=msg.value
            elif msg.type=='control_change' and msg.control==32:bank[ch][1]=msg.value
            elif msg.type=='program_change':program_points[ch].append((tick,index,(bank[ch][0],bank[ch][1],msg.program)))
            elif msg.type=='note_on' and msg.velocity>0:note_ticks[ch].append(tick)
        for ch in sorted(set(program_points)|set(note_ticks)):
            points=program_points[ch];segments=[]
            if not points:
                segments=[{'segment':0,'start_tick':0,'end_tick':track_end,'address':[None,None,None],'program_event_index':None,'bank_complete':False,'notes':len(note_ticks[ch])}]
            else:
                for si,(start,index,address) in enumerate(points):
                    end=points[si+1][0] if si+1<len(points) else track_end
                    segments.append({'segment':si,'start_tick':start,'end_tick':end,'address':list(address),'program_event_index':index,'bank_complete':address[0] is not None and address[1] is not None,'notes':sum(start<=value<end if end>start else value==start for value in note_ticks[ch])})
            unique={tuple(row['address']) for row in segments}
            channels.append({'track':ti,'channel':ch+1,'segments':segments,'segment_count':len(segments),'unique_addresses':[list(value) for value in sorted(unique,key=str)],'multi_program':len(unique)>1,'notes':len(note_ticks[ch])})
    return {'channels':channels,'multi_program_channels':sum(row['multi_program'] for row in channels),'segments':sum(row['segment_count'] for row in channels)}