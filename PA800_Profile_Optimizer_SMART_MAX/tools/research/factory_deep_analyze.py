import zipfile, struct, re, math, json, statistics, collections, os
from dataclasses import dataclass
from typing import *

ZIP='/mnt/data/Factory Styles.zip'
ELEMENTS = ['Variation 1','Variation 2','Variation 3','Variation 4','Intro 1','Intro 2','Intro 3','Fill 1','Fill 2','Fill 3','Break','Ending 1','Ending 2','Ending 3']
# manual has Fill 1-3; some exports may call Break separately. keep literal corpus names.
EL_RE = re.compile(r'^(Variation\s+[1-4]|Intro\s+[1-3]|Fill\s+[1-3]|Break(?:/Fill)?|Ending\s+[1-3])$', re.I)
BARS_RE = re.compile(r'^\s*(\d+)\s+Bars?\s*$', re.I)
ROLE_RE = re.compile(r'^(DRUMS|PERC|BASS|ACC[1-5])\s+CV([1-6])', re.I)


def read_vlq(buf,p):
    v=0
    while True:
        if p>=len(buf): raise EOFError
        b=buf[p];p+=1;v=(v<<7)|(b&0x7f)
        if not (b&0x80): return v,p

@dataclass
class Event:
    time:int; kind:str; channel:Optional[int]=None; a:Optional[int]=None; b:Optional[int]=None; meta_type:Optional[int]=None; data:Any=None; valid:bool=True

def parse_track(chunk):
    out=[]; p=0; running=None; t=0
    while p<len(chunk):
        try: dt,p=read_vlq(chunk,p)
        except: break
        t += dt
        if p>=len(chunk): break
        first=chunk[p]
        if first<0x80:
            if running is None:
                # cannot recover reliably
                break
            status=running
        else:
            status=first; p+=1
            running = status if status < 0xF0 else None
        if status==0xFF:
            if p>=len(chunk): break
            mt=chunk[p];p+=1
            try: ln,p=read_vlq(chunk,p)
            except: break
            dat=chunk[p:p+ln]; p+=ln
            try: txt=dat.decode('latin1')
            except: txt=''
            out.append(Event(t,'meta',meta_type=mt,data=(dat,txt)))
        elif status in (0xF0,0xF7):
            try: ln,p=read_vlq(chunk,p)
            except: break
            dat=chunk[p:p+ln]; p+=ln
            out.append(Event(t,'sysex',data=dat))
        elif status<0xF0:
            hi=status&0xF0; ch=status&0x0F
            n=1 if hi in (0xC0,0xD0) else 2
            vals=[]
            if p+n>len(chunk): break
            for _ in range(n): vals.append(chunk[p]); p+=1
            valid=all(v<128 for v in vals)
            kinds={0x80:'note_off',0x90:'note_on',0xA0:'poly_at',0xB0:'cc',0xC0:'pc',0xD0:'ch_at',0xE0:'pb'}
            out.append(Event(t,kinds.get(hi,'chan'),ch,vals[0] if vals else None,vals[1] if len(vals)>1 else None,valid=valid))
        else:
            break
    return out

def midi_chunks(data):
    if data[:4] != b'MThd': raise ValueError('not midi')
    hlen=struct.unpack('>I',data[4:8])[0]
    fmt,ntr,div=struct.unpack('>HHH',data[8:14])
    pos=8+hlen
    trs=[]
    for i in range(ntr):
        if data[pos:pos+4] != b'MTrk': raise ValueError(('bad track',i,pos))
        ln=struct.unpack('>I',data[pos+4:pos+8])[0]
        trs.append(data[pos+8:pos+8+ln]); pos += 8+ln
    return fmt,div,trs

def pct(vals,p):
    if not vals:return None
    s=sorted(vals); x=(len(s)-1)*p; lo=math.floor(x); hi=math.ceil(x)
    if lo==hi:return s[lo]
    return s[lo]*(hi-x)+s[hi]*(x-lo)

def qs(vals):
    if not vals:return {}
    return {k:round(pct(vals,p),3) for k,p in [('min',0),('p01',.01),('p05',.05),('p10',.10),('p25',.25),('p50',.50),('p75',.75),('p90',.90),('p95',.95),('p99',.99),('max',1)]}

def norm_role(name):
    m=ROLE_RE.match((name or '').strip())
    if not m:return None,None
    r=m.group(1).upper(); r='DRUM' if r=='DRUMS' else r
    return r,int(m.group(2))

