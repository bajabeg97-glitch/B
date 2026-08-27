import json, math, statistics, collections, os, sys
try:
    import orjson
    loads=orjson.loads
except Exception:
    loads=json.loads

SRC='/mnt/data/factory_records.ndjson'
OUT='/mnt/data/factory_arranger_atoms_v1.json'

def q_from_hist(hist, p):
    n=sum(hist)
    if not n:return None
    target=p*(n-1)
    lo=math.floor(target); hi=math.ceil(target)
    def kth(k):
        s=0
        for i,c in enumerate(hist):
            s+=c
            if s>k:return i
        return len(hist)-1
    a=kth(lo); b=kth(hi)
    return a if lo==hi else a*(hi-target)+b*(target-lo)

def median(xs):
    return statistics.median(xs) if xs else None

def pct(xs,p):
    if not xs:return None
    xs=sorted(xs); z=(len(xs)-1)*p; a=math.floor(z);b=math.ceil(z)
    return xs[a] if a==b else xs[a]*(b-z)+xs[b]*(z-a)

class Seg:
    __slots__=('file','role','cv','element','start','bars','ppq','tsn','tsd','sound','addr','n','vh','dur_sum','dur_n','pitch_min','pitch_max','onsets','grid_hist','bar_masks','pitch_events','pitch_n','repeat','step','leap','interval_n','simul_groups','last_onset','last_pitch','unique_onsets')
    def __init__(self,r):
        self.file=r['file']; self.role=r['role']; self.cv=r['cv']; self.element=r['element']; self.start=r['element_start']; self.bars=r.get('bars'); self.ppq=r['ppq']; self.tsn=r['ts_num']; self.tsd=r['ts_den']; self.sound=r.get('sound'); self.addr=(r.get('msb'),r.get('lsb'),r.get('program'))
        self.n=0;self.vh=[0]*128;self.dur_sum=0;self.dur_n=0;self.pitch_min=999;self.pitch_max=-1
        self.onsets=set(); self.grid_hist=collections.Counter(); self.bar_masks=collections.defaultdict(int)
        self.pitch_events=0; self.pitch_n=0;self.repeat=0;self.step=0;self.leap=0;self.interval_n=0
        self.simul_groups=collections.Counter(); self.last_onset=None;self.last_pitch=None; self.unique_onsets=0
    def add(self,r):
        self.n+=1;v=r['velocity'];
        if 0<=v<128:self.vh[v]+=1
        d=r.get('duration')
        if isinstance(d,(int,float)):
            self.dur_sum+=d;self.dur_n+=1
        p=r['note'];self.pitch_min=min(self.pitch_min,p);self.pitch_max=max(self.pitch_max,p)
        rel=r['rel_onset']; self.onsets.add(rel); self.simul_groups[rel]+=1
        barlen=int(round(self.ppq*4*self.tsn/self.tsd)) if self.tsd else self.ppq*4
        if barlen<=0:barlen=self.ppq*4
        bar=max(0, rel//barlen); within=rel%barlen
        step=max(1,self.ppq//4) # 16th-note grid
        gi=int(round(within/step))
        subdiv=max(1,int(round(barlen/step)))
        gi%=subdiv
        self.grid_hist[gi]+=1; self.bar_masks[bar]|=(1<<gi)
        if self.role not in ('DRUM','PERC'):
            if self.last_onset is not None and rel!=self.last_onset and self.last_pitch is not None:
                iv=p-self.last_pitch; a=abs(iv); self.interval_n+=1
                if a==0:self.repeat+=1
                elif a<=2:self.step+=1
                elif a>=5:self.leap+=1
            if rel!=self.last_onset:
                self.last_onset=rel;self.last_pitch=p
    def summary(self):
        bl=int(round(self.ppq*4*self.tsn/self.tsd)) if self.tsd else self.ppq*4
        bars=self.bars or (max(1,(max(self.onsets) if self.onsets else 0)//max(bl,1)+1))
        onset_count=len(self.onsets)
        chord_sizes=list(self.simul_groups.values())
        masks=list(self.bar_masks.values())
        # pairwise consecutive bar mask jaccard
        sims=[]
        for a,b in zip(masks,masks[1:]):
            inter=(a&b).bit_count(); uni=(a|b).bit_count(); sims.append(inter/uni if uni else 1.0)
        return {
          'file':self.file,'role':self.role,'cv':self.cv,'element':self.element,'bars':bars,'ppq':self.ppq,'meter':f'{self.tsn}/{self.tsd}',
          'sound':self.sound,'addr':self.addr,'notes':self.n,'notes_per_bar':self.n/bars if bars else None,'unique_onsets':onset_count,'onsets_per_bar':onset_count/bars if bars else None,
          'velocity':{'p10':q_from_hist(self.vh,.10),'p25':q_from_hist(self.vh,.25),'p50':q_from_hist(self.vh,.5),'p75':q_from_hist(self.vh,.75),'p90':q_from_hist(self.vh,.90)},
          'duration_mean_ticks':self.dur_sum/self.dur_n if self.dur_n else None,
          'pitch_min':None if self.pitch_max<0 else self.pitch_min,'pitch_max':None if self.pitch_max<0 else self.pitch_max,
          'polyphony':{'mean_chord_size':sum(chord_sizes)/len(chord_sizes) if chord_sizes else 0,'p90_chord_size':pct(chord_sizes,.9) if chord_sizes else 0,'max_chord_size':max(chord_sizes) if chord_sizes else 0},
          'interval':{'repeat_ratio':self.repeat/self.interval_n if self.interval_n else None,'step_ratio':self.step/self.interval_n if self.interval_n else None,'leap_ratio':self.leap/self.interval_n if self.interval_n else None},
          'bar_pattern_repeat_similarity':sum(sims)/len(sims) if sims else None,
          'grid_hist':dict(self.grid_hist),
          'bar_masks':masks,
        }

segs={}
with open(SRC,'rb') as f:
    for line in f:
        r=loads(line)
        if not r.get('role') or not r.get('element') or not r.get('cv'):continue
        # include exact sound state in segment key; if sound text absent, address still carries state
        k=(r['file'],r['track'],r['role'],r['cv'],r['element'],r['element_start'],r.get('msb'),r.get('lsb'),r.get('program'),r.get('sound'))
        s=segs.get(k)
        if s is None:
            s=Seg(r);segs[k]=s
        s.add(r)

summaries=[s.summary() for s in segs.values()]

# aggregate by element x role and element overall
by_er=collections.defaultdict(list); by_el=collections.defaultdict(list); by_cv=collections.defaultdict(list)
for s in summaries:
    by_er[(s['element'],s['role'])].append(s);by_el[s['element']].append(s);by_cv[(s['element'],s['cv'],s['role'])].append(s)

def aggregate(rows):
    if not rows:return {}
    return {
      'segments':len(rows),'styles':len(set(r['file'] for r in rows)),'notes':sum(r['notes'] for r in rows),
      'notes_per_bar_median':median([r['notes_per_bar'] for r in rows if r['notes_per_bar'] is not None]),
      'onsets_per_bar_median':median([r['onsets_per_bar'] for r in rows if r['onsets_per_bar'] is not None]),
      'velocity_p50_median':median([r['velocity']['p50'] for r in rows if r['velocity']['p50'] is not None]),
      'velocity_p90_median':median([r['velocity']['p90'] for r in rows if r['velocity']['p90'] is not None]),
      'mean_chord_size_median':median([r['polyphony']['mean_chord_size'] for r in rows]),
      'bar_repeat_similarity_median':median([r['bar_pattern_repeat_similarity'] for r in rows if r['bar_pattern_repeat_similarity'] is not None]),
      'duration_mean_ticks_median':median([r['duration_mean_ticks'] for r in rows if r['duration_mean_ticks'] is not None]),
    }
agg_er={f'{e}|{r}':aggregate(v) for (e,r),v in by_er.items()}
agg_el={e:aggregate(v) for e,v in by_el.items()}

# variation progression within same style role cv: choose aggregate across sound-state fragments per element, sum/weighted stats approximate
style_rc=collections.defaultdict(lambda:collections.defaultdict(list))
for s in summaries:
    if s['element'] in ('Variation 1','Variation 2','Variation 3','Variation 4'):
        style_rc[(s['file'],s['role'],s['cv'])][s['element']].append(s)

def merge_rows(rows):
    n=sum(x['notes'] for x in rows); bars=max([x['bars'] or 1 for x in rows] or [1])
    return {'notes_per_bar':sum(x['notes'] for x in rows)/bars,
            'onsets_per_bar':sum(x['unique_onsets'] for x in rows)/bars,
            'v50':sum((x['velocity']['p50'] or 0)*x['notes'] for x in rows)/n if n else None,
            'chord':sum(x['polyphony']['mean_chord_size']*x['notes'] for x in rows)/n if n else None}
transitions=collections.defaultdict(list)
complete=0
for k,d in style_rc.items():
    if all(f'Variation {i}' in d for i in range(1,5)):
        complete+=1
        m={e:merge_rows(d[e]) for e in d}
        for i in range(1,4):
            a=m[f'Variation {i}'];b=m[f'Variation {i+1}']
            for metric in ('notes_per_bar','onsets_per_bar','v50','chord'):
                if a[metric] is not None and b[metric] is not None:
                    transitions[(f'V{i}->V{i+1}',metric)].append(b[metric]-a[metric])
prog={}
for (tr,metric),vals in transitions.items():
    prog.setdefault(tr,{})[metric]={'median_delta':median(vals),'p25_delta':pct(vals,.25),'p75_delta':pct(vals,.75),'positive_fraction':sum(v>0 for v in vals)/len(vals),'n':len(vals)}

# Active role coverage per style-element-CV (presence if notes>0)
coverage=collections.defaultdict(lambda:collections.Counter())
style_ec=collections.defaultdict(set)
for s in summaries:
    style_ec[(s['file'],s['element'],s['cv'])].add(s['role'])
for (file,e,cv),roles in style_ec.items():
    coverage[e]['contexts']+=1
    for role in roles:coverage[e][role]+=1
coverage_out={e:dict(c) for e,c in coverage.items()}
for e,c in coverage_out.items():
    ctx=c.get('contexts',1)
    c['role_presence_fraction']={r:c.get(r,0)/ctx for r in ('DRUM','PERC','BASS','ACC1','ACC2','ACC3','ACC4','ACC5')}

# Bars distributions by element from segment metadata dedup across file/element - use max bars found
bars_by=collections.defaultdict(list); seen=set()
for s in summaries:
    k=(s['file'],s['element'])
    if k not in seen and s['bars']:
        seen.add(k);bars_by[s['element']].append(s['bars'])
bars_summary={e:{'n':len(v),'counts':dict(collections.Counter(v)),'median':median(v)} for e,v in bars_by.items()}

# Pattern similarity between adjacent variations using role/cv grid hist occupancy across whole element
# Create aggregate mask across bars for each segment: OR masks (which subdivisions ever used)
def aggmask(rows):
    m=0
    for r in rows:
        for bm in r['bar_masks']:m|=bm
    return m
similarity=collections.defaultdict(list)
for k,d in style_rc.items():
    for i in range(1,4):
        e1=f'Variation {i}';e2=f'Variation {i+1}'
        if e1 in d and e2 in d:
            a=aggmask(d[e1]);b=aggmask(d[e2]);u=(a|b).bit_count();j=(a&b).bit_count()/u if u else 1
            similarity[(f'V{i}->V{i+1}',k[1])].append(j)
sim_out={f'{tr}|{role}':{'median_jaccard':median(vals),'p25':pct(vals,.25),'p75':pct(vals,.75),'n':len(vals)} for (tr,role),vals in similarity.items()}

out={'segments':len(summaries),'element_overall':agg_el,'element_role':agg_er,'bars_by_element':bars_summary,'role_coverage_by_element':coverage_out,'variation_progression':prog,'variation_grid_similarity':sim_out,'complete_variation_role_cv_sets':complete}
with open(OUT,'w') as f:json.dump(out,f,indent=2)
print('segments',len(summaries),'complete_var_sets',complete)
print('\nELEMENT OVERALL')
for e in ['Variation 1','Variation 2','Variation 3','Variation 4','Fill 1','Fill 2','Break','Intro 1','Intro 2','Intro 3','Ending 1','Ending 2','Ending 3']:
    print(e,agg_el.get(e), 'bars',bars_summary.get(e))
print('\nVAR PROGRESSION')
for tr,d in prog.items():print(tr,d)
print('\nROLE PRESENCE V1-V4')
for e in ['Variation 1','Variation 2','Variation 3','Variation 4','Fill 1','Fill 2','Break','Intro 1','Intro 2','Intro 3','Ending 1','Ending 2','Ending 3']:
    c=coverage_out.get(e,{}); print(e,c.get('contexts'),c.get('role_presence_fraction'))
print('\nGRID SIMILARITY')
for k,v in sorted(sim_out.items()):
    if any(r in k for r in ['DRUM','BASS','ACC1','ACC2','PERC']):print(k,v)