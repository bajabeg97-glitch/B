import unittest,tempfile,os,json,mido,statistics
from tests.helpers import make_mid
from pa800_optimizer.optimizer import Optimizer
from pa800_optimizer.config import OptimizeConfig
from pa800_optimizer.midi_doctor import scan_midi_health
class T(unittest.TestCase):
    def run_mode(self,mode):
        with tempfile.TemporaryDirectory() as d:
            a=make_mid(os.path.join(d,'in.mid')); b=os.path.join(d,'out.mid'); r=os.path.join(d,'r.json'); rep=Optimizer(OptimizeConfig.for_mode(mode)).optimize(a,b,r); self.assertTrue(rep.verifier['pass']); self.assertTrue(rep.factory_usage_meter['pass']); self.assertEqual(rep.factory_usage_meter['notes_total'],rep.factory_usage_meter['invariants']['classification_sum']); self.assertTrue(os.path.exists(b)); self.assertTrue(os.path.exists(r)); return len(rep.changes)
    def test_natural(self): self.assertGreaterEqual(self.run_mode('natural'),1)
    def test_live(self): self.assertGreaterEqual(self.run_mode('live'),1)
    def test_deterministic(self):
        with tempfile.TemporaryDirectory() as d:
            a=make_mid(os.path.join(d,'in.mid')); b=os.path.join(d,'a.mid'); c=os.path.join(d,'b.mid'); cfg=OptimizeConfig.for_mode('live'); Optimizer(cfg).optimize(a,b); Optimizer(cfg).optimize(a,c); self.assertEqual(__import__('pathlib').Path(b).read_bytes(),__import__('pathlib').Path(c).read_bytes())
    def test_pitch_count_preserved(self):
        with tempfile.TemporaryDirectory() as d:
            a=make_mid(os.path.join(d,'in.mid')); b=os.path.join(d,'out.mid'); Optimizer(OptimizeConfig.for_mode('max')).optimize(a,b)
            def sig(p):
                m=mido.MidiFile(p); return sorted((x.channel,x.note) for t in m.tracks for x in t if x.type=='note_on' and x.velocity>0)
            self.assertEqual(sig(a),sig(b))
    def test_midi_doctor_repairs_broken_input_end_to_end(self):
        with tempfile.TemporaryDirectory() as d:
            a=os.path.join(d,'broken.mid');b=os.path.join(d,'repaired.mid')
            m=mido.MidiFile(type=1,ticks_per_beat=192);t=mido.MidiTrack();m.tracks.append(t)
            t.append(mido.MetaMessage('track_name',name='Broken Song',time=0))
            t.append(mido.Message('note_off',channel=0,note=40,velocity=0,time=0))
            t.append(mido.Message('note_on',channel=0,note=60,velocity=90,time=24))
            t.append(mido.Message('control_change',channel=0,control=64,value=127,time=48));m.save(a)
            cfg=OptimizeConfig.for_mode('gentle');cfg.content_type='song'
            rep=Optimizer(cfg).optimize(a,b)
            self.assertTrue(rep.midi_repair['pass']);self.assertGreaterEqual(rep.midi_repair['repair_count'],3)
            self.assertTrue(scan_midi_health(mido.MidiFile(b))['pass']);self.assertTrue(rep.verifier['pass'])
    def test_preserve_is_byte_identical_and_has_no_mutation_authority(self):
        with tempfile.TemporaryDirectory() as d:
            source=make_mid(os.path.join(d,'in.mid'));output=os.path.join(d,'out.mid')
            report=Optimizer(OptimizeConfig.for_mode('preserve')).optimize(source,output)
            self.assertEqual(open(source,'rb').read(),open(output,'rb').read())
            self.assertEqual(report.changes,[]);self.assertEqual(report.mutation_ledger,[])
            self.assertEqual(report.quality_gate['check_status']['strict_preserve_has_no_mutations'],'PASS')
    def test_auto_sound_and_fx_change_end_to_end(self):
        with tempfile.TemporaryDirectory() as d:
            a=os.path.join(d,'voice.mid');b=os.path.join(d,'voice_out.mid')
            m=mido.MidiFile(type=1,ticks_per_beat=192);t=mido.MidiTrack();m.tracks.append(t);ch=11
            t.append(mido.MetaMessage('track_name',name='Variation 2 ACC1 CV1',time=0));t.append(mido.Message('control_change',channel=ch,control=0,value=121,time=0));t.append(mido.Message('control_change',channel=ch,control=32,value=8,time=0));t.append(mido.Message('program_change',channel=ch,program=24,time=0));t.append(mido.Message('control_change',channel=ch,control=91,value=60,time=0));t.append(mido.Message('control_change',channel=ch,control=93,value=40,time=0))
            for i in range(24):
                t.append(mido.Message('note_on',channel=ch,note=60+(i%7),velocity=75,time=0 if i==0 else 4));t.append(mido.Message('note_off',channel=ch,note=60+(i%7),velocity=0,time=116))
            m.save(a);whitelist=os.path.join(d,'voice_whitelist.json');open(whitelist,'w').write('{"approved_targets":[{"address":[121,15,24]}]}');cfg=OptimizeConfig.for_mode('auto');cfg.voice_hardware_whitelist_path=whitelist;rep=Optimizer(cfg).optimize(a,b)
            self.assertEqual(rep.automation_decision['effective_smart_policy'],'apply');self.assertTrue(rep.verifier['pass'])
            row=rep.intelligence[0];self.assertEqual(row['sound_apply_status'],'applied');self.assertEqual(tuple(row['candidate_address']),(121,15,24));self.assertEqual(row['fx_send_changes'],2)
            out=mido.MidiFile(b);self.assertEqual([x.value for x in out.tracks[0] if x.type=='control_change' and x.control==32],[15])
    def test_velocity_conductor_aligns_quiet_and_loud_files(self):
        with tempfile.TemporaryDirectory() as d:
            def make(path,velocities):
                m=mido.MidiFile(type=1,ticks_per_beat=192);t=mido.MidiTrack();m.tracks.append(t)
                t.append(mido.MetaMessage('track_name',name='Song Piano',time=0));t.append(mido.Message('control_change',channel=0,control=0,value=121,time=0));t.append(mido.Message('control_change',channel=0,control=32,value=3,time=0));t.append(mido.Message('program_change',channel=0,program=0,time=0))
                for i,v in enumerate(velocities):t.append(mido.Message('note_on',channel=0,note=60+i,velocity=v,time=0 if i==0 else 96));t.append(mido.Message('note_off',channel=0,note=60+i,velocity=0,time=72))
                m.save(path)
            low=os.path.join(d,'low.mid');high=os.path.join(d,'high.mid');lo=os.path.join(d,'low_out.mid');ho=os.path.join(d,'high_out.mid');make(low,[20,30,40,50,60,70,80,90]);make(high,[70,80,90,100,110,120,125,127])
            cfg=OptimizeConfig.for_mode('live');cfg.content_type='song';cfg.enable_sound_kit_selector=False;cfg.enable_fx_intelligence=False;cfg.enable_timing=False;cfg.enable_gate=False
            lr=Optimizer(cfg).optimize(low,lo);hr=Optimizer(cfg).optimize(high,ho)
            def median(path):return statistics.median(x.velocity for tr in mido.MidiFile(path).tracks for x in tr if x.type=='note_on' and x.velocity>0)
            self.assertLessEqual(abs(median(lo)-median(ho)),8);self.assertTrue(lr.velocity_conductor['pass']);self.assertTrue(hr.velocity_conductor['pass'])
            self.assertGreaterEqual(lr.workstation['velocity_budget_projection']['projected_notes'],1)
            self.assertTrue(lr.instrument_director['checks']['cumulative_velocity_delta_bounded'])
    def test_multi_program_channel_is_preserved_end_to_end(self):
        with tempfile.TemporaryDirectory() as d:
            source=os.path.join(d,'multi.mid');output=os.path.join(d,'multi_out.mid');m=mido.MidiFile(type=1,ticks_per_beat=192);t=mido.MidiTrack();m.tracks.append(t)
            t.extend([mido.MetaMessage('track_name',name='Multi Program Song',time=0),mido.Message('control_change',channel=0,control=0,value=121,time=0),mido.Message('control_change',channel=0,control=32,value=3,time=0),mido.Message('program_change',channel=0,program=0,time=0),mido.Message('note_on',channel=0,note=60,velocity=70,time=0),mido.Message('note_off',channel=0,note=60,velocity=0,time=96),mido.Message('control_change',channel=0,control=32,value=13,time=96),mido.Message('program_change',channel=0,program=24,time=0),mido.Message('note_on',channel=0,note=67,velocity=90,time=0),mido.Message('note_off',channel=0,note=67,velocity=0,time=96)]);m.save(source)
            cfg=OptimizeConfig.for_mode('max');cfg.content_type='song';report=Optimizer(cfg).optimize(source,output)
            def address_events(path):
                return [(msg.type,getattr(msg,'control',None),getattr(msg,'value',None),getattr(msg,'program',None)) for track in mido.MidiFile(path).tracks for msg in track if msg.type=='program_change' or (msg.type=='control_change' and msg.control in (0,32))]
            self.assertEqual(address_events(source),address_events(output));self.assertEqual(report.compatibility['program_map']['multi_program_channels'],1)
            self.assertTrue(any('multi_program_preserved' in warning for warning in report.warnings));self.assertTrue(report.verifier['pass'])
            self.assertFalse(any(change.kind in ('velocity','velocity_conductor','timing','gate','performance_velocity') for change in report.changes))
            self.assertTrue(any(row['identity_profile']=='MULTI_PROGRAM_PRESERVE' for row in report.factory_usage))
    def test_report_path_cannot_alias_input_or_output(self):
        with tempfile.TemporaryDirectory() as d:
            source=make_mid(os.path.join(d,'in.mid'));output=os.path.join(d,'out.mid');optimizer=Optimizer(OptimizeConfig.for_mode('preserve'))
            with self.assertRaisesRegex(ValueError,'Report path'):optimizer.optimize(source,output,source)
            with self.assertRaisesRegex(ValueError,'Report path'):optimizer.optimize(source,output,output)
    def test_persisted_report_contains_commit_phase(self):
        with tempfile.TemporaryDirectory() as d:
            source=make_mid(os.path.join(d,'in.mid'));output=os.path.join(d,'out.mid');report_path=os.path.join(d,'report.json')
            report=Optimizer(OptimizeConfig.for_mode('preserve')).optimize(source,output,report_path);persisted=json.load(open(report_path,encoding='utf-8'))
            self.assertEqual(persisted['workstation']['completed_phases'],report.workstation['completed_phases'])
            self.assertEqual(persisted['workstation']['completed_phases'][-1],'COMMIT')
    def test_optimizer_emits_ordered_workstation_phase_callbacks(self):
        with tempfile.TemporaryDirectory() as d:
            source=make_mid(os.path.join(d,'in.mid'));output=os.path.join(d,'out.mid');phases=[]
            report=Optimizer(OptimizeConfig.for_mode('preserve'),phase_callback=lambda phase,details:phases.append(phase)).optimize(source,output)
            self.assertEqual(phases,['PREFLIGHT','DOCTOR','COMPATIBILITY','AI_RESOURCE_BRAIN','CONTEXT','VOICE_FX','STRUCTURAL_SOUND_COMMIT','ARTICULATION','STRUCTURAL_ARTICULATION_COMMIT','MUSICAL_CONTEXT','MUSICAL_UNDERSTANDING','SECTION_NARRATIVE','FAMILY_INTENT','INSTRUMENT_INTENT','PATTERN_ADVISOR','SONG_MAP','PHRASE_DOCTOR','REPAIR_PREVIEWS','AGENT_MESH','MUSICIAN_WORKFLOW','MIX_FX','MUSICAL_DECISION_BRAIN','PROPOSAL_ARBITRATION','EVENT_PROPOSAL_GENERATION','EVENT_PROPOSAL_COMMIT','REFINER_PROPOSAL_GENERATION','REFINER_PROPOSAL_COMMIT','PERFORMANCE_SHAPING','TRANSACTION_COVERAGE','MUTATION_ARBITER','QUALITY_DELTA','VERIFY','COMMIT'])
            self.assertEqual(report.workstation['completed_phases'],phases)
            self.assertTrue(report.authority_ledger['pass']);self.assertTrue(report.quality_gate['pass'])
            self.assertTrue(report.instrument_director['pass'])
            self.assertTrue(report.musical_understanding['analyzer_only']);self.assertFalse(report.musical_understanding['authority_granted'])
    def test_sparse_e0_unknown_track_is_preserved_by_intent_guard(self):
        with tempfile.TemporaryDirectory() as d:
            source=os.path.join(d,'unknown.mid');output=os.path.join(d,'unknown_out.mid')
            mid=mido.MidiFile(type=1,ticks_per_beat=192);track=mido.MidiTrack();mid.tracks.append(track)
            track.extend([mido.MetaMessage('track_name',name='Mystery',time=0),mido.Message('program_change',channel=0,program=0,time=0),mido.Message('note_on',channel=0,note=60,velocity=52,time=0),mido.Message('note_off',channel=0,note=60,velocity=0,time=96)]);mid.save(source)
            cfg=OptimizeConfig.for_mode('max');cfg.content_type='song';cfg.enable_sound_kit_selector=False;cfg.enable_fx_intelligence=False
            report=Optimizer(cfg).optimize(source,output)
            self.assertEqual(report.instrument_intent['summary']['unknown_tracks'],1)
            self.assertFalse(any(change.kind in ('velocity','velocity_conductor','timing','gate','performance_velocity') for change in report.changes))
            self.assertTrue(any('INTENT_UNKNOWN_PRESERVE' in warning for warning in report.warnings))
if __name__=='__main__':unittest.main()
