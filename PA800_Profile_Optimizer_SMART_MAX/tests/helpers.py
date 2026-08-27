import mido

def make_mid(path, msb=121,lsb=13,program=33,channel=8,velocities=(60,70,80,90,100),notes=(36,38,40,43,45)):
    mid=mido.MidiFile(type=1,ticks_per_beat=192); t=mido.MidiTrack(); mid.tracks.append(t)
    t.append(mido.MetaMessage('track_name',name='BASS CV1',time=0)); t.append(mido.Message('control_change',channel=channel,control=0,value=msb,time=0)); t.append(mido.Message('control_change',channel=channel,control=32,value=lsb,time=0)); t.append(mido.Message('program_change',channel=channel,program=program,time=0))
    first=True
    for n,v in zip(notes,velocities):
        t.append(mido.Message('note_on',channel=channel,note=n,velocity=v,time=0 if first else 96)); t.append(mido.Message('note_off',channel=channel,note=n,velocity=0,time=60)); first=False
    mid.save(path); return path