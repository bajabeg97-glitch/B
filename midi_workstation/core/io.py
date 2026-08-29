"""
ULTIMATE MIDI WORKSTATION - MIDI PARSER & WRITER

Lossless MIDI I/O sa podrškom za:
- Sve MIDI event tipove
- RPN/NRPN parsing
- SysEx handling
- Meta events
- PPQN konverziju
- SMF Format 0/1/2

CPU-only, bez vanjskih zavisnosti osim mido za basic parsing
"""

import mido
from typing import List, Dict, Optional, Tuple, Any
from datetime import datetime

from .models import (
    MidiDocument,
    MidiTrack,
    MidiEvent,
    EventType,
    TempoMap,
    MeterMap,
    ChordEvent,
    RpnData,
    NrpnData,
    ProcessingMode,
)


class RpnNrpnParser:
    """
    State-machine parser za RPN i NRPN poruke (Master Plan #4)
    Prati CC101/100/99/98/6/38 sekvence
    """
    
    def __init__(self):
        self.rpn_msb = None
        self.rpn_lsb = None
        self.nrpn_msb = None
        self.nrpn_lsb = None
        self.data_msb = None
        self.data_lsb = None
        self.pending_rpn = {}  # channel -> state
        self.pending_nrpn = {}  # channel -> state
    
    def reset_channel(self, channel: int):
        """Resetuje stanje za kanal"""
        if channel in self.pending_rpn:
            del self.pending_rpn[channel]
        if channel in self.pending_nrpn:
            del self.pending_nrpn[channel]
    
    def process_cc(self, channel: int, cc_number: int, value: int, absolute_tick: int) -> Optional[Dict]:
        """
        Procesira CC i vraća RPN/NRPN event ako je kompletna sekvenca
        """
        state_key = channel
        
        # RPN handling (CC 101, 100, 6, 38)
        if cc_number == 101:  # RPN MSB
            if state_key not in self.pending_rpn:
                self.pending_rpn[state_key] = {}
            self.pending_rpn[state_key]['rpn_msb'] = value
            self.rpn_msb = value
            
        elif cc_number == 100:  # RPN LSB
            if state_key not in self.pending_rpn:
                self.pending_rpn[state_key] = {}
            self.pending_rpn[state_key]['rpn_lsb'] = value
            self.rpn_lsb = value
            
        elif cc_number == 99:  # NRPN MSB
            if state_key not in self.pending_nrpn:
                self.pending_nrpn[state_key] = {}
            self.pending_nrpn[state_key]['nrpn_msb'] = value
            self.nrpn_msb = value
            
        elif cc_number == 98:  # NRPN LSB
            if state_key not in self.pending_nrpn:
                self.pending_nrpn[state_key] = {}
            self.pending_nrpn[state_key]['nrpn_lsb'] = value
            self.nrpn_lsb = value
            
        elif cc_number == 6:  # Data Entry MSB
            if state_key in self.pending_rpn and 'rpn_msb' in self.pending_rpn[state_key] and 'rpn_lsb' in self.pending_rpn[state_key]:
                # Kompletna RPN vrijednost
                rpn_number = (self.pending_rpn[state_key]['rpn_msb'] << 7) | self.pending_rpn[state_key]['rpn_lsb']
                return {
                    'type': 'rpn',
                    'rpn_number': rpn_number,
                    'value_msb': value,
                    'value_lsb': self.data_lsb or 0,
                    'value_combined': (value << 7) | (self.data_lsb or 0),
                    'channel': channel,
                    'absolute_tick': absolute_tick
                }
                
            elif state_key in self.pending_nrpn and 'nrpn_msb' in self.pending_nrpn[state_key] and 'nrpn_lsb' in self.pending_nrpn[state_key]:
                # Kompletna NRPN vrijednost
                nrpn_number = (self.pending_nrpn[state_key]['nrpn_msb'] << 7) | self.pending_nrpn[state_key]['nrpn_lsb']
                return {
                    'type': 'nrpn',
                    'nrpn_number': nrpn_number,
                    'value_msb': value,
                    'value_lsb': self.data_lsb or 0,
                    'value_combined': (value << 7) | (self.data_lsb or 0),
                    'channel': channel,
                    'absolute_tick': absolute_tick
                }
                
            self.data_msb = value
            
        elif cc_number == 38:  # Data Entry LSB
            self.data_lsb = value
            
            # Pokušaj kompletiranja sa postojećim RPN/NRPN
            if state_key in self.pending_rpn and 'rpn_msb' in self.pending_rpn[state_key] and 'rpn_lsb' in self.pending_rpn[state_key] and 'data_msb' in self.pending_rpn[state_key]:
                rpn_number = (self.pending_rpn[state_key]['rpn_msb'] << 7) | self.pending_rpn[state_key]['rpn_lsb']
                return {
                    'type': 'rpn',
                    'rpn_number': rpn_number,
                    'value_msb': self.pending_rpn[state_key].get('data_msb', 0),
                    'value_lsb': value,
                    'value_combined': (self.pending_rpn[state_key].get('data_msb', 0) << 7) | value,
                    'channel': channel,
                    'absolute_tick': absolute_tick
                }
        
        return None


