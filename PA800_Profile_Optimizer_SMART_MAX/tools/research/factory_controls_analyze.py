import zipfile, struct, re, collections, json, math
ZIP='/mnt/data/Factory Styles.zip'
EL_RE = re.compile(r'^(Variation\s+[1-4]|Intro\s+[1-3]|Fill\s+[1-3]|Break(?:/Fill)?|Ending\s+[1-3])$', re.I)
BARS_RE = re.compile(r'^\s*(\d+)\s+Bars?\s*$', re.I)
ROLE_RE = re.compile(r'^(DRUMS|PERC|BASS|ACC[1-5])\s+CV([1-6])', re.I)
def vlq(b,p):
 v=0
 while 1:
  x=b[p];p+=1;v=(v<<7)|(x&127)
  if not x&128:return v,p
def chunks(data):
 hlen=int.from_bytes(data[4:8],'big');fmt,ntr,div=struct.unpack('>HHH',data[8:14]);p=8+hlen;out=[]
 for _ in range(ntr):
  ln=int.from_bytes(data[p+4:p+8],'big');out.append(data[p+8:p+8+ln]);p+=8+ln
 return fmt,div,out
def parse(ch):
 p=0;run=None;t=0
 while p<len(ch):
  try:dt,p=vlq(ch,p)
  except:break
  t+=dt
  if p>=len(ch):break
  x=ch[p]
  if x<128:
   if run is None:break
   st=run
  else:st=x;p+=1;run=st if st<240 else None
  if st==255:
   if p>=len(ch):break
   mt=ch[p];p+=1
   try:ln,p=vlq(ch,p)
   except:break
   dat=ch[p:p+ln];p+=ln;yield t,'meta',None,mt,dat,True
  elif st in (240,247):
   try:ln,p=vlq(ch,p)
   except:break
   dat=ch[p:p+ln];p+=ln;yield t,'sysex',None,None,dat,True
  elif st<240:
   hi=st&240; c=st&15;n=1 if hi in (192,208) else 2
   if p+n>len(ch):break
   vals=list(ch[p:p+n]);p+=n; valid=all(v<128 for v in vals)
   kind={128:'off',144:'on',160:'poly_at',176:'cc',192:'pc',208:'ch_at',224:'pb'}[hi]
   yield t,kind,c,vals[0],vals[1] if len(vals)>1 else None,valid
  else:break
Z=zipfile.ZipFile(ZIP)
globalc=collections.Counter(); sndc=collections.defaultdict(collections.Counter); sndvals=collections.defaultdict(lambda:collections.defaultdict(collections.Counter)); rolec=collections.defaultdict(collections.Counter); elc=collections.defaultdict(collections.Counter)
for name in [n for n in Z.namelist() if n.lower().endswith('.mid')]:
 fmt,ppq,trs=chunks(Z.read(name))
 for ti,ch in enumerate(trs):
  evs=list(parse(ch)); tname=''
  for e in evs:
   if e[1]=='meta' and e[3]==3:
    txt=e[4].decode('latin1','ignore').strip()
    if txt and not txt.startswith('SN:'): tname=txt;break
  m=ROLE_RE.match(tname);role=(('DRUM' if m.group(1).upper()=='DRUMS' else m.group(1).upper()) if m else None)
  msb=lsb=pc=None;snd=None;element=None
  for t,kind,c,a,b,valid in evs:
   if kind=='meta':
    if a==1:
     txt=b.decode('latin1','ignore').strip()
     if EL_RE.match(txt): element=txt
     elif not BARS_RE.match(txt) and txt and not txt.startswith('SN:'): snd=txt
    continue
   if not valid:continue
   if kind=='cc':
    if a==0:msb=b
    elif a==32:lsb=b
    key=(msb,lsb,pc,snd)
    globalc[('cc',a)]+=1;sndc[key][('cc',a)]+=1;sndvals[key][('cc',a)][b]+=1;rolec[role][('cc',a)]+=1;elc[element][('cc',a)]+=1
   elif kind=='pc': pc=a
   elif kind=='pb':
    key=(msb,lsb,pc,snd);v=a+(b<<7)-8192
    globalc[('pb',None)]+=1;sndc[key][('pb',None)]+=1;sndvals[key][('pb',None)][v]+=1;rolec[role][('pb',None)]+=1
   elif kind=='ch_at':
    key=(msb,lsb,pc,snd);globalc[('ch_at',None)]+=1;sndc[key][('ch_at',None)]+=1;sndvals[key][('ch_at',None)][a]+=1;rolec[role][('ch_at',None)]+=1
   elif kind=='poly_at':
    key=(msb,lsb,pc,snd);globalc[('poly_at',None)]+=1;sndc[key][('poly_at',None)]+=1;rolec[role][('poly_at',None)]+=1
print('GLOBAL')
for k,v in globalc.most_common(): print(k,v)
print('\nPERFORMANCE CC relevant')
for cc in [1,2,7,11,64,65,66,67,71,72,73,74,91,93]:print(cc,globalc.get(('cc',cc),0))
print('PB',globalc.get(('pb',None),0),'CH_AT',globalc.get(('ch_at',None),0),'POLY_AT',globalc.get(('poly_at',None),0))
print('\nTop sounds with PB/AT/CC1/CC2/CC64')
score=[]
for k,c in sndc.items():
 s=sum(c.get(x,0) for x in [('pb',None),('ch_at',None),('cc',1),('cc',2),('cc',64)])
 if s:score.append((s,k,c))
for s,k,c in sorted(score,reverse=True)[:60]:
 print(s,k,{str(x):c[x] for x in c if x in [('pb',None),('ch_at',None),('cc',1),('cc',2),('cc',64),('cc',11),('cc',7)]})
# json top
out=[]
for s,k,c in sorted(score,reverse=True):
 out.append({'score':s,'msb':k[0],'lsb':k[1],'program':k[2],'sound':k[3], 'counts':{f'{a[0]}:{a[1]}':v for a,v in c.items()}})
json.dump(out,open('/mnt/data/factory_controller_profiles.json','w'),indent=2)