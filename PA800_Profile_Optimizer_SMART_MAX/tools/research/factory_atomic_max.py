from __future__ import annotations
import argparse, bisect, collections, csv, gzip, hashlib, json, math, os, re, sqlite3, statistics, struct, zipfile
from pathlib import Path
try:
    import orjson
    loads=orjson.loads
except Exception:
    loads=json.loads

ELEMENT_ORDER=['Variation 1','Variation 2','Variation 3','Variation 4','Intro 1','Intro 2','Intro 3','Fill 1','Fill 2','Break','Ending 1','Ending 2','Ending 3']
ROLES=['DRUM','PERC','BASS','ACC1','ACC2','ACC3','ACC4','ACC5']
ROLE_RE=re.compile(r'^(DRUMS|PERC|BASS|ACC[1-5])\s+CV([1-6])',re.I)
EL_RE=re.compile(r'^(Variation\s+[1-4]|Intro\s+[1-3]|Fill\s+[1-3]|Break(?:/Fill)?|Break|Ending\s+[1-3])$',re.I)
BARS_RE=re.compile(r'^\s*(\d+)\s+Bars?\s*$',re.I)

# ---------- math ----------
def percentile(vals,p):
    if not vals:return None
    s=sorted(vals); z=(len(s)-1)*p; a=math.floor(z); b=math.ceil(z)
    return float(s[a]) if a==b else float(s[a]*(b-z)+s[b]*(z-a))
def qsum(vals):
    if not vals:return {}
    return {k:round(percentile(vals,p),5) for k,p in [('min',0),('p01',.01),('p05',.05),('p10',.10),('p25',.25),('p50',.5),('p75',.75),('p90',.9),('p95',.95),('p99',.99),('max',1)]}
def hist_q(hist,p,offset=0):
    n=sum(hist)
    if not n:return None
    pos=(n-1)*p; lo=math.floor(pos); hi=math.ceil(pos)
    def kth(k):
        s=0
        for i,c in enumerate(hist):
            s+=c
            if s>k:return i+offset
        return len(hist)-1+offset
    a,b=kth(lo),kth(hi)
    return float(a) if lo==hi else float(a*(hi-pos)+b*(pos-lo))
def hist_summary(hist,offset=0):
    if not sum(hist):return {}
    return {k:round(hist_q(hist,p,offset),4) for k,p in [('raw_min',0),('p05',.05),('working_min',.10),('ideal_min',.25),('ideal_center',.5),('ideal_max',.75),('working_max',.9),('p95',.95),('p99',.99),('raw_max',1)]}
def mean_std(vals):
    if not vals:return (None,None)
    m=sum(vals)/len(vals); v=sum((x-m)*(x-m) for x in vals)/len(vals)
    return round(m,5),round(math.sqrt(v),5)
def entropy_from_counter(c):
    n=sum(c.values())
    if not n:return 0.0
    return round(-sum((v/n)*math.log2(v/n) for v in c.values() if v),5)
def jaccard(a,b):
    if not a and not b:return 1.0
    u=len(a|b)
    return len(a&b)/u if u else 1.0
def safe_div(a,b): return a/b if b else None

def family(name,role=None,msb=None):
    s=(name or '').lower()
    if role=='DRUM' or msb==120:return 'DRUM_KIT'
    if role=='PERC':return 'PERCUSSION'
    rules=[
      ('BASS',r'\bbass\b|upright|contrabass'),('GUITAR',r'guitar|gtr|nylon|steel|dist\.|overdrive|power chord|telecaster|strat|jazz gt|clean gt|mute gt|funk stein'),
      ('PIANO',r'piano|grand|honky|epiano|e\.piano|electric piano|wurly|rhodes|clav'),('ORGAN',r'organ|drawbar|rotary'),
      ('ACCORDION_REED',r'accord|harmonica|musette|bandoneon|reed|mouth harp'),('STRINGS',r'string|violin|viola|cello|orchestra|pizz'),
      ('BRASS',r'brass|trumpet|trombone|horn|tuba|flugel'),('WOODWIND',r'sax|clarinet|flute|oboe|bassoon|piccolo|recorder'),
      ('CHOIR_VOICE',r'choir|voice|vocal|doo|aah|ooh'),('PAD',r'pad|atmos|warm|sweep'),('SYNTH_LEAD',r'lead|synth|analog|square|saw|pulse'),
      ('MALLET',r'vibes|vibra|marimba|xylophone|kalimba|celesta|glock|bell'),('PLUCK',r'harp|koto|sitar|banjo|mandolin|dulcimer|oud|bouzouki'),('SFX',r'sfx|noise|effect|fx')]
    for fam,pat in rules:
        if re.search(pat,s):return fam
    return 'OTHER_ACC' if role and str(role).startswith('ACC') else 'OTHER'

def modes_valleys(hist):
    n=sum(hist)
    if n<30:return [],[]
    sm=[0.0]*128; w=[1,2,3,2,1]
    for i in range(1,128):
        num=den=0
        for off,ww in zip(range(-2,3),w):
            j=i+off
            if 1<=j<=127:num+=hist[j]*ww;den+=ww
        sm[i]=num/den if den else 0
    peaks=[]; minheight=max(2,n*.0025)
    for i in range(2,127):
        if sm[i]>=sm[i-1] and sm[i]>=sm[i+1] and sm[i]>=minheight:peaks.append((sm[i],i))
    peaks.sort(reverse=True); chosen=[]
    for h,i in peaks:
        if all(abs(i-j)>=5 for _,j in chosen):chosen.append((h,i))
        if len(chosen)>=6:break
    chosen.sort(key=lambda x:x[1]); modes=[]; valleys=[]
    for h,i in chosen:
        lo=max(1,i-4);hi=min(127,i+4); sup=sum(hist[lo:hi+1]); modes.append({'center':i,'fraction':round(sup/n,6),'support':sup})
    for (_,a),(_,b) in zip(chosen,chosen[1:]):
        if b-a<3:continue
        v=min(range(a+1,b),key=lambda x:sm[x]); dep=1-sm[v]/max(1e-9,min(sm[a],sm[b])); valleys.append({'velocity':v,'depth':round(dep,5),'left':a,'right':b})
    return modes,valleys

# ---------- note segment feature extraction ----------
def note_key(r):
    return (r['file'],r['track'],r.get('role'),r.get('cv'),r.get('element'),r.get('element_start'),r.get('msb'),r.get('lsb'),r.get('program'),r.get('sound'))

def meter_ticks(ppq,n,d):
    beat=ppq*4.0/d; return beat,beat*n

def grid_phase(rel,ppq,tsn,tsd):
    beat,bar=meter_ticks(ppq,tsn,tsd); pos=rel%max(1,int(round(bar))); phase=(pos/beat)%1.0 if beat else 0
    slot24=int(round(phase*24))%24
    slotbar=int(round(pos/beat*24)) if beat else 0
    return slot24,slotbar,pos,beat,bar

def nearest_grid_residual(rel,ppq,step_div):
    # step_div = number subdivisions per quarter, e.g. 8 for 1/32, 6 triplet 1/16
    step=ppq/step_div
    if not step:return 0
    return rel-round(rel/step)*step