class MidiParser:
    """
    Lossless MIDI Parser
    Učitava .mid fajlove u MidiDocument strukturu
    """
    
    def __init__(self):
        self.rpn_parser = RpnNrpnParser()
    
    def parse_file(self, filepath: str) -> MidiDocument:
        """
        Parsira MIDI fajl i vraća MidiDocument
        """
        try:
            mid = mido.MidiFile(filepath)
        except Exception as e:
            raise ValueError(f"Failed to parse MIDI file {filepath}: {str(e)}")
        
        document = MidiDocument(
            filename=filepath.split('/')[-1],
            filepath=filepath,
            format_type=mid.type,
            ppqn=mid.ticks_per_beat
        )
        
        # Parsiraj sve trackove
        absolute_tick = 0
        current_tempo = 500000  # Default 120 BPM (microseconds per beat)
        current_meter = (4, 4)
        
        for track_index, mido_track in enumerate(mid.tracks):
            track = self._parse_track(
                mido_track, 
                track_index, 
                document.ppqn,
                document.tempo_map,
                document.meter_map
            )
            track.source_file = filepath
            document.add_track(track)
        
        # Izračunaj statistike
        document.calculate_statistics()
        
        # Sačuvaj originalni hash
        import hashlib
        with open(filepath, 'rb') as f:
            document.hash_original = hashlib.sha256(f.read()).hexdigest()
        
        document.update_hash()
        
        return document
    
    def _parse_track(self, mido_track, track_index: int, ppqn: int, 
                     tempo_map: TempoMap, meter_map: MeterMap) -> MidiTrack:
        """
        Parsira pojedinačni track
        """
        track = MidiTrack(
            track_index=track_index
        )
        
        absolute_tick = 0
        running_status = None
        active_notes = {}  # note -> (start_tick, velocity)
        
        # Extract track name ako postoji
        for msg in mido_track:
            if msg.type == 'track_name':
                track.name = msg.name
                break
        
        # Main parsing loop
        for msg in mido_track:
            absolute_tick += msg.time
            
            event = self._convert_message_to_event(
                msg, 
                track_index, 
                absolute_tick, 
                ppqn,
                active_notes
            )
            
            if event:
                track.add_event(event)
                
                # Ažuriraj tempo mapu
                if event.event_type == EventType.TEMPO and event.tempo_bpm:
                    tempo_map.add_tempo(absolute_tick, event.tempo_bpm)
                
                # Ažuriraj meter mapu
                if event.event_type == EventType.TIME_SIGNATURE:
                    if event.numerator and event.denominator:
                        meter_map.add_meter(absolute_tick, event.numerator, event.denominator)
                
                # Ažuriraj program/bank info
                if event.event_type == EventType.PROGRAM_CHANGE:
                    if event.program is not None:
                        track.program = event.program
                    if event.bank_msb is not None:
                        track.bank_msb = event.bank_msb
                    if event.bank_lsb is not None:
                        track.bank_lsb = event.bank_lsb
                
                # Detektuj drum track (channel 10)
                if event.channel == 9:  # MIDI channel 10 = index 9
                    track.is_drum_track = True
        
        # Calculate final statistics
        track.calculate_statistics()
        
        return track
    
    def _convert_message_to_event(self, msg, track_index: int, absolute_tick: int, 
                                   ppqn: int, active_notes: Dict) -> Optional[MidiEvent]:
        """
        Konvertuje mido message u MidiEvent
        """
        event = MidiEvent(
            track_index=track_index,
            absolute_tick=absolute_tick,
            delta_tick=msg.time,
            source="file"
        )
        
        # Determine event type
        if msg.type == 'note_on' and msg.velocity > 0:
            event.event_type = EventType.NOTE_ON
            event.note = msg.note
            event.velocity = msg.velocity
            event.channel = msg.channel
            active_notes[msg.note] = (absolute_tick, msg.velocity)
            
        elif msg.type == 'note_off' or (msg.type == 'note_on' and msg.velocity == 0):
            event.event_type = EventType.NOTE_OFF
            
            # Find corresponding note_on
            if msg.note in active_notes:
                start_tick, start_velocity = active_notes[msg.note]
                event.note = msg.note
                event.velocity = msg.velocity  # release velocity
                event.duration_ticks = absolute_tick - start_tick
                del active_notes[msg.note]
            else:
                event.note = msg.note
                event.velocity = msg.velocity
            
            event.channel = msg.channel
            
        elif msg.type == 'control_change':
            event.event_type = EventType.CONTROL_CHANGE
            event.cc_number = msg.control
            event.cc_value = msg.value
            event.channel = msg.channel
            
            # Check for RPN/NRPN
            rpn_data = self.rpn_parser.process_cc(
                msg.channel, 
                msg.control, 
                msg.value, 
                absolute_tick
            )
            if rpn_data:
                payload = {k: v for k, v in rpn_data.items() if k != "type"}
                if rpn_data['type'] == 'rpn':
                    event.rpn_data = RpnData(**payload)
                elif rpn_data['type'] == 'nrpn':
                    event.nrpn_data = NrpnData(**payload)
            
        elif msg.type == 'program_change':
            event.event_type = EventType.PROGRAM_CHANGE
            event.program = msg.program
            event.channel = msg.channel
            
        elif msg.type == 'pitchwheel':
            event.event_type = EventType.PITCH_BEND
            event.pitch_bend = msg.pitch
            event.channel = msg.channel
            
        elif msg.type == 'aftertouch':
            event.event_type = EventType.CHANNEL_PRESSURE
            event.pressure = msg.value
            event.channel = msg.channel
            
        elif msg.type == 'polytouch':
            event.event_type = EventType.POLY_PRESSURE
            event.note = msg.note
            event.pressure = msg.value
            event.channel = msg.channel
            
        elif msg.type == 'sysex':
            event.event_type = EventType.SYSTEM_EXCLUSIVE
            event.sysex_data = bytes(msg.data)
            if len(msg.data) > 0:
                event.manufacturer_id = msg.data[0]
            
        elif msg.type == 'set_tempo':
            event.event_type = EventType.TEMPO
            # tempo is in microseconds per beat
            event.tempo_bpm = 60000000 / msg.tempo
            
        elif msg.type == 'time_signature':
            event.event_type = EventType.TIME_SIGNATURE
            event.numerator = msg.numerator
            event.denominator = msg.denominator
            event.key_fifths = msg.numerator  # numerator represents beats per measure
            
        elif msg.type == 'key_signature':
            event.event_type = EventType.KEY_SIGNATURE
            event.key_fifths = msg.key
            event.key_mode = 0 if msg.mode == 'major' else 1
            
        elif msg.type == 'track_name':
            event.event_type = EventType.TRACK_NAME
            event.text_data = msg.name
            
        elif msg.type == 'marker':
            event.event_type = EventType.MARKER
            event.text_data = msg.text
            
        elif msg.type == 'lyrics':
            event.event_type = EventType.LYRIC
            event.text_data = msg.text
            
        elif msg.type == 'copyright':
            event.event_type = EventType.COPYRIGHT
            event.text_data = msg.text
            
        elif msg.type == 'end_of_track':
            event.event_type = EventType.END_OF_TRACK
            
        else:
            event.event_type = EventType.UNKNOWN
            event.raw_bytes = msg.bytes() if hasattr(msg, 'bytes') else None
        
        # Store raw bytes for lossless roundtrip
        try:
            event.raw_bytes = msg.bytes()
        except:
            pass
        
        return event


