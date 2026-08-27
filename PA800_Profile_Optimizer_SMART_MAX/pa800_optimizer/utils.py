import hashlib, random, math

def clamp(v, lo, hi): return max(lo, min(hi, v))

def stable_seed(*parts):
    s='|'.join(str(x) for x in parts).encode('utf-8')
    return int(hashlib.sha256(s).hexdigest()[:16],16)

def deterministic_gauss(seed, mu=0.0, sigma=1.0):
    r=random.Random(seed)
    return r.gauss(mu,sigma)

def quantiles(values, ps=(.1,.25,.5,.75,.9)):
    if not values: return [0.0]*len(ps)
    a=sorted(values); n=len(a)
    out=[]
    for p in ps:
        x=(n-1)*p; i=int(x); f=x-i
        if i+1<n: out.append(a[i]*(1-f)+a[i+1]*f)
        else: out.append(float(a[i]))
    return out

def piecewise_map(x, src, dst):
    if len(src)!=len(dst): raise ValueError('src/dst length')
    if x<=src[0]:
        den=max(1e-9,src[1]-src[0]); return dst[0]+(x-src[0])*(dst[1]-dst[0])/den
    for i in range(len(src)-1):
        if x<=src[i+1]:
            den=max(1e-9,src[i+1]-src[i]); t=(x-src[i])/den
            return dst[i]+t*(dst[i+1]-dst[i])
    den=max(1e-9,src[-1]-src[-2]); return dst[-1]+(x-src[-1])*(dst[-1]-dst[-2])/den