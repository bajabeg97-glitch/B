from __future__ import annotations
import collections,json,re,struct,zipfile,argparse
from pathlib import Path
ROLE_RE=re.compile(r'^(DRUMS|PERC|BASS|ACC[1-5])\s+CV([1-6])',re.I)
EL_RE=re.compile(r'^(Variation\s+[1-4]|Intro\s+[1-3]|Fill\s+[1-3]|Break(?:/Fill)?|Break|Ending\s+[1-3])$',re.I)
BARS_RE=re.compile(r'^\s*(\d+)\s+Bars?\s*$',re.I)
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
   hi=st&240;c=st&15;n=1 if hi in (192,208) else 2
   if p+n>len(ch):break
   vals=list(ch[p:p+n]);p+=n;valid=all(v<128 for v in vals)
   kind={128:'off',144:'on',160:'poly_at',176:'cc',192:'pc',208:'ch_at',224:'pb'}.get(hi,'chan')
   yield t,kind,c,vals[0] if vals else None,vals[1] if len(vals)>1 else None,valid
  else:break

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--zip',required=True);ap.add_argument('--out',required=True);a=ap.parse_args()
 Z=zipfile.ZipFile(a.zip);gc=collections.Counter();ccv=collections.defaultdict(collections.Counter);meta=collections.Counter();texts=collections.Counter();bad=collections.Counter();sx=collections.Counter();nrpn=collections.Counter();rpn=collections.Counter();ctrl_ctx=collections.Counter();pb_ctx=collections.Counter();cc80_sounds=collections.Counter();cc81_sounds=collections.Counter()
 for name in [n for n in Z.namelist() if n.lower().endswith(('.mid','.midi'))]:
  fmt,ppq,trs=chunks(Z.read(name))
  for ti,ch in enumerate(trs):
   role=None;cv=None;el=None;msb=lsb=pc=None;snd=None; state=collections.defaultdict(lambda:{'nm':None,'nl':None,'rm':None,'rl':None})
   for t,kind,c,x,y,valid in parse(ch):
    if not valid:bad[(kind,x,y)]+=1;continue
    if kind=='meta':
     meta[x]+=1
     if x in (1,3,4,5,6,7):
      txt=y.decode('latin1','ignore').strip();texts[txt]+=1
      if x==3:
       m=ROLE_RE.match(txt)
       if m:role='DRUM' if m.group(1).upper()=='DRUMS' else m.group(1).upper();cv=int(m.group(2))
      elif x==1:
       if EL_RE.match(txt):el=txt
       elif txt and not BARS_RE.match(txt) and not txt.startswith('SN:'):snd=txt
     continue
    if kind=='sysex':gc['sysex']+=1;sx[len(y or b'')]+=1;continue
    if kind=='cc':
     gc[f'cc:{x}']+=1;ccv[x][y]+=1
     if x==0:msb=y
     elif x==32:lsb=y
     key=(role,el,cv,x);ctrl_ctx[key]+=1
     if x==80:cc80_sounds[(msb,lsb,pc,snd)]+=1
     if x==81:cc81_sounds[(msb,lsb,pc,snd)]+=1
     st=state[c]
     if x==99:st['nm']=y;st['rm']=st['rl']=None
     elif x==98:st['nl']=y
     elif x==101:st['rm']=y;st['nm']=st['nl']=None
     elif x==100:st['rl']=y
     elif x in (6,38):
      if st['nm'] is not None and st['nl'] is not None:nrpn[(st['nm'],st['nl'],x,y)]+=1
      if st['rm'] is not None and st['rl'] is not None:rpn[(st['rm'],st['rl'],x,y)]+=1
    elif kind=='pc':pc=x
    elif kind=='pb':gc['pb']+=1;pb_ctx[(role,el,cv)]+=1
    elif kind=='ch_at':gc['ch_at']+=1
    elif kind=='poly_at':gc['poly_at']+=1
 out={'global_counts':dict(gc),'cc_value_histograms':{str(k):dict(v) for k,v in ccv.items()},'cc_threshold_summary':{str(k):{'n':sum(v.values()),'ge64':sum(n for x,n in v.items() if x>=64),'ge90':sum(n for x,n in v.items() if x>=90),'zero':v.get(0,0),'min':min(v) if v else None,'max':max(v) if v else None} for k,v in ccv.items()},'meta_types':dict(meta),'top_texts':texts.most_common(500),'invalid_events':[[str(k),v] for k,v in bad.most_common()],'sysex_lengths':dict(sx),'nrpn_sequences':[[*k,n] for k,n in nrpn.most_common(500)],'rpn_sequences':[[*k,n] for k,n in rpn.most_common(500)],'controller_context_counts':[[*k,n] for k,n in ctrl_ctx.most_common()],'pb_context_counts':[[*k,n] for k,n in pb_ctx.most_common()],'cc80_sounds':[[*k,n] for k,n in cc80_sounds.most_common()],'cc81_sounds':[[*k,n] for k,n in cc81_sounds.most_common()]}
 Path(a.out).write_text(json.dumps(out,indent=2),encoding='utf-8');print(json.dumps({'counts':out['global_counts'],'nrpn':len(nrpn),'rpn':len(rpn),'cc80_sounds':len(cc80_sounds),'cc81_sounds':len(cc81_sounds)},indent=2))
if __name__=='__main__':main()