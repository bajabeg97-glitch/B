import json,collections,math,csv,re
ND='/mnt/data/factory_records.ndjson'
def pct(vals,p):
 if not vals:return None
 s=sorted(vals);x=(len(s)-1)*p;lo=int(math.floor(x));hi=int(math.ceil(x));return float(s[lo] if lo==hi else s[lo]*(hi-x)+s[hi]*(x-lo))
def stats(vals):
 if not vals:return None
 return {k:round(pct(vals,p),3) for k,p in [('raw_min',0),('p05',.05),('working_min',.10),('ideal_min',.25),('ideal_center',.50),('ideal_max',.75),('working_max',.90),('p95',.95),('raw_max',1)]}
def resid(x,g):
 r=x%g
 return r-g if r>g/2 else r
A=collections.defaultdict(lambda:{'vel':[],'dur':[],'res48':[],'res32':[],'res24':[],'styles':set(),'elements':collections.Counter(),'cvs':collections.Counter(),'positions':collections.Counter()})
for line in open(ND):
 r=json.loads(line)
 if r['msb']!=120:continue
 k=(r['msb'],r['lsb'],r['program'],r['sound'],r['note'])
 a=A[k];a['vel'].append(r['velocity']);
 if r['duration'] is not None:a['dur'].append(r['duration'])
 a['res48'].append(resid(r['rel_onset'],48));a['res32'].append(resid(r['rel_onset'],32));a['res24'].append(resid(r['rel_onset'],24));a['styles'].add(r['file']);a['elements'][r['element']]+=1;a['cvs'][r['cv']]+=1
 # 1/16 phase index within quarter: round to nearest 12? use raw modulo 192 in 12-tick bins
 a['positions'][round((r['rel_onset']%192)/12)*12 % 192]+=1
P=[]
for k,a in A.items():
 msb,lsb,pc,snd,note=k
 n=len(a['vel']); styles=len(a['styles'])
 P.append({'kit':{'msb':msb,'lsb':lsb,'program':pc,'sound':snd},'key':note,'support':{'hits':n,'styles':styles},'velocity':stats(a['vel']),'duration_ticks':stats(a['dur']),'timing_residual':{'48':stats(a['res48']),'32':stats(a['res32']),'24':stats(a['res24'])},'elements':a['elements'].most_common(),'cvs':a['cvs'].most_common(),'top_quarter_positions':a['positions'].most_common(8)})
P.sort(key=lambda x:x['support']['hits'],reverse=True)
json.dump({'schema':'factory_drum_key_profiles_v1','count':len(P),'profiles':P},open('/mnt/data/factory_drum_key_profiles_v1.json','w'),indent=2)
with open('/mnt/data/factory_drum_key_profiles_v1.csv','w',newline='',encoding='utf8') as f:
 cols=['msb','lsb','program','kit','key','hits','styles','v_absmin','v_workmin','v_idealmin','v_center','v_idealmax','v_workmax','v_absmax','dur_center','top_positions']
 w=csv.DictWriter(f,fieldnames=cols);w.writeheader()
 for p in P:
  v=p['velocity'];w.writerow({'msb':p['kit']['msb'],'lsb':p['kit']['lsb'],'program':p['kit']['program'],'kit':p['kit']['sound'],'key':p['key'],'hits':p['support']['hits'],'styles':p['support']['styles'],'v_absmin':v['raw_min'],'v_workmin':v['working_min'],'v_idealmin':v['ideal_min'],'v_center':v['ideal_center'],'v_idealmax':v['ideal_max'],'v_workmax':v['working_max'],'v_absmax':v['raw_max'],'dur_center':(p['duration_ticks'] or {}).get('ideal_center'),'top_positions':json.dumps(p['top_quarter_positions'],separators=(',',':'))})
print('drum key profiles',len(P),'kits',len(set((p['kit']['msb'],p['kit']['lsb'],p['kit']['program'],p['kit']['sound']) for p in P)))
for p in P[:30]: print(p['kit']['sound'],p['key'],p['support'],p['velocity'],p['top_quarter_positions'][:4])