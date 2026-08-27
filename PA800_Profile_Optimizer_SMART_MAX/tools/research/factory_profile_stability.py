import json, hashlib, math, statistics
from collections import defaultdict

PROF='/mnt/data/factory_sound_profiles_v1.json'
REC='/mnt/data/factory_records.ndjson'
OUT='/mnt/data/factory_profile_stability_v1.json'

def q(vals,p):
    if not vals:return None
    s=sorted(vals); x=(len(s)-1)*p; i=int(x); f=x-i
    return s[i]*(1-f)+s[min(i+1,len(s)-1)]*f

def fold_for_file(fn):
    h=int(hashlib.sha1(fn.encode()).hexdigest()[:8],16)
    return h%3

D=json.load(open(PROF,encoding='utf8'))['profiles']
# exact includes role as profiles do
eligible={ (p['identity']['msb'],p['identity']['lsb'],p['identity']['program'],p['identity']['sound'],p['identity']['role']):p
           for p in D if p['support']['grade'] in ('STRONG','GOOD') }
acc={k:[{'v':[],'pitch':[],'dur':[],'styles':set()} for _ in range(3)] for k in eligible}
with open(REC,encoding='utf8') as f:
    for line in f:
        r=json.loads(line)
        k=(r['msb'],r['lsb'],r['program'],r['sound'],r['role'])
        if k not in acc: continue
        z=fold_for_file(r['file']); a=acc[k][z]
        a['v'].append(r['velocity']); a['pitch'].append(r['note'])
        if r.get('duration') is not None: a['dur'].append(r['duration'])
        a['styles'].add(r['file'])

rows=[]
for k,folds in acc.items():
    fs=[]
    for a in folds:
        fs.append({
          'notes':len(a['v']),'styles':len(a['styles']),
          'v_p10':q(a['v'],.10),'v_p25':q(a['v'],.25),'v_p50':q(a['v'],.5),'v_p75':q(a['v'],.75),'v_p90':q(a['v'],.90),
          'key_p10':q(a['pitch'],.10),'key_p50':q(a['pitch'],.5),'key_p90':q(a['pitch'],.90),
          'dur_p50':q(a['dur'],.5),
        })
    valid=[x for x in fs if x['notes']>=50 and x['styles']>=1]
    if len(valid)>=2:
        medspread=max(x['v_p50'] for x in valid)-min(x['v_p50'] for x in valid)
        p10spread=max(x['v_p10'] for x in valid)-min(x['v_p10'] for x in valid)
        p90spread=max(x['v_p90'] for x in valid)-min(x['v_p90'] for x in valid)
        keymed=max(x['key_p50'] for x in valid)-min(x['key_p50'] for x in valid)
        # stability: ≤4 median & ≤8 tails strong; ≤8 & ≤15 medium else context dependent
        if medspread<=4 and p10spread<=8 and p90spread<=8: stab='STABLE'
        elif medspread<=8 and p10spread<=15 and p90spread<=15: stab='MODERATE'
        else: stab='CONTEXT_DEPENDENT'
    else:
        medspread=p10spread=p90spread=keymed=None; stab='INSUFFICIENT_SPLIT_SUPPORT'
    p=eligible[k]
    rows.append({
      'identity':p['identity'],'support':p['support'],'folds':fs,'stability':stab,
      'velocity_fold_spread':{'p10':p10spread,'p50':medspread,'p90':p90spread},'key_median_fold_spread':keymed
    })

summary=defaultdict(int)
for r in rows: summary[r['stability']]+=1
byfam=defaultdict(lambda:defaultdict(int))
for r in rows: byfam[r['identity']['org_family']][r['stability']]+=1
json.dump({'schema':'factory-profile-stability-v1','profiles':rows,'summary':dict(summary),'by_family':{k:dict(v) for k,v in byfam.items()}},open(OUT,'w'),indent=2)
print('summary',dict(summary))
print('by family')
for k in sorted(byfam): print(k,dict(byfam[k]))
# print selected
names=['Finger Bass RX','Clean Guitar RX1','Clean Funk RX1','Standard Kit RX3','Grand Piano','Steirisch.Akk.1','Fat Brass','Jazz Clarinet','Movie Strings2','Fresh Air 2']
for n in names:
    rr=[r for r in rows if r['identity']['sound']==n]
    for r in rr[:3]: print(n,r['identity']['role'],r['support'],r['stability'],r['velocity_fold_spread'],[(x['notes'],x['styles'],x['v_p10'],x['v_p50'],x['v_p90']) for x in r['folds']])