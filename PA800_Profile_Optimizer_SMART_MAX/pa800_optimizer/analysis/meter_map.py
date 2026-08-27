"""Deterministic serialized meter map and variable-length bar boundaries."""
from __future__ import annotations


def _meter_changes(mid):
    events=[]
    for track_index,track in enumerate(mid.tracks):
        tick=0
        for ordinal,msg in enumerate(track):
            tick+=int(getattr(msg,'time',0))
            if msg.type=='time_signature':
                events.append((tick,track_index,ordinal,max(1,int(msg.numerator)),max(1,int(msg.denominator))))
    events.sort()
    by_tick={}
    for tick,track_index,ordinal,numerator,denominator in events:
        by_tick[tick]=(track_index,ordinal,numerator,denominator)
    if 0 not in by_tick:by_tick[0]=(-1,-1,4,4)
    return [{'tick':tick,'numerator':value[2],'denominator':value[3]} for tick,value in sorted(by_tick.items())]


def _build_bar_spans(mid,end_tick):
    end_tick=max(1,int(end_tick));changes=_meter_changes(mid);rows=[]
    for index,change in enumerate(changes):
        start=int(change['tick'])
        if start>=end_tick:break
        stop=min(end_tick,int(changes[index+1]['tick'])) if index+1<len(changes) else end_tick
        bar_ticks=max(1,int(round(mid.ticks_per_beat*change['numerator']*4/change['denominator'])))
        cursor=start
        while cursor<stop:
            bar_end=min(stop,cursor+bar_ticks)
            rows.append({'index':len(rows),'start_tick':cursor,'end_tick':bar_end,'bar_ticks':bar_ticks,'partial':bar_end-cursor<bar_ticks,'numerator':change['numerator'],'denominator':change['denominator']})
            cursor=bar_end
    if not rows:
        change=changes[0];bar_ticks=max(1,int(round(mid.ticks_per_beat*change['numerator']*4/change['denominator'])))
        rows=[{'index':0,'start_tick':0,'end_tick':min(end_tick,bar_ticks),'bar_ticks':bar_ticks,'partial':end_tick<bar_ticks,'numerator':change['numerator'],'denominator':change['denominator']}]
    return rows