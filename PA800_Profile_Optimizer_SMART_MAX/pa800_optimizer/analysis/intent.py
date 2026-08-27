from collections import defaultdict

def classify_intents(notes, contexts, ppq):
    by_tc=defaultdict(list)
    for n in notes: by_tc[(n.track_index,n.channel)].append(n)
    for key,arr in by_tc.items():
        arr.sort(key=lambda n:(n.onset,n.note)); ctx=contexts.get(key)
        role=ctx.role if ctx else 'UNKNOWN'; fam=ctx.family if ctx else 'UNKNOWN'
        onset_groups=defaultdict(list)
        for n in arr: onset_groups[n.onset].append(n)
        for i,n in enumerate(arr):
            beatpos=(n.onset % (ppq*4))/float(ppq)
            strong=abs(beatpos-round(beatpos))<1e-6 and int(round(beatpos)) in (0,2)
            prev=arr[i-1] if i else None; nxt=arr[i+1] if i+1<len(arr) else None
            if role in ('DRUM','PERC'):
                if len(onset_groups[n.onset])>=3: n.intent='ENSEMBLE_HIT'
                elif strong: n.intent='METRIC_MAIN'
                else: n.intent='SECONDARY_HIT'
            elif role=='BASS' or fam=='BASS':
                if prev and prev.note==n.note: n.intent='REPEATED'
                elif prev and nxt and abs(n.note-prev.note)<=2 and abs(nxt.note-n.note)<=2: n.intent='PASSING_CANDIDATE'
                elif strong: n.intent='METRIC_ANCHOR'
                elif nxt and abs(nxt.note-n.note)<=2: n.intent='APPROACH_CANDIDATE'
                else: n.intent='NORMAL_BASS'
            elif fam=='GUITAR':
                g=onset_groups[n.onset]
                if len(g)>=3: n.intent='CHORD_STRUM'
                elif prev and prev.note==n.note: n.intent='REPEATED_RIFF'
                else: n.intent='GUITAR_LINE'
            elif fam in ('PIANO','ORGAN','ENSEMBLE','SYNTH_PAD','STRINGS','ACCORDION','HARMONICA','REED'):
                n.intent='CHORDAL' if len(onset_groups[n.onset])>=2 else ('PHRASE_ACCENT' if strong else 'LINE')
            else:
                n.intent='PHRASE_ACCENT' if strong else 'NORMAL'
    return notes