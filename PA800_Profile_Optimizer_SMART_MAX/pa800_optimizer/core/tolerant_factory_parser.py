"""Research-only tolerant raw SMF scanner.
Skips invalid channel-data events (>127) instead of clipping them.
It is intentionally separate from the production writer.
"""
from pathlib import Path
import struct

def read_vlq(data,pos):
    v=0
    while True:
        b=data[pos]; pos+=1; v=(v<<7)|(b&0x7f)
        if not b&0x80: return v,pos

def scan_invalid_channel_events(path):
    data=Path(path).read_bytes(); pos=14; bad=[]
    while pos+8<=len(data):
        if data[pos:pos+4]!=b'MTrk': break
        ln=struct.unpack('>I',data[pos+4:pos+8])[0]; body=data[pos+8:pos+8+ln]; pos+=8+ln
        p=0; running=None; tick=0
        while p<len(body):
            try:
                dt,p=read_vlq(body,p); tick+=dt; b=body[p]
                if b<0x80:
                    if running is None: break
                    status=running
                else:
                    p+=1; status=b
                    if status<0xF0: running=status
                if status==0xFF:
                    p+=1; l,p=read_vlq(body,p); p+=l; running=None; continue
                if status in (0xF0,0xF7):
                    l,p=read_vlq(body,p); p+=l; running=None; continue
                typ=status&0xF0; n=1 if typ in (0xC0,0xD0) else 2
                vals=[]
                for _ in range(n): vals.append(body[p]); p+=1
                if any(v>127 for v in vals): bad.append((tick,status,tuple(vals)))
            except Exception: break
    return bad