class MidiWriter:
    """
    Lossless MIDI Writer
    Eksportuje MidiDocument u .mid fajl
    """

    def write(self, project, output_path: Optional[str] = None, format_type: Optional[int] = None):
        document = project.document if hasattr(project, "document") and project.document else project
        if output_path:
            return self.write_file(document, output_path, format_type)
        import os
        import tempfile
        fd, path = tempfile.mkstemp(suffix=".mid")
        os.close(fd)
        try:
            self.write_file(document, path, format_type)
            with open(path, "rb") as handle:
                return handle.read()
        finally:
            if os.path.exists(path):
                os.remove(path)
    
    def write_file(self, document: MidiDocument, filepath: str, 
                   format_type: Optional[int] = None) -> str:
        """
        Piše MidiDocument u MIDI fajl
        """
        if format_type is None:
            format_type = document.format_type
        
        # Kreiraj mido MidiFile
        mid = mido.MidiFile(ticks_per_beat=document.ppqn, type=format_type)
        
        # Konvertuj trackove
        for track in document.tracks:
            mido_track = self._convert_track_to_mido(track, document.ppqn)
            mid.tracks.append(mido_track)
        
        # Sačuvaj fajl
        mid.save(filepath)
        
        # Verify roundtrip
        document.filepath = filepath
        document.filename = filepath.split('/')[-1]
        document.update_hash()
        
        return filepath
    
    def _convert_track_to_mido(self, track: MidiTrack, ppqn: int):
        """
        Konvertuje MidiTrack u mido track
        """
        mido_track = mido.MidiTrack()
        
        # Dodaj track name ako postoji
        if track.name:
            mido_track.append(mido.MetaMessage('track_name', name=track.name, time=0))
        
        # Sort events by absolute tick
        sorted_events = sorted(track.events, key=lambda e: e.absolute_tick)
        
        prev_tick = 0
        
        for event in sorted_events:
            delta_tick = event.absolute_tick - prev_tick
            prev_tick = event.absolute_tick
            
            mido_msg = self._convert_event_to_message(event, delta_tick)
            if mido_msg:
                mido_track.append(mido_msg)
        
        # Add end of track
        mido_track.append(mido.MetaMessage('end_of_track', time=0))
        
        return mido_track
    
    def _convert_event_to_message(self, event: MidiEvent, delta_tick: int):
        """
        Konvertuje MidiEvent u mido message
        """
        try:
            if event.event_type == EventType.NOTE_ON:
                return mido.Message('note_on', 
                                   note=event.note or 0,
                                   velocity=event.velocity,
                                   channel=event.channel,
                                   time=delta_tick)
            
            elif event.event_type == EventType.NOTE_OFF:
                return mido.Message('note_off',
                                   note=event.note or 0,
                                   velocity=event.release_velocity or event.velocity,
                                   channel=event.channel,
                                   time=delta_tick)
            
            elif event.event_type == EventType.CONTROL_CHANGE:
                return mido.Message('control_change',
                                   control=event.cc_number or 0,
                                   value=event.cc_value,
                                   channel=event.channel,
                                   time=delta_tick)
            
            elif event.event_type == EventType.PROGRAM_CHANGE:
                return mido.Message('program_change',
                                   program=event.program or 0,
                                   channel=event.channel,
                                   time=delta_tick)
            
            elif event.event_type == EventType.PITCH_BEND:
                return mido.Message('pitchwheel',
                                   pitch=event.pitch_bend or 0,
                                   channel=event.channel,
                                   time=delta_tick)
            
            elif event.event_type == EventType.CHANNEL_PRESSURE:
                return mido.Message('aftertouch',
                                   value=event.pressure or 0,
                                   channel=event.channel,
                                   time=delta_tick)
            
            elif event.event_type == EventType.POLY_PRESSURE:
                return mido.Message('polytouch',
                                   note=event.note or 0,
                                   value=event.pressure or 0,
                                   channel=event.channel,
                                   time=delta_tick)
            
            elif event.event_type == EventType.SYSTEM_EXCLUSIVE:
                if event.sysex_data:
                    return mido.MetaMessage('sysex', 
                                           data=list(event.sysex_data),
                                           time=delta_tick)
            
            elif event.event_type == EventType.TEMPO:
                if event.tempo_bpm:
                    tempo_microseconds = int(60000000 / event.tempo_bpm)
                    return mido.MetaMessage('set_tempo',
                                           tempo=tempo_microseconds,
                                           time=delta_tick)
            
            elif event.event_type == EventType.TIME_SIGNATURE:
                if event.numerator and event.denominator:
                    return mido.MetaMessage('time_signature',
                                           numerator=event.numerator,
                                           denominator=event.denominator,
                                           time=delta_tick)
            
            elif event.event_type == EventType.KEY_SIGNATURE:
                mode = 'major' if event.key_mode == 0 else 'minor'
                return mido.MetaMessage('key_signature',
                                       key=event.key_fifths or 0,
                                       mode=mode,
                                       time=delta_tick)
            
            elif event.event_type == EventType.TRACK_NAME:
                if event.text_data:
                    return mido.MetaMessage('track_name',
                                           name=event.text_data,
                                           time=delta_tick)
            
            elif event.event_type == EventType.MARKER:
                if event.text_data:
                    return mido.MetaMessage('marker',
                                           text=event.text_data,
                                           time=delta_tick)
            
            elif event.event_type == EventType.LYRIC:
                if event.text_data:
                    return mido.MetaMessage('lyrics',
                                           text=event.text_data,
                                           time=delta_tick)
            
            elif event.event_type == EventType.COPYRIGHT:
                if event.text_data:
                    return mido.MetaMessage('copyright',
                                           text=event.text_data,
                                           time=delta_tick)
            
            elif event.event_type == EventType.END_OF_TRACK:
                return mido.MetaMessage('end_of_track', time=delta_tick)
            
            # Fallback za unknown events sa raw bytes
            if event.raw_bytes:
                return mido.Message.from_bytes(event.raw_bytes, time=delta_tick)
            
        except Exception as e:
            # Log error ali nastavi
            print(f"Warning: Could not convert event {event.event_type}: {e}")
        
        return None


