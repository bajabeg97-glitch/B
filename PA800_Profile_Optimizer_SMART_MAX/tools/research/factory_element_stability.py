import json,hashlib
from collections import defaultdict,Counter
REC='/mnt/data/factory_records.ndjson'; OUT='/mnt/data/factory_element_profile_stability_v1.json'

def q(v,p):
 if not v:return None
 v=sorted(v);x=(len(v)-1)*p;i=int(x);f=x-i;return v[i]*(1-f)+v[min(i+1,len(v)-1)]*f

def fold(fn):return int(hashlib.sha1(fn.encode()).hexdigest()[:8],16)%3
# first pass support exact sound+role+element
sup=defaultdict(lambda:{'n':0,'styles':set()})
with open(REC,encoding='utf8') as f:
 for line in f:
  r=json.loads(line); k=(r['msb'],r['lsb'],r['program'],r['sound'],r['role'],r['element'])
  a=sup[k];a['n']+=1;a['styles'].add(r['file'])
elig={k for k,a in sup.items() if a['n']>=300 and len(a['styles'])>=5}
acc={k:[{'v':[],'styles':set()} for _ in range(3)] for k in elig}
with open(REC,encoding='utf8') as f:
 for line in f:
  r=json.loads(line); k=(r['msb'],r['lsb'],r['program'],r['sound'],r['role'],r['element'])
  if k not in acc: continue
  a=acc[k][fold(r['file'])];a['v'].append(r['velocity']);a['styles'].add(r['file'])
rows=[]; c=Counter(); fam=Counter()
for k,fs0 in acc.items():
 fs=[]
 for a in fs0:
  fs.append({'notes':len(a['v']),'styles':len(a['styles']),'p10':q(a['v'],.1),'p50':q(a['v'],.5),'p90':q(a['v'],.9)})
 valid=[x for x in fs if x['notes']>=50 and x['styles']>=1]
 if len(valid)>=2:
  s10=max(x['p10'] for x in valid)-min(x['p10'] for x in valid);s50=max(x['p50'] for x in valid)-min(x['p50'] for x in valid);s90=max(x['p90'] for x in valid)-min(x['p90'] for x in valid)
  if s50<=4 and s10<=8 and s90<=8: st='STABLE'
  elif s50<=8 and s10<=15 and s90<=15: st='MODERATE'
  else: st='CONTEXT_DEPENDENT'
 else:s10=s50=s90=None;st='INSUFFICIENT_SPLIT_SUPPORT'
 c[st]+=1
 rows.append({'identity':{'msb':k[0],'lsb':k[1],'program':k[2],'sound':k[3],'role':k[4],'element':k[5]},'support':{'notes':sup[k]['n'],'styles':len(sup[k]['styles'])},'folds':fs,'stability':st,'spread':{'p10':s10,'p50':s50,'p90':s90}})
json.dump({'schema':'factory-element-stability-v1','count':len(rows),'summary':dict(c),'profiles':rows},open(OUT,'w'),indent=2)
print('eligible',len(rows),'summary',dict(c))
# selected stable/moderate examples and selected sounds
for n in ['Finger Bass RX','Clean Guitar RX1','Clean Funk RX1','Standard Kit RX3','Grand Piano','Steirisch.Akk.1']:
 print('\n',n)
 for r in sorted([x for x in rows if x['identity']['sound']==n],key=lambda z:-z['support']['notes']):
  print(r['identity']['element'],r['support'],r['stability'],r['spread'],[(f['styles'],f['p10'],f['p50'],f['p90']) for f in r['folds']])