def group_near_onsets(notes,threshold):
    if not notes:return []
    arr=sorted(notes,key=lambda x:(x['rel_onset'],x['note']))
    groups=[]; cur=[arr[0]]; last=arr[0]['rel_onset']
    for n in arr[1:]:
        if n['rel_onset']-last<=threshold:
            cur.append(n)
        else:
            groups.append(cur);cur=[n]
        last=n['rel_onset']
    groups.append(cur);return groups

def monotonic_direction(group):
    if len(group)<3:return None
    arr=sorted(group,key=lambda x:(x['rel_onset'],x['note']))
    if max(x['rel_onset'] for x in arr)==min(x['rel_onset'] for x in arr):return None
    pitches=[x['note'] for x in arr]; dif=[b-a for a,b in zip(pitches,pitches[1:])]
    if all(x>=0 for x in dif) and any(x>0 for x in dif):return 'UP_PITCH_WITH_TIME'
    if all(x<=0 for x in dif) and any(x<0 for x in dif):return 'DOWN_PITCH_WITH_TIME'
    return 'MIXED'

def run_candidates(seq,ppq):
    # seq: one representative note per distinct onset (onset,pitch,vel,dur)
    out={'repeat_runs':0,'max_repeat_run':1,'trill_runs':0,'tremolo_runs':0,'grace_candidates':0}
    if not seq:return out
    # repeated pitch runs
    run=1
    for a,b in zip(seq,seq[1:]):
        if b[1]==a[1]:run+=1
        else:
            if run>=3:out['repeat_runs']+=1
            out['max_repeat_run']=max(out['max_repeat_run'],run);run=1
    if run>=3:out['repeat_runs']+=1
    out['max_repeat_run']=max(out['max_repeat_run'],run)
    # alternating two-note trill / rapid tremolo
    i=0
    while i+3<len(seq):
        a,b,c,d=seq[i:i+4]; iois=[b[0]-a[0],c[0]-b[0],d[0]-c[0]]
        if max(iois)<=ppq/2 and a[1]==c[1] and b[1]==d[1]:
            j=i+4
            while j<len(seq) and seq[j][1]==seq[j-2][1] and seq[j][0]-seq[j-1][0]<=ppq/2:j+=1
            if abs(a[1]-b[1])<=2:out['trill_runs']+=1
            else:out['tremolo_runs']+=1
            i=j
        else:i+=1
    # grace: short note closely before next note, small-ish interval
    for a,b in zip(seq,seq[1:]):
        gap=b[0]-a[0]
        if a[3] is not None and a[3]<=ppq/8 and 0<gap<=ppq/4 and abs(b[1]-a[1])<=4:out['grace_candidates']+=1
    return out