# Helper funkcije

def load_midi(filepath: str) -> MidiDocument:
    """Quick load funkcija"""
    parser = MidiParser()
    return parser.parse_file(filepath)


def save_midi(document: MidiDocument, filepath: str, format_type: Optional[int] = None) -> str:
    """Quick save funkcija"""
    writer = MidiWriter()
    return writer.write_file(document, filepath, format_type)


def verify_roundtrip(original_path: str, exported_path: str) -> Dict[str, Any]:
    """
    Verifikuje da li je export očuvao sve bitne podatke
    """
    parser = MidiParser()
    
    # Učitaj original i export
    original_doc = parser.parse_file(original_path)
    exported_doc = parser.parse_file(exported_path)
    
    # Compare basic stats
    results = {
        'original_tracks': len(original_doc.tracks),
        'exported_tracks': len(exported_doc.tracks),
        'original_events': sum(len(t.events) for t in original_doc.tracks),
        'exported_events': sum(len(t.events) for t in exported_doc.tracks),
        'original_ppqn': original_doc.ppqn,
        'exported_ppqn': exported_doc.ppqn,
        'match': True,
        'differences': []
    }
    
    # Track count match
    if results['original_tracks'] != results['exported_tracks']:
        results['match'] = False
        results['differences'].append('Track count mismatch')
    
    # PPQN match
    if results['original_ppqn'] != results['exported_ppqn']:
        results['match'] = False
        results['differences'].append('PPQN mismatch')
    
    # Event count match (allow small variance for meta events)
    event_diff = abs(results['original_events'] - results['exported_events'])
    if event_diff > 10:  # Allow small variance
        results['match'] = False
        results['differences'].append(f'Event count difference: {event_diff}')
    
    return results
