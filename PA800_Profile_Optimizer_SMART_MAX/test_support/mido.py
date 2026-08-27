"""Small test-only Mido-compatible subset that reads and writes real SMF bytes.

It deliberately supports only the event types used by this project's tests.
Unlike the former PKL0/pickle stand-in, every saved fixture is consumable by a
normal MIDI parser and contains the actual tested events inside MTrk chunks.
"""
from __future__ import annotations

import math
import struct

__standard_smf_backend__=True


def _vlq(value):
    value=max(0,int(value));out=[value&0x7f];value>>=7
    while value:out.append(0x80|(value&0x7f));value>>=7
    return bytes(reversed(out))


def _read_vlq(data,pos):
    value=0
    for _ in range(4):
        if pos>=len(data):raise ValueError('truncated variable-length quantity')
        byte=data[pos];pos+=1;value=(value<<7)|(byte&0x7f)
        if not byte&0x80:return value,pos
    raise ValueError('invalid variable-length quantity')


class Message:
    is_meta=False
    def __init__(self,type,time=0,**kwargs):self.type=type;self.time=time;self.__dict__.update(kwargs)
    def copy(self,**kwargs):
        data=dict(self.__dict__);typ=data.pop('type');data.update(kwargs);return self.__class__(typ,**data)
    def dict(self):return dict(self.__dict__)
    def __repr__(self):return f"{self.__class__.__name__}({self.__dict__!r})"


class MetaMessage(Message):
    is_meta=True


class MidiTrack(list):pass


_TEXT_META={'text':0x01,'track_name':0x03,'lyrics':0x05,'marker':0x06}
_TEXT_META_REVERSE={value:key for key,value in _TEXT_META.items()}


def _encode_message(msg):
    typ=msg.type
    if isinstance(msg,MetaMessage) or getattr(msg,'is_meta',False):
        if typ in _TEXT_META:
            key='name' if typ=='track_name' else 'text'
            payload=str(getattr(msg,key,'')).encode('utf-8')
            return b'\xff'+bytes([_TEXT_META[typ]])+_vlq(len(payload))+payload
        if typ=='set_tempo':payload=int(getattr(msg,'tempo',500000)).to_bytes(3,'big')
        elif typ=='time_signature':
            denominator=max(1,int(getattr(msg,'denominator',4)));power=int(round(math.log2(denominator)))
            payload=bytes([int(getattr(msg,'numerator',4))&0xff,power&0xff,int(getattr(msg,'clocks_per_click',24))&0xff,int(getattr(msg,'notated_32nd_notes_per_beat',8))&0xff])
        elif typ=='end_of_track':payload=b''
        elif typ=='unknown_meta':payload=bytes(getattr(msg,'data',b''))
        else:raise ValueError('unsupported test meta message: '+typ)
        meta_type={'set_tempo':0x51,'time_signature':0x58,'end_of_track':0x2f,'unknown_meta':int(getattr(msg,'meta_type',0x7f))}[typ]
        return b'\xff'+bytes([meta_type])+_vlq(len(payload))+payload
    channel=int(getattr(msg,'channel',0))&0x0f
    if typ=='note_off':return bytes([0x80|channel,int(msg.note)&0x7f,int(getattr(msg,'velocity',0))&0x7f])
    if typ=='note_on':return bytes([0x90|channel,int(msg.note)&0x7f,int(getattr(msg,'velocity',64))&0x7f])
    if typ=='control_change':return bytes([0xb0|channel,int(msg.control)&0x7f,int(msg.value)&0x7f])
    if typ=='program_change':return bytes([0xc0|channel,int(msg.program)&0x7f])
    if typ=='aftertouch':return bytes([0xd0|channel,int(getattr(msg,'value',0))&0x7f])
    if typ=='pitchwheel':
        value=max(0,min(16383,int(getattr(msg,'pitch',0))+8192));return bytes([0xe0|channel,value&0x7f,(value>>7)&0x7f])
    if typ=='sysex':
        payload=bytes(getattr(msg,'data',b''));return b'\xf0'+_vlq(len(payload)+1)+payload+b'\xf7'
    raise ValueError('unsupported test MIDI message: '+typ)