def family(name, role=None, msb=None):
    s=(name or '').lower()
    if role=='DRUM' or msb==120:return 'DRUM_KIT'
    if role=='PERC':return 'PERCUSSION'
    rules=[
      ('BASS',r'\bbass\b|upright|contrabass'),
      ('GUITAR',r'guitar|gtr|nylon|steel str|dist\.?(?!ortion)|overdrive|power chord|telecaster|strat|jazz gt|clean gt|mute gt'),
      ('PIANO',r'piano|grand|upright piano|honky|epiano|e\.piano|electric piano|wurly|rhodes'),
      ('ORGAN',r'organ|drawbar|rotary'),
      ('ACCORDION_REED',r'accord|harmonica|musette|bandoneon|reed|mouth harp'),
      ('STRINGS',r'string|string ens|violin|viola|cello|orchestra|pizzicato'),
      ('BRASS',r'brass|trumpet|trombone|horn|tuba|flugel'),
      ('WOODWIND',r'sax|clarinet|flute|oboe|bassoon|piccolo|pan flute|recorder'),
      ('CHOIR_VOICE',r'choir|voice|vocal|doo|aah|ooh'),
      ('PAD',r'pad|atmos|warm pad|sweep'),
      ('SYNTH_LEAD',r'lead|synth|analog|square|saw|pulse'),
      ('MALLET',r'vibes|vibra|marimba|xylophone|kalimba|celesta|glock|bell'),
      ('PLUCK',r'harp|koto|sitar|banjo|mandolin|dulcimer|oud|bouzouki'),
      ('SFX',r'sfx|noise|effect|fx'),
    ]
    for fam,pat in rules:
        if re.search(pat,s):return fam
    if role and role.startswith('ACC'):return 'OTHER_ACC'
    return 'OTHER'

Z=zipfile.ZipFile(ZIP)
files=[n for n in Z.namelist() if n.lower().endswith(('.mid','.midi'))]
records=[]; invalid=collections.Counter(); file_meta=[]; sound_names=collections.Counter(); role_counts=collections.Counter(); elements=collections.Counter(); raw_texts=collections.Counter()

for fi,name in enumerate(files):
    data=Z.read(name); fmt,ppq,tracks=midi_chunks(data)
    # global tempo and time sig from track 0
    tempo=500000; ts=(4,4)
    for ev in parse_track(tracks[0]):
        if ev.kind=='meta' and ev.meta_type==0x51:
            b=ev.data[0]
            if len(b)==3: tempo=int.from_bytes(b,'big')
        elif ev.kind=='meta' and ev.meta_type==0x58:
            b=ev.data[0]
            if len(b)>=2: ts=(b[0],2**b[1])
    invalid_file=0
    for ti,ch in enumerate(tracks):
        evs=parse_track(ch)
        # identify initial track name
        tname=''
        for e in evs:
            if e.kind=='meta' and e.meta_type==0x03:
                txt=e.data[1].strip()
                if txt and not txt.startswith('SN:'):
                    tname=txt; break
        role,cv=norm_role(tname)
        if role: role_counts[role]+=1
        # state
        element=None; elem_start=0; bars=None
        bank_msb=None; bank_lsb=None; program=None; snd=None
        active=collections.defaultdict(list) # (ch,note)-> stack rec index
        last_onset_by_context={}
        for e in evs:
            if e.kind in ('note_on','note_off','cc','pc','pb','poly_at','ch_at') and not e.valid:
                invalid[(e.kind,e.a,e.b)] += 1; invalid_file += 1
                continue
            if e.kind=='meta':
                mt=e.meta_type; txt=e.data[1].strip()
                if mt==0x01:
                    raw_texts[txt]+=1
                    if EL_RE.match(txt): element=txt.title().replace('Variation','Variation').replace('Intro','Intro').replace('Fill','Fill').replace('Ending','Ending'); elem_start=e.time; bars=None; elements[element]+=1
                    else:
                        bm=BARS_RE.match(txt)
                        if bm: bars=int(bm.group(1))
                        elif txt and not txt.startswith('SN:'):
                            # sound name annotations are usually here. accept if close to a bank/program context later
                            snd=txt.strip()
                continue
            if e.kind=='cc':
                if e.a==0: bank_msb=e.b
                elif e.a==32: bank_lsb=e.b
                continue
            if e.kind=='pc':
                program=e.a
                continue
            if e.kind=='note_on' and e.b and e.b>0:
                # key context
                addr=(bank_msb,bank_lsb,program)
                key=(e.channel,e.a)
                # IOI within same sound/role/element/cv/track
                ctx=(fi,ti,role,cv,element,addr,snd)
                prev=last_onset_by_context.get(ctx)
                ioi=None if prev is None else e.time-prev
                last_onset_by_context[ctx]=e.time
                rec={
                  'file':name,'track':ti,'track_name':tname,'role':role,'cv':cv,'element':element,'element_start':elem_start,'bars':bars,
                  'ppq':ppq,'tempo':tempo,'ts_num':ts[0],'ts_den':ts[1],
                  'channel':e.channel,'msb':bank_msb,'lsb':bank_lsb,'program':program,'sound':snd,
                  'note':e.a,'velocity':e.b,'onset':e.time,'rel_onset':e.time-elem_start,'ioi':ioi,'duration':None
                }
                idx=len(records); records.append(rec); active[key].append(idx)
                sound_names[(bank_msb,bank_lsb,program,snd,role)] += 1
            elif (e.kind=='note_off') or (e.kind=='note_on' and (e.b==0 or e.b is None)):
                key=(e.channel,e.a)
                if active[key]:
                    idx=active[key].pop(0); records[idx]['duration']=max(0,e.time-records[idx]['onset'])
    file_meta.append({'file':name,'fmt':fmt,'ppq':ppq,'tracks':len(tracks),'tempo':tempo,'time_sig':ts,'invalid_events':invalid_file})

