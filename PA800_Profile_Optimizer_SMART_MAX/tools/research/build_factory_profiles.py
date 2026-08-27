import json, collections, math, csv, re, os
from statistics import median
ND='/mnt/data/factory_records.ndjson'

def pct(vals,p):
    if not vals:return None
    s=sorted(vals); x=(len(s)-1)*p; lo=int(math.floor(x)); hi=int(math.ceil(x))
    if lo==hi:return float(s[lo])
    return float(s[lo]*(hi-x)+s[hi]*(x-lo))

def stats(vals):
    if not vals:return None
    return {k:round(pct(vals,p),3) for k,p in [('raw_min',0),('p01',.01),('p05',.05),('working_min',.10),('ideal_min',.25),('ideal_center',.50),('ideal_max',.75),('working_max',.90),('p95',.95),('p99',.99),('raw_max',1)]}

def signed_resid(x,g):
    r=x%g
    if r>g/2:r-=g
    return r

def pitch_clusters(counter, min_frac=.003, gap=8):
    N=sum(counter.values())
    if N==0:return []
    thr=max(2, math.ceil(N*min_frac))
    active=sorted(n for n,c in counter.items() if c>=thr)
    if not active:return []
    groups=[[active[0]]]
    for n in active[1:]:
        if n-groups[-1][-1]>=gap:groups.append([n])
        else:groups[-1].append(n)
    out=[]
    for ns in groups:
        cnt=sum(counter[n] for n in ns)
        center=sum(n*counter[n] for n in ns)/cnt
        out.append({'min':ns[0],'max':ns[-1],'center':round(center,2),'count':cnt,'fraction':round(cnt/N,5)})
    return out

def vel_modes(counter):
    N=sum(counter.values())
    if N<50:return []
    arr=[0]*128
    for v,c in counter.items():
        if 0<=v<128:arr[v]=c
    # smooth [1,2,3,2,1]
    sm=[0.0]*128
    w=[1,2,3,2,1]
    for i in range(1,128):
        num=den=0
        for j,ww in enumerate(w,-2):
            k=i+j
            if 1<=k<128:num += arr[k]*ww; den += ww
        sm[i]=num/den if den else 0
    cand=[]; minheight=max(3,N*.003)
    for i in range(2,127):
        if sm[i]>=sm[i-1] and sm[i]>=sm[i+1] and sm[i]>=minheight:
            cand.append((sm[i],i))
    cand.sort(reverse=True)
    chosen=[]
    for h,i in cand:
        if all(abs(i-j)>=5 for _,j in chosen): chosen.append((h,i))
        if len(chosen)>=4:break
    return [{'center':i,'support_approx':round(h,1)} for h,i in sorted(chosen,key=lambda x:x[1])]