def _decode_track(data):
    track=MidiTrack();pos=0;running=None
    while pos<len(data):
        delta,pos=_read_vlq(data,pos)
        if pos>=len(data):break
        first=data[pos]
        if first&0x80:status=first;pos+=1
        elif running is not None:status=running
        else:raise ValueError('running status without previous channel status')
        if status==0xff:
            running=None
            meta_type=data[pos];pos+=1;size,pos=_read_vlq(data,pos);payload=data[pos:pos+size];pos+=size
            if meta_type in _TEXT_META_REVERSE:
                typ=_TEXT_META_REVERSE[meta_type];key='name' if typ=='track_name' else 'text';track.append(MetaMessage(typ,time=delta,**{key:payload.decode('utf-8','replace')}))
            elif meta_type==0x51 and len(payload)==3:track.append(MetaMessage('set_tempo',time=delta,tempo=int.from_bytes(payload,'big')))
            elif meta_type==0x58 and len(payload)>=4:track.append(MetaMessage('time_signature',time=delta,numerator=payload[0],denominator=1<<payload[1],clocks_per_click=payload[2],notated_32nd_notes_per_beat=payload[3]))
            elif meta_type==0x2f:track.append(MetaMessage('end_of_track',time=delta));break
            else:track.append(MetaMessage('unknown_meta',time=delta,meta_type=meta_type,data=tuple(payload)))
            continue
        if status in (0xf0,0xf7):
            running=None;size,pos=_read_vlq(data,pos);payload=data[pos:pos+size];pos+=size
            if payload.endswith(b'\xf7'):payload=payload[:-1]
            track.append(Message('sysex',time=delta,data=tuple(payload)));continue
        running=status;kind=status&0xf0;channel=status&0x0f
        sizes={0x80:2,0x90:2,0xa0:2,0xb0:2,0xc0:1,0xd0:1,0xe0:2}
        size=sizes.get(kind)
        if size is None:raise ValueError('unsupported status byte: 0x%02x'%status)
        payload=data[pos:pos+size];pos+=size
        if len(payload)!=size:raise ValueError('truncated channel message')
        if kind==0x80:msg=Message('note_off',time=delta,channel=channel,note=payload[0],velocity=payload[1])
        elif kind==0x90:msg=Message('note_on',time=delta,channel=channel,note=payload[0],velocity=payload[1])
        elif kind==0xa0:msg=Message('polytouch',time=delta,channel=channel,note=payload[0],value=payload[1])
        elif kind==0xb0:msg=Message('control_change',time=delta,channel=channel,control=payload[0],value=payload[1])
        elif kind==0xc0:msg=Message('program_change',time=delta,channel=channel,program=payload[0])
        elif kind==0xd0:msg=Message('aftertouch',time=delta,channel=channel,value=payload[0])
        else:msg=Message('pitchwheel',time=delta,channel=channel,pitch=(payload[0]|payload[1]<<7)-8192)
        track.append(msg)
    return track


class MidiFile:
    def __init__(self,filename=None,type=1,ticks_per_beat=480,clip=False):
        self.type=type;self.ticks_per_beat=ticks_per_beat;self.tracks=[]
        if filename is not None:self._load(filename)
    def _load(self,filename):
        raw=open(filename,'rb').read()
        if raw[:4]!=b'MThd' or len(raw)<14:raise ValueError('not a Standard MIDI File')
        header_size=struct.unpack('>I',raw[4:8])[0]
        if header_size<6:raise ValueError('invalid MIDI header')
        self.type,track_count,self.ticks_per_beat=struct.unpack('>HHH',raw[8:14]);pos=8+header_size
        for _ in range(track_count):
            if raw[pos:pos+4]!=b'MTrk':raise ValueError('missing MTrk chunk')
            size=struct.unpack('>I',raw[pos+4:pos+8])[0];pos+=8;self.tracks.append(_decode_track(raw[pos:pos+size]));pos+=size
    def save(self,filename):
        chunks=[]
        for source in self.tracks:
            body=bytearray();has_eot=False
            for msg in source:
                body.extend(_vlq(getattr(msg,'time',0)));body.extend(_encode_message(msg));has_eot=has_eot or msg.type=='end_of_track'
            if not has_eot:body.extend(b'\x00\xff\x2f\x00')
            chunks.append(b'MTrk'+struct.pack('>I',len(body))+bytes(body))
        header=b'MThd'+struct.pack('>IHHH',6,int(self.type),len(chunks),max(1,min(32767,int(self.ticks_per_beat))))
        with open(filename,'wb') as stream:stream.write(header+b''.join(chunks))