# basic per-sound aggregates
agg=collections.defaultdict(lambda:{'vel':[],'note':[],'dur':[],'ioi':[],'styles':set(),'segments':set(),'roles':collections.Counter(),'elements':collections.Counter(),'cvs':collections.Counter()})
for r in records:
    if r['msb'] is None or r['program'] is None: continue
    k=(r['msb'],r['lsb'],r['program'],r['sound'])
    a=agg[k];a['vel'].append(r['velocity']);a['note'].append(r['note']);
    if r['duration'] is not None:a['dur'].append(r['duration'])
    if r['ioi'] is not None:a['ioi'].append(r['ioi'])
    a['styles'].add(r['file']);a['segments'].add((r['file'],r['track'],r['element'],r['cv']))
    a['roles'][r['role']]+=1;a['elements'][r['element']]+=1;a['cvs'][r['cv']]+=1

summ=[]
for k,a in agg.items():
    msb,lsb,pc,snd=k; top_role=a['roles'].most_common(1)[0][0] if a['roles'] else None
    summ.append({
      'msb':msb,'lsb':lsb,'program':pc,'sound':snd,'family':family(snd,top_role,msb),'top_role':top_role,
      'notes':len(a['vel']),'styles':len(a['styles']),'segments':len(a['segments']),
      'velocity':qs(a['vel']),'key':qs(a['note']),'duration_ticks':qs(a['dur']),'ioi_ticks':qs(a['ioi']),
      'roles':a['roles'].most_common(),'elements':a['elements'].most_common(),
      'top_notes':collections.Counter(a['note']).most_common(12),'top_velocities':collections.Counter(a['vel']).most_common(12)
    })
summ.sort(key=lambda x:x['notes'], reverse=True)

# family aggregate
fagg=collections.defaultdict(lambda:{'vel':[],'note':[],'dur':[],'sounds':set(),'styles':set(),'roles':collections.Counter()})
for r in records:
    if r['msb'] is None or r['program'] is None: continue
    fam=family(r['sound'],r['role'],r['msb']); a=fagg[fam];a['vel'].append(r['velocity']);a['note'].append(r['note']);
    if r['duration'] is not None:a['dur'].append(r['duration'])
    a['sounds'].add((r['msb'],r['lsb'],r['program'],r['sound']));a['styles'].add(r['file']);a['roles'][r['role']]+=1
fs=[]
for fam,a in fagg.items():
    fs.append({'family':fam,'notes':len(a['vel']),'sound_count':len(a['sounds']),'styles':len(a['styles']),'velocity':qs(a['vel']),'key':qs(a['note']),'duration_ticks':qs(a['dur']),'roles':a['roles'].most_common()})
fs.sort(key=lambda x:x['notes'],reverse=True)

out={'files':file_meta,'invalid_summary':{str(k):v for k,v in invalid.items()},'record_count':len(records),'sound_count':len(summ),'sounds':summ,'families':fs}
with open('/mnt/data/factory_deep_summary.json','w') as f: json.dump(out,f,indent=2)
# dump records compact ndjson for later phase analysis
with open('/mnt/data/factory_records.ndjson','w') as f:
    for r in records:f.write(json.dumps(r,separators=(',',':'))+'\n')
print('files',len(files),'records',len(records),'sounds',len(summ),'families',len(fs),'invalid',sum(invalid.values()))
print('family summary')
for x in fs: print(x['family'],x['notes'],x['sound_count'],x['velocity'].get('p10'),x['velocity'].get('p50'),x['velocity'].get('p90'),x['key'].get('p10'),x['key'].get('p50'),x['key'].get('p90'))
print('\nTOP SOUNDS')
for x in summ[:40]: print((x['msb'],x['lsb'],x['program']),repr(x['sound']),x['top_role'],x['family'],x['notes'],x['styles'],x['velocity'].get('p10'),x['velocity'].get('p50'),x['velocity'].get('p90'),x['key'].get('p10'),x['key'].get('p50'),x['key'].get('p90'))