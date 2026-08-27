import json
import os
import tempfile
import unittest

from tests.helpers import make_mid
from pa800_optimizer.analysis.note_velocity_max import NoteVelocityMaxDetector


class NoteVelocityMaxTests(unittest.TestCase):
    def test_full_detection_fields(self):
        with tempfile.TemporaryDirectory() as d:
            p = make_mid(os.path.join(d, 'in.mid'), velocities=(60, 80, 90, 110, 127))
            r = NoteVelocityMaxDetector().analyze(p)
            self.assertEqual(r['summary']['notes'], 5)
            self.assertEqual(len(r['detections']), 5)
            x = r['detections'][2]
            self.assertIn('contextual_max', x['velocity_detection'])
            self.assertIn('working_max', x['velocity_detection'])
            self.assertIn('factory_raw_max', x['velocity_detection'])
            self.assertIn('zone', x['velocity_detection'])
            self.assertIn('local_context', x)
            self.assertIn('estimated_factory_percentile', x['velocity_detection'])

    def test_127_detected(self):
        with tempfile.TemporaryDirectory() as d:
            p = make_mid(os.path.join(d, 'in.mid'), velocities=(127, 127, 90, 80, 70))
            r = NoteVelocityMaxDetector().analyze(p)
            self.assertEqual(r['summary']['velocity_127'], 2)
            self.assertTrue(any(x['velocity_detection']['at_midi_max_127'] for x in r['detections']))

    def test_rx_low_velocity_protected(self):
        with tempfile.TemporaryDirectory() as d:
            p = make_mid(os.path.join(d, 'in.mid'), velocities=(10, 15, 20, 40, 90))
            r = NoteVelocityMaxDetector().analyze(p)
            low = [x for x in r['detections'] if x['note']['velocity'] <= 20]
            self.assertTrue(low)
            self.assertTrue(all(x['special_safety']['protected'] for x in low))
            self.assertTrue(all(x['velocity_detection']['contextual_max_policy'] == 'PROTECTED_ORIGINAL' for x in low))

    def test_json_csv_write(self):
        with tempfile.TemporaryDirectory() as d:
            p = make_mid(os.path.join(d, 'in.mid'))
            det = NoteVelocityMaxDetector(); r = det.analyze(p)
            j = os.path.join(d, 'r.json'); c = os.path.join(d, 'r.csv')
            det.write_json(r, j); det.write_csv(r, c)
            self.assertTrue(os.path.getsize(j) > 100)
            self.assertTrue(os.path.getsize(c) > 100)
            self.assertEqual(json.load(open(j, encoding='utf-8'))['schema'], 'PA800_NOTE_VELOCITY_MAX_DETECTION')

    def test_event_level_element_and_sound(self):
        import mido
        with tempfile.TemporaryDirectory() as d:
            p=os.path.join(d,'switch.mid')
            mid=mido.MidiFile(type=1,ticks_per_beat=192); t=mido.MidiTrack(); mid.tracks.append(t)
            ch=8
            t.append(mido.MetaMessage('track_name',name='BASS CV1',time=0))
            t.append(mido.MetaMessage('text',text='Variation 1',time=0))
            t.append(mido.Message('control_change',channel=ch,control=0,value=121,time=0))
            t.append(mido.Message('control_change',channel=ch,control=32,value=13,time=0))
            t.append(mido.MetaMessage('text',text='Finger Bass RX',time=0))
            t.append(mido.Message('program_change',channel=ch,program=33,time=0))
            t.append(mido.Message('note_on',channel=ch,note=36,velocity=90,time=0)); t.append(mido.Message('note_off',channel=ch,note=36,velocity=0,time=60))
            t.append(mido.MetaMessage('track_name',name='BASS CV1',time=132))
            t.append(mido.MetaMessage('text',text='Variation 2',time=0))
            t.append(mido.Message('control_change',channel=ch,control=0,value=121,time=0))
            t.append(mido.Message('control_change',channel=ch,control=32,value=4,time=0))
            t.append(mido.MetaMessage('text',text='SlapFing Bass RX',time=0))
            t.append(mido.Message('program_change',channel=ch,program=36,time=0))
            t.append(mido.Message('note_on',channel=ch,note=38,velocity=92,time=0)); t.append(mido.Message('note_off',channel=ch,note=38,velocity=0,time=60))
            mid.save(p)
            r=NoteVelocityMaxDetector().analyze(p)
            self.assertEqual(r['detections'][0]['context']['element'],'Variation 1')
            self.assertEqual(r['detections'][1]['context']['element'],'Variation 2')
            self.assertEqual(r['detections'][0]['context']['cv'],1)
            self.assertEqual(r['detections'][1]['context']['cv'],1)
            self.assertEqual(r['detections'][0]['sound']['name'],'Finger Bass RX')
            self.assertEqual(r['detections'][1]['sound']['name'],'SlapFing Bass RX')


if __name__ == '__main__':
    unittest.main()

class DncManualVelocityTests(unittest.TestCase):
    def test_manual_dnc_exact_and_controller_mapping(self):
        import mido
        with tempfile.TemporaryDirectory() as d:
            p=os.path.join(d,'dnc.mid')
            mid=mido.MidiFile(type=1,ticks_per_beat=192); t=mido.MidiTrack(); mid.tracks.append(t); ch=11
            t.append(mido.MetaMessage('track_name',name='ACC1 CV1',time=0))
            t.append(mido.Message('control_change',channel=ch,control=0,value=121,time=0))
            t.append(mido.Message('control_change',channel=ch,control=32,value=18,time=0))
            t.append(mido.Message('program_change',channel=ch,program=24,time=0))
            t.append(mido.Message('control_change',channel=ch,control=80,value=127,time=0))  # SC1
            t.append(mido.Message('control_change',channel=ch,control=1,value=64,time=0))    # joystick Y+
            t.append(mido.Message('note_on',channel=ch,note=60,velocity=90,time=0))
            t.append(mido.Message('note_off',channel=ch,note=60,velocity=0,time=60))
            t.append(mido.Message('note_on',channel=ch,note=64,velocity=92,time=2))
            t.append(mido.Message('note_off',channel=ch,note=64,velocity=0,time=60))
            mid.save(p)
            r=NoteVelocityMaxDetector().analyze(p)
            self.assertEqual(r['detections'][0]['sound']['name'],'Nylon Guitar DNC')
            self.assertTrue(r['detections'][0]['sound']['dnc_named'])
            dnc=r['detections'][1]['dnc_manual_state']
            self.assertTrue(dnc['is_dnc'])
            self.assertIn('SC1_CC80',dnc['active_candidates'])
            self.assertNotIn('SC1_CC1',dnc['active_candidates'])
            self.assertEqual(dnc['legato_max_range_example'],5)
            self.assertTrue(dnc['legato_candidate_using_15ms_example'])

    def test_semantic_velocity_v2_present(self):
        with tempfile.TemporaryDirectory() as d:
            p=make_mid(os.path.join(d,'in.mid'), velocities=(60,80,90,100,110))
            r=NoteVelocityMaxDetector().analyze(p)
            x=r['detections'][2]
            self.assertIn('semantic',x['profile'])
            self.assertTrue(x['profile']['semantic']['available'])
            self.assertIsNotNone(x['profile']['semantic']['exact_histogram_percentile'])
            self.assertIn('semantic_contextual_max',x['velocity_detection'])