def segment_features(rows,special_map):
    r0=rows[0]; ppq=int(r0.get('ppq') or 192); tsn=int(r0.get('ts_num') or 4); tsd=int(r0.get('ts_den') or 4)
    beat_ticks,bar_ticks=meter_ticks(ppq,tsn,tsd); bars=int(r0.get('bars') or 0)
    if not bars:
        maxrel=max(int(r.get('rel_onset') or 0) for r in rows); bars=max(1,int(maxrel//max(1,round(bar_ticks)))+1)
    vels=[int(r['velocity']) for r in rows]; pitches=[int(r['note']) for r in rows]; durs=[int(r['duration']) for r in rows if isinstance(r.get('duration'),(int,float))]
    vh=[0]*128; ph=collections.Counter(); pc=collections.Counter(); grid24=collections.Counter(); bar_slot=collections.Counter(); residuals={k:[] for k in ['8','8T','16','16T','32']}
    onsets=collections.defaultdict(list); bar_notes=collections.defaultdict(list)
    for r in rows:
        v=int(r['velocity']);p=int(r['note']);rel=int(r.get('rel_onset') or 0); vh[v]+=1;ph[p]+=1;pc[p%12]+=1; onsets[rel].append(r)
        sl24,slbar,pos,bt,bar=grid_phase(rel,ppq,tsn,tsd);grid24[sl24]+=1;bar_slot[slbar]+=1
        residuals['8'].append(abs(nearest_grid_residual(rel,ppq,2))); residuals['8T'].append(abs(nearest_grid_residual(rel,ppq,3)))
        residuals['16'].append(abs(nearest_grid_residual(rel,ppq,4))); residuals['16T'].append(abs(nearest_grid_residual(rel,ppq,6))); residuals['32'].append(abs(nearest_grid_residual(rel,ppq,8)))
        bi=int(rel//max(1,round(bar_ticks)));bar_notes[bi].append(r)
    # exact chord sizes
    chord_sizes=[len(g) for g in onsets.values()]; exact_chords=sum(1 for x in chord_sizes if x>=2)
    # near-onset / strum candidates
    fam=family(r0.get('sound'),r0.get('role'),r0.get('msb')); groups=group_near_onsets(rows,max(1,int(round(ppq/8))))
    strums=[]
    for g in groups:
        if len(g)>=3:
            spread=max(x['rel_onset'] for x in g)-min(x['rel_onset'] for x in g); direction=monotonic_direction(g)
            if 0<spread<=ppq/4 and direction in ('UP_PITCH_WITH_TIME','DOWN_PITCH_WITH_TIME'):
                arr=sorted(g,key=lambda x:(x['rel_onset'],x['note'])); slope=(arr[-1]['velocity']-arr[0]['velocity'])/max(1,spread)
                strums.append((spread,direction,slope,len(g)))
    # one representative pitch per onset for interval/run analysis: median pitch, max duration/median velocity
    seq=[]
    for o,g in sorted(onsets.items()):
        ps=sorted(x['note'] for x in g);vs=sorted(x['velocity'] for x in g); ds=[x['duration'] for x in g if isinstance(x.get('duration'),(int,float))]
        seq.append((o,int(round(statistics.median(ps))),int(round(statistics.median(vs))),max(ds) if ds else None))
    intervals=[b[1]-a[1] for a,b in zip(seq,seq[1:])]; absiv=[abs(x) for x in intervals]
    runs=run_candidates(seq,ppq)
    # gate classification against next distinct onset
    gates=[]; stacc=leg=ten=dead=0
    seq_onsets=[x[0] for x in seq]
    for i,(o,g) in enumerate(sorted(onsets.items())):
        if i+1>=len(seq_onsets):continue
        nxt=seq_onsets[i+1]; ioi=nxt-o
        if ioi<=0:continue
        for n in g:
            d=n.get('duration')
            if not isinstance(d,(int,float)):continue
            gr=float(d)/ioi;gates.append(gr)
            if gr<.45:stacc+=1
            elif gr>=.95:leg+=1
            elif .75<=gr<.95:ten+=1
            if fam in ('GUITAR','BASS') and gr<.30 and n['velocity']<=percentile(vels,.4):dead+=1
    # ghost/accent candidates use pitch-local robust percentiles where support exists
    pitch_vels=collections.defaultdict(list)
    for r in rows:pitch_vels[int(r['note'])].append(int(r['velocity']))
    ghost=accent=0
    seg_low=percentile(vels,.20); seg_high=percentile(vels,.90)
    pitch_bounds={}
    for p,pv in pitch_vels.items():
        pitch_bounds[p]=(percentile(pv,.25),percentile(pv,.90)) if len(pv)>=4 else (seg_low,seg_high)
    for r in rows:
        v=int(r['velocity']);rel=int(r['rel_onset']); phase=((rel%max(1,round(beat_ticks)))/beat_ticks) if beat_ticks else 0
        low,high=pitch_bounds[int(r['note'])]
        if r0.get('role') in ('DRUM','PERC') and low is not None and v<=low and min(phase,1-phase)>.05:ghost+=1
        if high is not None and v>=high:accent+=1
    # bar repetition on 96-like slot sets (24 slots/quarter)
    masks=[]
    for bi in range(bars):
        ss=set()
        for r in bar_notes.get(bi,[]):
            rel=int(r['rel_onset'])-int(round(bi*bar_ticks)); _sl,slbar,*_=grid_phase(rel,ppq,tsn,tsd);ss.add(slbar)
        masks.append(ss)
    reps=[jaccard(a,b) for a,b in zip(masks,masks[1:])]
    # phrase contour quarters and bars
    bar_density=[len(bar_notes.get(i,[])) for i in range(bars)]
    bar_vmed=[percentile([x['velocity'] for x in bar_notes.get(i,[])],.5) if bar_notes.get(i) else None for i in range(bars)]
    qbins=[[] for _ in range(4)]
    total=max(1,round(bar_ticks*bars))
    for r in rows:
        idx=min(3,int(4*int(r['rel_onset'])/total));qbins[idx].append(r)
    quarter_density=[len(x) for x in qbins]; quarter_v=[percentile([r['velocity'] for r in x],.5) if x else None for x in qbins]
    # special ranges from exact sound profile
    smkey=(r0.get('msb'),r0.get('lsb'),r0.get('program'),' '.join((r0.get('sound') or '').lower().split()))
    spranges=special_map.get(smkey,[]); primary=special_map.get(smkey+('PRIMARY',),None)
    special=[];normal=[]
    def in_ranges(p,rr):return any(int(x['min'])<=p<=int(x['max']) for x in rr)
    for r in rows:(special if in_ranges(int(r['note']),spranges) else normal).append(r)
    # relation special to nearest normal event in same segment
    nont=sorted(int(x['rel_onset']) for x in normal); special_offsets=[]; special_pos=collections.Counter()
    for s in special:
        if not nont: special_pos['ISOLATED']+=1;continue
        o=int(s['rel_onset']);j=bisect.bisect_left(nont,o);cand=[]
        if j:cand.append((o-nont[j-1],'AFTER_NORMAL'))
        if j<len(nont):cand.append((nont[j]-o,'BEFORE_NORMAL'))
        if cand:
            d,lab=min(cand,key=lambda x:abs(x[0]));special_offsets.append(abs(d));special_pos[lab]+=1
    # fingerprints
    rhythm_repr='|'.join(','.join(map(str,sorted(x))) for x in masks)
    rhythm_fp=hashlib.sha1((f'{tsn}/{tsd}|{bars}|'+rhythm_repr).encode()).hexdigest()[:16]
    if r0.get('role') in ('DRUM','PERC'):
        perf_seq=[(int(r['rel_onset']),int(r['note']),int(r['velocity'])//8) for r in rows]
    else:
        base=seq[0][1] if seq else 0; perf_seq=[(o,p-base,v//8) for o,p,v,d in seq]
    perf_fp=hashlib.sha1(json.dumps(perf_seq,separators=(',',':')).encode()).hexdigest()[:16]
    grid_fit={k:round(percentile(v,.5) or 0,3) for k,v in residuals.items()}
    vmodes,vvalleys=modes_valleys(vh)
    return {
      'file':r0['file'],'track':r0['track'],'role':r0.get('role'),'cv':r0.get('cv'),'element':r0.get('element'),'bars':bars,'meter':f'{tsn}/{tsd}','ppq':ppq,
      'msb':r0.get('msb'),'lsb':r0.get('lsb'),'program':r0.get('program'),'sound':r0.get('sound'),'family':fam,'notes':len(rows),'unique_onsets':len(onsets),
      'notes_per_bar':round(len(rows)/bars,5),'onsets_per_bar':round(len(onsets)/bars,5),'active_bar_fraction':round(sum(bool(bar_notes.get(i)) for i in range(bars))/bars,5),
      'velocity':hist_summary(vh),'velocity_mean_std':mean_std(vels),'velocity_entropy':entropy_from_counter(collections.Counter(vels)),'velocity_modes':vmodes,'velocity_valleys':vvalleys,
      'pitch':qsum(pitches),'register_width':max(pitches)-min(pitches),'unique_pitches':len(ph),'pitch_class_entropy':entropy_from_counter(pc),'top_pitches':ph.most_common(12),
      'duration':qsum(durs),'gate_ratio':qsum(gates),'staccato_fraction':round(stacc/max(1,len(gates)),5),'legato_overlap_fraction':round(leg/max(1,len(gates)),5),'tenuto_fraction':round(ten/max(1,len(gates)),5),
      'dead_mute_candidate_fraction':round(dead/max(1,len(gates)),5),'ghost_candidate_fraction':round(ghost/max(1,len(rows)),5),'accent_candidate_fraction':round(accent/max(1,len(rows)),5),
      'polyphony_mean':round(sum(chord_sizes)/len(chord_sizes),5),'polyphony_max':max(chord_sizes),'exact_chord_onsets':exact_chords,'exact_chord_fraction':round(exact_chords/max(1,len(onsets)),5),
      'strum_candidates':len(strums),'strum_fraction':round(len(strums)/max(1,len(groups)),5),'strum_spread_ticks':qsum([x[0] for x in strums]),'strum_up_fraction':round(sum(x[1]=='UP_PITCH_WITH_TIME' for x in strums)/max(1,len(strums)),5),'strum_velocity_slope':qsum([x[2] for x in strums]),
      'interval':{'repeat_fraction':round(sum(x==0 for x in absiv)/max(1,len(absiv)),5),'step_fraction':round(sum(0<x<=2 for x in absiv)/max(1,len(absiv)),5),'third_fourth_fraction':round(sum(3<=x<=5 for x in absiv)/max(1,len(absiv)),5),'fifth_octave_fraction':round(sum(7<=x<=12 for x in absiv)/max(1,len(absiv)),5),'large_leap_fraction':round(sum(x>12 for x in absiv)/max(1,len(absiv)),5),'signed':qsum(intervals)},
      'runs':runs,'grid_fit_median_abs_ticks':grid_fit,'phase24_hist':dict(grid24),'bar_slot_hist':dict(bar_slot),'fine_subdivision_fraction':round(sum(c for k,c in grid24.items() if k%6 not in (0,))/max(1,len(rows)),5),'offbeat_8th_fraction':round(sum(c for k,c in grid24.items() if k==12)/max(1,len(rows)),5),
      'bar_repeat_similarity':round(sum(reps)/len(reps),5) if reps else None,'bar_density':bar_density,'bar_velocity_median':bar_vmed,'quarter_density':quarter_density,'quarter_velocity_median':quarter_v,
      'special_pitch_notes':len(special),'special_pitch_fraction':round(len(special)/len(rows),6),'special_velocity':qsum([x['velocity'] for x in special]),'special_duration':qsum([x['duration'] for x in special if isinstance(x.get('duration'),(int,float))]),'special_nearest_normal_offset_ticks':qsum(special_offsets),'special_relation':dict(special_pos),
      'rhythm_fingerprint':rhythm_fp,'performance_fingerprint':perf_fp,
      '_onset_set':set(int(x) for x in onsets.keys()),'_mask_union':set().union(*masks) if masks else set(), '_vels':vels,
    }

# ---------- source MIDI control parser ----------
def vlq(buf,p):
    v=0
    while True:
        if p>=len(buf):raise EOFError
        b=buf[p];p+=1;v=(v<<7)|(b&127)
        if not b&128:return v,p

def midi_chunks(data):
    if data[:4]!=b'MThd':raise ValueError('not MIDI')
    hlen=int.from_bytes(data[4:8],'big');fmt,ntr,div=struct.unpack('>HHH',data[8:14]);p=8+hlen;out=[]
    for i in range(ntr):
        if data[p:p+4]!=b'MTrk':break
        ln=int.from_bytes(data[p+4:p+8],'big');out.append(data[p+8:p+8+ln]);p+=8+ln
    return fmt,div,out

def parse_events(ch):
    p=0;run=None;t=0
    while p<len(ch):
        try:dt,p=vlq(ch,p)
        except Exception:break
        t+=dt
        if p>=len(ch):break
        x=ch[p]
        if x<128:
            if run is None:break
            st=run
        else:
            st=x;p+=1;run=st if st<240 else None
        if st==255:
            if p>=len(ch):break
            mt=ch[p];p+=1
            try:ln,p=vlq(ch,p)
            except Exception:break
            dat=ch[p:p+ln];p+=ln;yield t,'meta',None,mt,dat,True
        elif st in (240,247):
            try:ln,p=vlq(ch,p)
            except Exception:break
            dat=ch[p:p+ln];p+=ln;yield t,'sysex',None,None,dat,True
        elif st<240:
            hi=st&240;c=st&15;n=1 if hi in (192,208) else 2
            if p+n>len(ch):break
            vals=list(ch[p:p+n]);p+=n;valid=all(v<128 for v in vals)
            kind={128:'off',144:'on',160:'poly_at',176:'cc',192:'pc',208:'ch_at',224:'pb'}.get(hi,'chan')
            yield t,kind,c,vals[0] if vals else None,vals[1] if len(vals)>1 else None,valid
        else:break

def control_analysis(zip_path):
    Z=zipfile.ZipFile(zip_path); global_counts=collections.Counter(); cc_values=collections.defaultdict(collections.Counter); meta_counts=collections.Counter(); texts=collections.Counter(); per_sound=collections.defaultdict(lambda:{'counts':collections.Counter(),'cc_values':collections.defaultdict(collections.Counter),'pb':[],'at':[],'styles':set(),'elements':collections.Counter(),'roles':collections.Counter(),'nrpn':collections.Counter(),'rpn':collections.Counter()})
    invalid=collections.Counter(); sysex_lengths=collections.Counter(); nrpn_global=collections.Counter(); rpn_global=collections.Counter()
    for name in [x for x in Z.namelist() if x.lower().endswith(('.mid','.midi'))]:
        fmt,ppq,tracks=midi_chunks(Z.read(name))
        for ti,ch in enumerate(tracks):
            evs=list(parse_events(ch));tname=''
            for e in evs:
                if e[1]=='meta' and e[3]==3:
                    txt=e[4].decode('latin1','ignore').strip()
                    if txt and not txt.startswith('SN:'):tname=txt;break
            m=ROLE_RE.match(tname);role=(('DRUM' if m and m.group(1).upper()=='DRUMS' else m.group(1).upper()) if m else None);cv=int(m.group(2)) if m else None
            element=None;msb=lsb=pc=None;snd=None; state=collections.defaultdict(lambda:{'nrpn_msb':None,'nrpn_lsb':None,'rpn_msb':None,'rpn_lsb':None})
            for t,kind,c,a,b,valid in evs:
                if not valid:
                    invalid[(kind,a,b)]+=1;continue
                if kind=='meta':
                    meta_counts[a]+=1
                    if a in (1,3,4,5,6,7):
                        txt=b.decode('latin1','ignore').strip();
                        if txt:texts[txt]+=1
                        if a==1:
                            if EL_RE.match(txt):element=txt
                            elif not BARS_RE.match(txt) and txt and not txt.startswith('SN:'):snd=txt
                    continue
                if kind=='sysex':global_counts['sysex']+=1;sysex_lengths[len(b or b'')]+=1;continue
                if kind=='cc':
                    if a==0:msb=b
                    elif a==32:lsb=b
                elif kind=='pc':pc=a;continue
                key=(msb,lsb,pc,snd);ps=per_sound[key];ps['styles'].add(name);ps['elements'][element]+=1;ps['roles'][role]+=1
                if kind=='cc':
                    global_counts[f'cc:{a}']+=1;cc_values[a][b]+=1;ps['counts'][f'cc:{a}']+=1;ps['cc_values'][a][b]+=1
                    st=state[c]
                    if a==99:st['nrpn_msb']=b;st['rpn_msb']=st['rpn_lsb']=None
                    elif a==98:st['nrpn_lsb']=b
                    elif a==101:st['rpn_msb']=b;st['nrpn_msb']=st['nrpn_lsb']=None
                    elif a==100:st['rpn_lsb']=b
                    elif a in (6,38):
                        if st['nrpn_msb'] is not None and st['nrpn_lsb'] is not None:
                            par=(st['nrpn_msb'],st['nrpn_lsb'],a,b);nrpn_global[par]+=1;ps['nrpn'][par]+=1
                        if st['rpn_msb'] is not None and st['rpn_lsb'] is not None:
                            par=(st['rpn_msb'],st['rpn_lsb'],a,b);rpn_global[par]+=1;ps['rpn'][par]+=1
                elif kind=='pb':
                    val=a+(b<<7)-8192;global_counts['pb']+=1;ps['counts']['pb']+=1;ps['pb'].append(val)
                elif kind=='ch_at':global_counts['ch_at']+=1;ps['counts']['ch_at']+=1;ps['at'].append(a)
                elif kind=='poly_at':global_counts['poly_at']+=1;ps['counts']['poly_at']+=1
    sounds=[]
    for k,p in per_sound.items():
        if not p['counts']:continue
        pb=p['pb'];at=p['at']
        sounds.append({'msb':k[0],'lsb':k[1],'program':k[2],'sound':k[3],'styles':len(p['styles']),'roles':p['roles'].most_common(),'elements':p['elements'].most_common(),'counts':dict(p['counts']),
                       'cc_thresholds':{str(cc):{'n':sum(p['cc_values'][cc].values()),'ge64':sum(v for x,v in p['cc_values'][cc].items() if x>=64),'zero':p['cc_values'][cc].get(0,0),'max':max(p['cc_values'][cc]) if p['cc_values'][cc] else None} for cc in (1,2,64,80,81) if p['cc_values'][cc]},
                       'pitchbend':{'n':len(pb),'nonzero':sum(x!=0 for x in pb),'positive':sum(x>0 for x in pb),'negative':sum(x<0 for x in pb),'zero':sum(x==0 for x in pb),'max_abs':max(map(abs,pb)) if pb else 0,'summary':qsum(pb)},
                       'aftertouch':{'n':len(at),'ge90':sum(x>=90 for x in at),'summary':qsum(at)},'nrpn':[[*k2,n] for k2,n in p['nrpn'].most_common(30)],'rpn':[[*k2,n] for k2,n in p['rpn'].most_common(30)]})
    sounds.sort(key=lambda x:sum(x['counts'].values()),reverse=True)
    return {'global_counts':dict(global_counts),'cc_values':{str(k):dict(v) for k,v in cc_values.items()},'meta_types':dict(meta_counts),'top_texts':texts.most_common(300),'invalid_events':[[str(k),v] for k,v in invalid.most_common()], 'sysex_lengths':dict(sysex_lengths),'nrpn':[[*k,n] for k,n in nrpn_global.most_common(200)],'rpn':[[*k,n] for k,n in rpn_global.most_common(200)],'sounds':sounds}

# ---------- aggregation / comparison ----------
def context_merge(rows):
    if not rows:return None
    notes=sum(r['notes'] for r in rows); bars=max(r['bars'] for r in rows); onsets=set(); mask=set(); v=[]
    for r in rows:onsets|=r['_onset_set'];mask|=r['_mask_union'];v.extend(r['_vels'])
    weighted=lambda k:sum((r.get(k) or 0)*r['notes'] for r in rows)/notes if notes else 0
    return {'notes':notes,'bars':bars,'notes_per_bar':notes/bars if bars else 0,'unique_onsets':len(onsets),'onsets_per_bar':len(onsets)/bars if bars else 0,'velocity_p50':percentile(v,.5),'velocity_p90':percentile(v,.9),
            'register_width':max((r['register_width'] for r in rows),default=0),'polyphony_mean':weighted('polyphony_mean'),'fine_subdivision_fraction':weighted('fine_subdivision_fraction'),'offbeat_8th_fraction':weighted('offbeat_8th_fraction'),
            'strum_fraction':weighted('strum_fraction'),'staccato_fraction':weighted('staccato_fraction'),'legato_overlap_fraction':weighted('legato_overlap_fraction'),'mask':mask,'onsets':onsets,
            'rhythm_fp_set':set(r['rhythm_fingerprint'] for r in rows),'sounds':set((r['msb'],r['lsb'],r['program'],r['sound']) for r in rows)}

def aggregate_rows(rows):
    if not rows:return {}
    vals=lambda key:[r.get(key) for r in rows if r.get(key) is not None]
    return {'segments':len(rows),'styles':len(set(r['file'] for r in rows)),'notes':sum(r['notes'] for r in rows),
            'notes_per_bar':qsum(vals('notes_per_bar')),'onsets_per_bar':qsum(vals('onsets_per_bar')),'register_width':qsum(vals('register_width')),'polyphony_mean':qsum(vals('polyphony_mean')),
            'fine_subdivision_fraction':qsum(vals('fine_subdivision_fraction')),'offbeat_8th_fraction':qsum(vals('offbeat_8th_fraction')),'bar_repeat_similarity':qsum(vals('bar_repeat_similarity')),
            'strum_fraction':qsum(vals('strum_fraction')),'staccato_fraction':qsum(vals('staccato_fraction')),'legato_overlap_fraction':qsum(vals('legato_overlap_fraction')),
            'ghost_candidate_fraction':qsum(vals('ghost_candidate_fraction')),'accent_candidate_fraction':qsum(vals('accent_candidate_fraction')),'special_pitch_fraction':qsum(vals('special_pitch_fraction'))}

def compare_metric(records,a,b,key):
    vals=[]
    for x,y in records:
        if x.get(key) is not None and y.get(key) is not None:vals.append(y[key]-x[key])
    return {'n':len(vals),'delta':qsum(vals),'positive_fraction':round(sum(x>0 for x in vals)/len(vals),5) if vals else None,'negative_fraction':round(sum(x<0 for x in vals)/len(vals),5) if vals else None}

def cross_role_metrics(ctx_by_key):
    out=[]
    pairs=[('DRUM','PERC'),('DRUM','BASS'),('BASS','ACC1'),('BASS','ACC2'),('DRUM','ACC1'),('DRUM','ACC2'),('DRUM','ACC3')]
    for (file,el,cv),roles in ctx_by_key.items():
        for a,b in pairs:
            if a not in roles or b not in roles:continue
            A=sorted(roles[a]['onsets']);B=sorted(roles[b]['onsets']);sb=set(B); exact=sum(x in sb for x in A)
            ds=[];signed=[]
            for x in A:
                j=bisect.bisect_left(B,x);cand=[]
                if j:cand.append(B[j-1]-x)
                if j<len(B):cand.append(B[j]-x)
                if cand:
                    d=min(cand,key=lambda z:abs(z));ds.append(abs(d));signed.append(d)
            ppq=roles[a].get('ppq',192)
            out.append({'file':file,'element':el,'cv':cv,'role_a':a,'role_b':b,'a_onsets':len(A),'b_onsets':len(B),'exact_fraction_a':exact/max(1,len(A)),'nearest_abs_ticks_p50':percentile(ds,.5),'nearest_abs_qn_p50':(percentile(ds,.5)/ppq if ds else None),'nearest_signed_ticks_p50':percentile(signed,.5),'jaccard':jaccard(set(A),set(B))})
    return out

def write_csv(path,rows,fields=None):
    if not rows:return
    if fields is None:
        fields=[]
        for r in rows:
            for k in r:
                if k not in fields:fields.append(k)
    with open(path,'w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=fields,extrasaction='ignore');w.writeheader()
        for r in rows:
            rr={k:(json.dumps(v,separators=(',',':')) if isinstance(v,(dict,list,tuple,set)) else v) for k,v in r.items()};w.writerow(rr)

def main():
    ap=argparse.ArgumentParser();root=Path(__file__).resolve().parents[2]
    ap.add_argument('--records',default='/mnt/data/factory_records.ndjson');ap.add_argument('--zip',default=str(root/'corpus/Factory Styles.zip'));ap.add_argument('--outdir',default=str(root/'research_max'));ap.add_argument('--skip-controls',action='store_true');ap.add_argument('--skip-sqlite',action='store_true')
    args=ap.parse_args();outdir=Path(args.outdir);outdir.mkdir(parents=True,exist_ok=True)
    # exact sound special pitch map
    sp=json.loads((root/'pa800_optimizer/profiles/data/factory_sound_profiles_v1.json').read_text(encoding='utf-8'))
    special_map={}
    for p in sp['profiles']:
        i=p['identity'];k=(i['msb'],i['lsb'],i['program'],' '.join((i.get('sound') or '').lower().split()));special_map[k]=p.get('special_pitch_candidates',[]);special_map[k+('PRIMARY',)]=p.get('primary_pitch_cluster')
    # DNC addresses for explicit absence/presence cross-check
    dnc=json.loads((root/'pa800_optimizer/profiles/data/pa800_dnc_manual_registry_v1.json').read_text(encoding='utf-8'))
    dnc_addr={(x['msb'],x['lsb'],x['program']):x['name'] for x in dnc['sounds']}
    dnc_seen=collections.Counter()
    segments=[];current=[];curkey=None
    by_style_ec_role=collections.defaultdict(lambda:collections.defaultdict(list)); by_group=collections.defaultdict(list); fp_rhythm=collections.defaultdict(list);fp_perf=collections.defaultdict(list)
    line_count=0
    with open(args.records,'rb') as f:
        for line in f:
            line_count+=1
            if line_count%200000==0: print('READ',line_count,'segments',len(segments),flush=True)
            r=loads(line);k=note_key(r)
            a=(r.get('msb'),r.get('lsb'),r.get('program'))
            if a in dnc_addr:dnc_seen[a]+=1
            if curkey is None:curkey=k
            if k!=curkey:
                sf=segment_features(current,special_map);segments.append(sf);by_group[(sf['element'],sf['role'],sf['cv'])].append(sf);by_style_ec_role[(sf['file'],sf['element'],sf['cv'])][sf['role']].append(sf);fp_rhythm[(sf['role'],sf['element'],sf['rhythm_fingerprint'])].append(sf);fp_perf[(sf['role'],sf['element'],sf['performance_fingerprint'])].append(sf)
                current=[r];curkey=k
            else:current.append(r)
    if current:
        sf=segment_features(current,special_map);segments.append(sf);by_group[(sf['element'],sf['role'],sf['cv'])].append(sf);by_style_ec_role[(sf['file'],sf['element'],sf['cv'])][sf['role']].append(sf);fp_rhythm[(sf['role'],sf['element'],sf['rhythm_fingerprint'])].append(sf);fp_perf[(sf['role'],sf['element'],sf['performance_fingerprint'])].append(sf)
    print('NOTE_PASS_DONE',len(segments),flush=True)
    # collapse role contexts
    ctx_by_key={}
    for key,roles in by_style_ec_role.items():
        ctx_by_key[key]={}
        for role,rr in roles.items():
            m=context_merge(rr);m['ppq']=rr[0]['ppq'];ctx_by_key[key][role]=m
    print('CTX_MERGE_DONE',len(ctx_by_key),flush=True)
    # aggregate element/role/cv and element/role
    erc={f'{e}|{r}|CV{cv}':aggregate_rows(v) for (e,r,cv),v in by_group.items()}
    er=collections.defaultdict(list)
    for s in segments:er[(s['element'],s['role'])].append(s)
    er_out={f'{e}|{r}':aggregate_rows(v) for (e,r),v in er.items()}
    # element metadata, bars, active roles
    element_stats={}
    for e in ELEMENT_ORDER:
        ss=[s for s in segments if s['element']==e]
        contexts=[(k,v) for k,v in ctx_by_key.items() if k[1]==e]
        if not ss:continue
        bar_counts=collections.Counter()
        seen=set()
        for s in ss:
            k=(s['file'],s['element'])
            if k not in seen:bar_counts[s['bars']]+=1;seen.add(k)
        active=[len(v) for k,v in contexts]
        role_presence={r:round(sum(r in v for k,v in contexts)/max(1,len(contexts)),5) for r in ROLES}
        element_stats[e]={'styles':len(set(s['file'] for s in ss)),'segments':len(ss),'notes':sum(s['notes'] for s in ss),'bars_counts':dict(bar_counts),'bars_median':percentile([s['bars'] for s in ss],.5),'active_roles':qsum(active),'role_presence':role_presence,'aggregate':aggregate_rows(ss)}
    # variation progression per style-role-cv
    by_src=collections.defaultdict(dict)
    for (file,el,cv),roles in ctx_by_key.items():
        if el.startswith('Variation'):
            for role,m in roles.items():by_src[(file,role,cv)][el]=m
    metrics=['notes_per_bar','onsets_per_bar','velocity_p50','velocity_p90','register_width','polyphony_mean','fine_subdivision_fraction','offbeat_8th_fraction','strum_fraction','staccato_fraction','legato_overlap_fraction']
    progression=[]; comp_pairs=collections.defaultdict(list)
    for key,d in by_src.items():
        for i in range(1,4):
            a=f'Variation {i}';b=f'Variation {i+1}'
            if a in d and b in d:
                x,y=d[a],d[b];row={'file':key[0],'role':key[1],'cv':key[2],'transition':f'V{i}->V{i+1}','rhythm_jaccard':jaccard(x['mask'],y['mask']),'same_rhythm_mask':x['mask']==y['mask'],'sound_same':x['sounds']==y['sounds'],'sound_added':len(y['sounds']-x['sounds']),'sound_removed':len(x['sounds']-y['sounds'])}
                for m in metrics:row['delta_'+m]=(y.get(m)-x.get(m)) if x.get(m) is not None and y.get(m) is not None else None
                progression.append(row);comp_pairs[(f'V{i}->V{i+1}',key[1])].append((x,y))
    progression_summary={}
    for k,pairs in comp_pairs.items():
        tr,role=k;rs=[x for x in progression if x['transition']==tr and x['role']==role]
        d={'n':len(rs),'rhythm_jaccard':qsum([x['rhythm_jaccard'] for x in rs]),'same_rhythm_fraction':round(sum(x['same_rhythm_mask'] for x in rs)/len(rs),5),'same_sound_fraction':round(sum(x['sound_same'] for x in rs)/len(rs),5)}
        for m in metrics:d[m]=compare_metric(pairs,None,None,m)
        progression_summary[f'{tr}|{role}']=d
    # arrangement-level V1-V4 role additions and energy
    arrangement=[];by_style_cv=collections.defaultdict(dict)
    for (file,el,cv),roles in ctx_by_key.items():
        if el.startswith('Variation'):
            total_notes=sum(v['notes'] for v in roles.values()); bars=max((v['bars'] for v in roles.values()),default=1); vel=[]
            for rr in by_style_ec_role[(file,el,cv)].values():
                for s in rr:vel.extend(s['_vels'])
            by_style_cv[(file,cv)][el]={'active_roles':len(roles),'role_set':set(roles),'notes_per_bar':total_notes/bars,'velocity_p50':percentile(vel,.5),'fine':sum(v['fine_subdivision_fraction']*v['notes'] for v in roles.values())/max(1,total_notes),'poly':sum(v['polyphony_mean']*v['notes'] for v in roles.values())/max(1,total_notes)}
    for key,d in by_style_cv.items():
        for i in range(1,4):
            a=f'Variation {i}';b=f'Variation {i+1}'
            if a in d and b in d:
                x,y=d[a],d[b];arrangement.append({'file':key[0],'cv':key[1],'transition':f'V{i}->V{i+1}','active_roles_delta':y['active_roles']-x['active_roles'],'added_roles':sorted(y['role_set']-x['role_set']),'removed_roles':sorted(x['role_set']-y['role_set']),'notes_per_bar_delta':y['notes_per_bar']-x['notes_per_bar'],'velocity_p50_delta':y['velocity_p50']-x['velocity_p50'],'fine_subdivision_delta':y['fine']-x['fine'],'polyphony_delta':y['poly']-x['poly']})
    # CV contrast within style/element/role
    by_cvcomp=collections.defaultdict(dict)
    for (file,el,cv),roles in ctx_by_key.items():
        for role,m in roles.items():by_cvcomp[(file,el,role)][cv]=m
    cvrows=[]
    for key,d in by_cvcomp.items():
        if 1 not in d:continue
        for cv,m in sorted(d.items()):
            if cv==1:continue
            a=d[1];cvrows.append({'file':key[0],'element':key[1],'role':key[2],'pair':f'CV1-CV{cv}','rhythm_jaccard':jaccard(a['mask'],m['mask']),'same_rhythm_mask':a['mask']==m['mask'],'density_ratio':m['notes_per_bar']/a['notes_per_bar'] if a['notes_per_bar'] else None,'velocity_p50_delta':m['velocity_p50']-a['velocity_p50'],'register_width_delta':m['register_width']-a['register_width'],'sound_same':m['sounds']==a['sounds']})
    print('CV_DONE',len(cvrows),flush=True)
    # cross role
    cross=cross_role_metrics(ctx_by_key)
    cross_summary={}
    for key,g in collections.defaultdict(list).items():pass
    crg=collections.defaultdict(list)
    for x in cross:crg[(x['element'],x['role_a'],x['role_b'])].append(x)
    for k,g in crg.items():cross_summary['|'.join(k)]={'n':len(g),'exact_fraction_a':qsum([x['exact_fraction_a'] for x in g]),'nearest_abs_qn_p50':qsum([x['nearest_abs_qn_p50'] for x in g if x['nearest_abs_qn_p50'] is not None]),'jaccard':qsum([x['jaccard'] for x in g])}
    print('CROSS_DONE',len(cross),flush=True)
    # fingerprints duplicates
    fprows=[]
    for kind,dic in [('RHYTHM',fp_rhythm),('PERFORMANCE',fp_perf)]:
        for (role,el,fp),g in dic.items():
            styles=set(x['file'] for x in g)
            if len(styles)>=2:
                fprows.append({'kind':kind,'role':role,'element':el,'fingerprint':fp,'segments':len(g),'styles':len(styles),'example_files':sorted(styles)[:8]})
    fprows.sort(key=lambda x:(x['styles'],x['segments']),reverse=True)
    # techniques aggregate
    techg=collections.defaultdict(list)
    for s in segments:techg[(s['family'],s['role'],s['element'])].append(s)
    techniques=[]
    for k,g in techg.items():
        n=sum(x['notes'] for x in g)
        def w(field):return sum((x.get(field) or 0)*x['notes'] for x in g)/max(1,n)
        techniques.append({'family':k[0],'role':k[1],'element':k[2],'segments':len(g),'styles':len(set(x['file'] for x in g)),'notes':n,'ghost_candidate_fraction':w('ghost_candidate_fraction'),'accent_candidate_fraction':w('accent_candidate_fraction'),'staccato_fraction':w('staccato_fraction'),'legato_overlap_fraction':w('legato_overlap_fraction'),'tenuto_fraction':w('tenuto_fraction'),'dead_mute_candidate_fraction':w('dead_mute_candidate_fraction'),'strum_candidates':sum(x['strum_candidates'] for x in g),'trill_runs':sum(x['runs']['trill_runs'] for x in g),'tremolo_runs':sum(x['runs']['tremolo_runs'] for x in g),'grace_candidates':sum(x['runs']['grace_candidates'] for x in g),'repeat_runs':sum(x['runs']['repeat_runs'] for x in g),'special_pitch_notes':sum(x['special_pitch_notes'] for x in g)})
    techniques.sort(key=lambda x:x['notes'],reverse=True)
    # special sounds aggregate from segments
    spg=collections.defaultdict(list)
    for s in segments:
        if s['special_pitch_notes']:spg[(s['msb'],s['lsb'],s['program'],s['sound'])].append(s)
    special_rows=[]
    for k,g in spg.items():
        special_rows.append({'msb':k[0],'lsb':k[1],'program':k[2],'sound':k[3],'family':g[0]['family'],'segments':len(g),'styles':len(set(x['file'] for x in g)),'special_notes':sum(x['special_pitch_notes'] for x in g),'all_notes':sum(x['notes'] for x in g),'special_fraction':sum(x['special_pitch_notes'] for x in g)/sum(x['notes'] for x in g),'before_normal':sum(x['special_relation'].get('BEFORE_NORMAL',0) for x in g),'after_normal':sum(x['special_relation'].get('AFTER_NORMAL',0) for x in g),'isolated':sum(x['special_relation'].get('ISOLATED',0) for x in g)})
    special_rows.sort(key=lambda x:x['special_notes'],reverse=True)
    print('AGGS_DONE',len(techniques),len(special_rows),flush=True)
    # controls/meta
    if args.skip_controls:
        cp=root/'pa800_optimizer/profiles/data/factory_controller_profiles.json'
        controls={'global_counts':{},'cc_values':{},'meta_types':{},'top_texts':[],'invalid_events':[],'sysex_lengths':{},'nrpn':[],'rpn':[],'sounds':json.loads(cp.read_text(encoding='utf-8')) if cp.exists() else []}
    else:
        controls=control_analysis(args.zip)
    print('CONTROLS_DONE',flush=True)
    # serialize segments stripped of private sets/lists
    seg_rows=[]
    for s in segments:
        seg_rows.append({k:v for k,v in s.items() if not k.startswith('_')})
    summary={'schema':'PA800_FACTORY_ATOMIC_MAX_V1','source':'Factory Styles.zip','records':sum(x['notes'] for x in segments),'segments':len(segments),'styles':len(set(x['file'] for x in segments)),'element_stats':element_stats,'element_role_cv':erc,'element_role':er_out,'variation_progression_summary':progression_summary,'cross_role_summary':cross_summary,'manual_dnc_addresses_observed_in_factory':{'count':len(dnc_seen),'notes':sum(dnc_seen.values()),'addresses':[{'address':list(a),'name':dnc_addr[a],'notes':n} for a,n in dnc_seen.items()]},'controls_global':{k:v for k,v in controls.items() if k!='sounds'},'principles':{'factory_observation_not_internal_sound_semantics':True,'raw_min_max_not_targets':True,'unknown_dnc_mapping_not_inferred':True,'exact_onset_sound_state_required':True}}
    # write artifacts
    (outdir/'factory_atomic_max_summary.json').write_text(json.dumps(summary,indent=2),encoding='utf-8')
    (outdir/'factory_atomic_max_controls.json').write_text(json.dumps(controls,indent=2),encoding='utf-8')
    # full segment detail as compressed NDJSON; scalar CSV separately for easy browsing
    with gzip.open(outdir/'factory_atomic_max_segments.ndjson.gz','wb',compresslevel=5) as gz:
        for r in seg_rows:
            gz.write((json.dumps(r,separators=(',',':'))+'\n').encode('utf-8'))
    scalar_fields=['file','track','role','cv','element','bars','meter','ppq','msb','lsb','program','sound','family','notes','unique_onsets','notes_per_bar','onsets_per_bar','register_width','unique_pitches','velocity_entropy','pitch_class_entropy','staccato_fraction','legato_overlap_fraction','tenuto_fraction','dead_mute_candidate_fraction','ghost_candidate_fraction','accent_candidate_fraction','polyphony_mean','polyphony_max','exact_chord_onsets','exact_chord_fraction','strum_candidates','strum_fraction','fine_subdivision_fraction','offbeat_8th_fraction','bar_repeat_similarity','special_pitch_notes','special_pitch_fraction','rhythm_fingerprint','performance_fingerprint']
    write_csv(outdir/'factory_atomic_max_segments_scalar.csv',seg_rows,scalar_fields)
    write_csv(outdir/'factory_variation_progression_max.csv',progression)
    write_csv(outdir/'factory_arrangement_progression_max.csv',arrangement)
    write_csv(outdir/'factory_cv_contrast_max.csv',cvrows)
    write_csv(outdir/'factory_cross_role_max.csv',cross)
    write_csv(outdir/'factory_technique_candidates_max.csv',techniques)
    write_csv(outdir/'factory_special_pitch_relations_max.csv',special_rows)
    write_csv(outdir/'factory_pattern_fingerprints_max.csv',fprows[:20000])
    # controls per sound csv
    write_csv(outdir/'factory_controller_sound_profiles_max.csv',controls['sounds'])
    # SQLite aggregated warehouse (optional; compressed NDJSON + CSV are canonical)
    if not args.skip_sqlite:
        db=sqlite3.connect(outdir/'factory_atomic_max.sqlite');cur=db.cursor()
        tables=[('variation_progression',progression),('arrangement_progression',arrangement),('cv_contrast',cvrows),('cross_role',cross),('techniques',techniques),('special_pitch',special_rows),('fingerprints',fprows[:20000])]
        for t,rows in tables:
            cur.execute(f'DROP TABLE IF EXISTS {t}')
            if not rows:continue
            cols=list(rows[0].keys());cur.execute(f'CREATE TABLE {t} ('+','.join('"'+c+'" TEXT' for c in cols)+')')
            sql=f'INSERT INTO {t} ('+','.join('"'+c+'"' for c in cols)+') VALUES ('+','.join('?' for _ in cols)+')'
            vals=[]
            for r in rows:vals.append([json.dumps(r.get(c),separators=(',',':')) if isinstance(r.get(c),(dict,list,tuple,set)) else r.get(c) for c in cols])
            cur.executemany(sql,vals)
        cur.execute('CREATE TABLE IF NOT EXISTS metadata (key TEXT PRIMARY KEY,value TEXT)');cur.execute('INSERT OR REPLACE INTO metadata VALUES (?,?)',('schema','PA800_FACTORY_ATOMIC_MAX_V1'));cur.execute('INSERT OR REPLACE INTO metadata VALUES (?,?)',('styles',str(summary['styles'])));cur.execute('INSERT OR REPLACE INTO metadata VALUES (?,?)',('notes',str(summary['records'])));db.commit();db.close()
    # concise report generated separately here
    report=[];A=report.append
    A('# PA800 Factory Styles — ATOMIC MAX forensic analysis (NO DNA)\n')
    A('## Scope\n')
    A(f'- Styles: **{summary["styles"]}**\n- Valid Note-On atoms: **{summary["records"]:,}**\n- Context/sound-state segments: **{summary["segments"]:,}**\n- Unit of analysis: `Style → Element → CV → role → exact Sound state → bar/beat/subdivision → onset group → note atom`.\n')
    A('Factory proves observed arranger behavior; it does not by itself name internal RX/DNC oscillator semantics. Manual DNC addresses observed in this Factory corpus: **%d**.\n' % len(dnc_seen))
    A('## Element anatomy\n')
    for e in ELEMENT_ORDER:
        if e not in element_stats:continue
        x=element_stats[e];A(f'- **{e}**: notes={x["notes"]:,}, median bars={x["bars_median"]}, active-role median={x["active_roles"].get("p50")}, notes/bar median={x["aggregate"].get("notes_per_bar",{}).get("p50")}, onset/bar median={x["aggregate"].get("onsets_per_bar",{}).get("p50")}.\n')
    A('\n## Variation progression — strongest structural finding\n')
    A('The corpus does **not** primarily build V1→V4 by simply raising velocity. The dominant growth mechanism is orchestration/density: more ACC/Perc roles become active, and V3/V4 more often add note/onset detail while many existing role rhythm masks remain highly similar. This supports a layered arranger model: preserve the skeleton, add layers/detail by higher Variations.\n')
    for k,v in progression_summary.items():
        if any(k.endswith('|'+r) for r in ('DRUM','PERC','BASS','ACC1','ACC2')):
            A(f'- {k}: rhythm Jaccard median={v["rhythm_jaccard"].get("p50")}, exact-mask fraction={v["same_rhythm_fraction"]}, same-Sound fraction={v["same_sound_fraction"]}; Δnotes/bar median={v["notes_per_bar"]["delta"].get("p50")}.\n')
    A('\n## CV logic\n')
    A('CVs must remain separate. `CV1` is the best-supported reference, but CV2–CV6 can preserve a rhythm skeleton while changing pitch/register/Sound or can be genuinely specialized. The CSV `factory_cv_contrast_max.csv` records rhythm Jaccard, density ratio, velocity delta, register delta and Sound identity equality for every supported CV1↔CVn pair.\n')
    A('\n## Playing-technique candidate layer\n')
    A('The analysis now measures, without claiming undocumented semantics: ghost/secondary-hit candidates, accent candidates, staccato, legato/overlap, tenuto, short/dead/mute candidates, near-onset guitar strums and direction, repeated-note runs, trill/tremolo/grace candidates, special-pitch/RX candidates, exact chord groups and phrase/bar contours. These are candidates derived from MIDI context; manual/hardware remains the authority for an RX/DNC articulation name.\n')
    A('\n## Noise / special pitch logic\n')
    A(f'- Exact Sound profiles with observed special-pitch activity in this pass: **{len(special_rows)}**.\n- For each one, special notes are separated from the primary musical range and classified by timing relation: BEFORE_NORMAL / AFTER_NORMAL / ISOLATED, plus velocity and duration distributions. This is the required basis for fret/release/pick/noise hypotheses without deleting out-of-range RX events.\n')
    A('\n## Controllers and performance events\n')
    gc=controls['global_counts'];
    for key in sorted(gc,key=lambda x:(0 if x.startswith('cc:') else 1,x)):
        if gc[key]:A(f'- {key}: {gc[key]:,}\n')
    A('NRPN/RPN sequences, PB sign/range/reset behavior, CC value distributions, CC1/CC2/CC64/CC80/CC81 threshold populations, aftertouch and SysEx inventories are stored in the MAX controller artifacts.\n')
    A('\n## What the optimizer can now use\n')
    A('1. Exact per-note Element/CV/Sound state.\n2. 1–127 velocity histogram + modes/valleys + context.\n3. 8th/16th/32nd and triplet grid residuals + 24-phase groove histogram.\n4. Gate/overlap/staccato/tenuto distributions.\n5. Variation and CV structural relationships.\n6. Per-role density, polyphony, register and phrase contour.\n7. Drum/Perc ghost/accent candidates and per-key profiles.\n8. Guitar strum candidates and spread/direction/velocity slope.\n9. Special/RX pitch timing relationships.\n10. Cross-role timing lock (Drum↔Bass, Drum↔Perc, Bass↔ACC).\n11. Pattern fingerprints to identify reused Factory skeletons.\n12. Controller/NRPN/PB/AT state evidence.\n')
    A('\n## Hard limits / NOT OBSERVABLE from this Factory SMF alone\n')
    A('- Exact internal oscillator selected by Cycle/Random.\n- Exact per-Sound RX/DNC semantic name when the manual/Sound Edit does not expose the mapping.\n- NTT/Trigger Mode/Tension parameter value when it is not serialized in this export.\n- Actual audible timbre/sample result without Pa800 playback/audio capture.\nThese remain protected/unknown instead of guessed.\n')
    (outdir/'FACTORY_ATOMIC_MAX_REPORT.md').write_text(''.join(report),encoding='utf-8')
    print(json.dumps({'styles':summary['styles'],'notes':summary['records'],'segments':summary['segments'],'outdir':str(outdir),'dnc_addresses_seen':len(dnc_seen),'special_sounds':len(special_rows),'fingerprint_groups':len(fprows),'cross_rows':len(cross)},indent=2))

if __name__=='__main__':main()