# Secondary organizational family only, exact addr remains primary.
GM_FAMS=['PIANO','CHROMATIC_PERC','ORGAN','GUITAR','BASS','STRINGS','ENSEMBLE','BRASS','REED','PIPE','SYNTH_LEAD','SYNTH_PAD','SYNTH_FX','ETHNIC','PERCUSSIVE','SFX']
def org_family(msb,pc,sound,role):
    if msb==120:return 'DRUM_KIT'
    s=(sound or '').lower()
    if re.search(r'accord|akk\.|musette|bandoneon|harmonica',s): return 'ACCORDION_REED'
    if re.search(r'pad',s): return 'SYNTH_PAD'
    if pc is not None and 0<=pc<128:return GM_FAMS[pc//8]
    return 'UNKNOWN'

def grade(n,styles):
    if n>=1000 and styles>=10:return 'STRONG'
    if n>=300 and styles>=5:return 'GOOD'
    if n>=100 and styles>=3:return 'LIMITED'
    return 'FALLBACK'

A=collections.defaultdict(lambda:{'vel':[],'note':collections.Counter(),'dur':[],'gate':[],'styles':set(),'segments':set(),'elements':collections.defaultdict(lambda:{'vel':[],'note':collections.Counter(),'dur':[],'styles':set()}),'roles':collections.Counter(),'cvs':collections.Counter(),'res48':[],'res32':[],'res24':[],'res64':[],'density':[],'chord_sizes':[],'intervals':[]})
# process segment by segment for gate/chord/density/interval
current_key=None; seg=[]
def flush(seg):
    if not seg:return
    # segment can contain multiple exact sounds only if program changes; group sound within segment but preserve onset order
    bysnd=collections.defaultdict(list)
    for r in seg:
        k=(r['msb'],r['lsb'],r['program'],r['sound'])
        bysnd[k].append(r)
    for k,rs in bysnd.items():
        a=A[k]
        onsets=collections.defaultdict(list)
        for r in rs:onsets[r['onset']].append(r)
        ots=sorted(onsets)
        # chord sizes exact onset
        a['chord_sizes'].extend(len(onsets[t]) for t in ots)
        # density notes/bar
        bars=next((r.get('bars') for r in rs if r.get('bars')),None)
        if bars and bars>0:a['density'].append(len(rs)/bars)
        # gate ratios to next distinct onset
        for i,t in enumerate(ots[:-1]):
            nxt=ots[i+1]; ioi=nxt-t
            if ioi<=0:continue
            for r in onsets[t]:
                if r['duration'] is not None:
                    ratio=r['duration']/ioi
                    if ratio<=8:a['gate'].append(ratio)
        # interval using median pitch at each onset; helpful as generic contour
        centers=[]
        for t in ots:
            ns=sorted(r['note'] for r in onsets[t]); centers.append(ns[len(ns)//2])
        for x,y in zip(centers,centers[1:]):a['intervals'].append(y-x)

with open(ND) as f:
    for line in f:
        r=json.loads(line)
        k=(r['msb'],r['lsb'],r['program'],r['sound'])
        a=A[k]
        a['vel'].append(r['velocity']);a['note'][r['note']]+=1
        if r['duration'] is not None:a['dur'].append(r['duration'])
        a['styles'].add(r['file']);a['segments'].add((r['file'],r['track'],r['element'],r['cv']))
        a['roles'][r['role']]+=1;a['cvs'][r['cv']]+=1
        rel=r['rel_onset'];a['res48'].append(signed_resid(rel,48));a['res32'].append(signed_resid(rel,32));a['res24'].append(signed_resid(rel,24));a['res64'].append(signed_resid(rel,64))
        e=a['elements'][r['element']];e['vel'].append(r['velocity']);e['note'][r['note']]+=1
        if r['duration'] is not None:e['dur'].append(r['duration'])
        e['styles'].add(r['file'])
        sk=(r['file'],r['track'],r['element'],r['cv'])
        if current_key is None:current_key=sk
        if sk!=current_key:
            flush(seg);seg=[];current_key=sk
        seg.append(r)
flush(seg)

# controller profile map
ctrl={}
if os.path.exists('/mnt/data/factory_controller_profiles.json'):
    for x in json.load(open('/mnt/data/factory_controller_profiles.json')):
        ctrl[(x['msb'],x['lsb'],x['program'],x['sound'])]=x['counts']

profiles=[]
for k,a in A.items():
    msb,lsb,pc,sound=k; n=len(a['vel']);styles=len(a['styles']);top_role=a['roles'].most_common(1)[0][0] if a['roles'] else None
    clusters=pitch_clusters(a['note'])
    primary=max(clusters,key=lambda x:x['count']) if clusters else None
    specials=[]
    if primary:
        for c in clusters:
            if c is primary:continue
            dist=min(abs(c['min']-primary['max']),abs(primary['min']-c['max']))
            if c['fraction']>=.01 and dist>=7:specials.append(c)
    elements={}
    for el,e in a['elements'].items():
        if len(e['vel'])<30:continue
        elements[str(el)]={'notes':len(e['vel']),'styles':len(e['styles']),'velocity':stats(e['vel']),'key':stats(list(e['note'].elements())),'duration_ticks':stats(e['dur'])}
    profile={
      'identity':{'msb':msb,'lsb':lsb,'program':pc,'sound':sound,'role':top_role,'org_family':org_family(msb,pc,sound,top_role),'rx_named':bool(sound and re.search(r'RX(?:\d|\b)',sound,re.I)),'dnc_named':bool(sound and re.search(r'DNC',sound,re.I))},
      'support':{'notes':n,'styles':styles,'segments':len(a['segments']),'grade':grade(n,styles)},
      'velocity':stats(a['vel']),'velocity_modes':vel_modes(collections.Counter(a['vel'])),
      'key':stats(list(a['note'].elements())),'pitch_clusters':clusters,'primary_pitch_cluster':primary,'special_pitch_candidates':specials,
      'duration_ticks':stats(a['dur']),'gate_to_next_onset':stats(a['gate']),
      'notes_per_bar':stats(a['density']),'exact_onset_chord_size':stats(a['chord_sizes']),'signed_interval':stats(a['intervals']),
      'timing_residual_ticks':{'grid_1_16_48':stats(a['res48']),'grid_triplet_32':stats(a['res32']),'grid_1_32_24':stats(a['res24']),'grid_triplet_8_64':stats(a['res64'])},
      'roles':a['roles'].most_common(),'cvs':a['cvs'].most_common(),'elements':elements,
      'controllers':ctrl.get(k,{})
    }
    profiles.append(profile)
profiles.sort(key=lambda p:p['support']['notes'],reverse=True)
json.dump({'schema':'factory_sound_performance_profiles_v1','profile_count':len(profiles),'profiles':profiles},open('/mnt/data/factory_sound_profiles_v1.json','w'),indent=2)
# CSV summary
cols=['msb','lsb','program','sound','role','family','rx','dnc','notes','styles','segments','grade','v_absmin','v_workmin','v_idealmin','v_center','v_idealmax','v_workmax','v_absmax','k_p10','k_p50','k_p90','dur_p10','dur_p50','dur_p90','gate_p10','gate_p50','gate_p90','special_clusters']
with open('/mnt/data/factory_sound_profiles_v1.csv','w',newline='',encoding='utf-8') as f:
 w=csv.DictWriter(f,fieldnames=cols);w.writeheader()
 for p in profiles:
  i=p['identity'];s=p['support'];v=p['velocity'] or {};kq=p['key'] or {};d=p['duration_ticks'] or {};g=p['gate_to_next_onset'] or {}
  w.writerow({'msb':i['msb'],'lsb':i['lsb'],'program':i['program'],'sound':i['sound'],'role':i['role'],'family':i['org_family'],'rx':i['rx_named'],'dnc':i['dnc_named'],'notes':s['notes'],'styles':s['styles'],'segments':s['segments'],'grade':s['grade'],
   'v_absmin':v.get('raw_min'),'v_workmin':v.get('working_min'),'v_idealmin':v.get('ideal_min'),'v_center':v.get('ideal_center'),'v_idealmax':v.get('ideal_max'),'v_workmax':v.get('working_max'),'v_absmax':v.get('raw_max'),
   'k_p10':kq.get('working_min'),'k_p50':kq.get('ideal_center'),'k_p90':kq.get('working_max'),'dur_p10':d.get('working_min'),'dur_p50':d.get('ideal_center'),'dur_p90':d.get('working_max'),'gate_p10':g.get('working_min'),'gate_p50':g.get('ideal_center'),'gate_p90':g.get('working_max'),'special_clusters':json.dumps(p['special_pitch_candidates'],separators=(',',':'))})
print('profiles',len(profiles))
print('rx profiles',sum(p['identity']['rx_named'] for p in profiles),'dnc',sum(p['identity']['dnc_named'] for p in profiles))
print('special candidate profiles',sum(bool(p['special_pitch_candidates']) for p in profiles),'rx specials',sum(bool(p['special_pitch_candidates']) and p['identity']['rx_named'] for p in profiles))
for p in [x for x in profiles if x['identity']['rx_named']][:15]:
 i=p['identity'];s=p['support'];print(i['msb'],i['lsb'],i['program'],i['sound'],s['notes'],'V',p['velocity']['working_min'],p['velocity']['ideal_center'],p['velocity']['working_max'],'Kprimary',p['primary_pitch_cluster'],'special',p['special_pitch_candidates'],'gate',p['gate_to_next_onset'])