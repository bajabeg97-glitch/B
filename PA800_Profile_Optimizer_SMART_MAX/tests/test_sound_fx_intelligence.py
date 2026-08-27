import unittest
import json
import tempfile
import mido
from pa800_optimizer.intelligence.sound_fx import normalize_family, FX_PROFILES, SoundFxIntelligence
from pa800_optimizer.profiles.registry import ProfileRegistry
from pa800_optimizer.models import TrackContext, SoundIdentity, NoteEvent

class TestSoundFxIntelligence(unittest.TestCase):
    def test_accordion_is_not_harmonica(self):
        self.assertEqual(normalize_family('ACCORDION_REED','Musette Accordion'), 'ACCORDION')
        self.assertEqual(normalize_family('ACCORDION_REED','Harmonica DNC'), 'HARMONICA')
        self.assertNotEqual(FX_PROFILES['ACCORDION'], FX_PROFILES['HARMONICA'])

    def test_exact_good_factory_sound_can_be_kept(self):
        reg=ProfileRegistry(); eng=SoundFxIntelligence(reg)
        p=reg.by_address[(121,3,0)][0]
        ctx=TrackContext(0,0,'ACC1',SoundIdentity(121,3,0,p['identity']['sound'],'PIANO'),family='PIANO')
        notes=[NoteEvent(0,0,n,90,i*120,i*120+100,i*2,i*2+1) for i,n in enumerate([55,60,64,67,72])]
        rec=eng.recommend(ctx,notes)
        self.assertEqual(rec.family,'PIANO')
        self.assertIsNotNone(rec.candidate_address)
        self.assertGreater(rec.score,60)

    def test_unknown_preserve_fx(self):
        reg=ProfileRegistry(); eng=SoundFxIntelligence(reg)
        ctx=TrackContext(0,0,'UNKNOWN',SoundIdentity(None,None,None,None,'UNKNOWN'),family='UNKNOWN')
        rec=eng.recommend(ctx,[])
        self.assertEqual(rec.action,'PRESERVE')
        self.assertEqual(rec.fx['chain'],'PRESERVE')

    def test_auto_gate_excludes_weak_unstable_and_conflicting_profiles(self):
        reg=ProfileRegistry(); allowed=[p for p in reg.profiles if reg.auto_candidate_allowed(p)[0]]
        self.assertGreater(len(allowed),0)
        for p in allowed:
            self.assertIn(p['support']['grade'],('STRONG','GOOD'))
            self.assertGreaterEqual(p['support']['styles'],5)
            self.assertIn(reg.profile_stability(p),('STABLE','MODERATE'))
            self.assertFalse(p['identity'].get('rx_named') or p['identity'].get('dnc_named'))
            i=p['identity']; self.assertNotIn((i['msb'],i['lsb'],i['program']),reg.conflicts)

    def test_instrument_change_requires_measurable_improvement(self):
        reg=ProfileRegistry();eng=SoundFxIntelligence(reg);p=reg.by_address[(121,8,24)][0]
        ctx=TrackContext(0,0,'ACC1',SoundIdentity(121,8,24,p['identity']['sound'],'GUITAR'),family='GUITAR',resolution_status='EXACT_ADDRESS')
        notes=[NoteEvent(0,0,60+(i%7),75,i*120,i*120+116,i*2,i*2+1) for i in range(24)]
        features={'ticks_per_beat':192,'controllers':{},'pitch_bend_events':0,'aftertouch_events':0,'existing_fx':{91:[],93:[]}}
        rec=eng.recommend(ctx,notes,features)
        self.assertEqual(rec.action,'SUGGEST_ONLY');self.assertEqual(tuple(rec.candidate_address),(121,15,24));self.assertGreaterEqual(rec.improvement,6)
        self.assertIn('E3',rec.reason)
        self.assertEqual(rec.evidence_level,'E2')

    def test_suggest_hardware_record_does_not_grant_auto_authority(self):
        reg=ProfileRegistry();p=reg.by_address[(121,8,24)][0]
        ctx=TrackContext(0,0,'ACC1',SoundIdentity(121,8,24,p['identity']['sound'],'GUITAR'),family='GUITAR',resolution_status='EXACT_ADDRESS')
        notes=[NoteEvent(0,0,60+(i%7),75,i*120,i*120+116,i*2,i*2+1) for i in range(24)]
        with tempfile.TemporaryDirectory() as directory:
            path=directory+'/evidence.json';open(path,'w',encoding='utf-8').write(json.dumps({'records':[{'kind':'voice','source_address':[121,8,24],'target_address':[121,15,24],'family':'GUITAR','aesthetic':'original','approval':'suggest'}]}))
            class Config:voice_aesthetic='original';voice_hardware_whitelist_path=None;hardware_evidence_path=path
            rec=SoundFxIntelligence(reg,Config()).recommend(ctx,notes,{'ticks_per_beat':192,'controllers':{},'pitch_bend_events':0,'aftertouch_events':0,'existing_fx':{91:[],93:[]}})
        self.assertEqual(rec.action,'SUGGEST_ONLY');self.assertEqual(rec.evidence_level,'E2');self.assertIsNone(rec.hardware_approval)

    def test_sound_apply_requires_single_unambiguous_address_sequence(self):
        reg=ProfileRegistry();eng=SoundFxIntelligence(reg);p=reg.by_address[(121,8,24)][0]
        ctx=TrackContext(0,0,'ACC1',SoundIdentity(121,8,24,p['identity']['sound'],'GUITAR'),family='GUITAR',resolution_status='EXACT_ADDRESS')
        notes=[NoteEvent(0,0,60+(i%7),75,i*120,i*120+116,i*2,i*2+1) for i in range(24)]
        eng.hardware_targets.add((121,15,24));rec=eng.recommend(ctx,notes,{'ticks_per_beat':192,'controllers':{},'pitch_bend_events':0,'aftertouch_events':0,'existing_fx':{91:[],93:[]}})
        mid=mido.MidiFile(type=1,ticks_per_beat=192);tr=mido.MidiTrack();mid.tracks.append(tr)
        tr.append(mido.Message('control_change',channel=0,control=0,value=121,time=0));tr.append(mido.Message('control_change',channel=0,control=32,value=8,time=0));tr.append(mido.Message('program_change',channel=0,program=24,time=0))
        changed,status=eng.apply_sound(mid,ctx,rec);self.assertTrue(changed);self.assertEqual(status,'applied')
        tr.append(mido.Message('program_change',channel=0,program=24,time=0))
        changed,status=eng.apply_sound(mid,ctx,rec);self.assertFalse(changed);self.assertEqual(status,'ambiguous_multiple_program_events')

    def test_redundant_bank_setup_with_one_program_is_safe_to_rewrite(self):
        reg=ProfileRegistry();eng=SoundFxIntelligence(reg);p=reg.by_address[(121,8,24)][0]
        ctx=TrackContext(0,0,'ACC1',SoundIdentity(121,8,24,p['identity']['sound'],'GUITAR'),family='GUITAR',resolution_status='EXACT_ADDRESS')
        notes=[NoteEvent(0,0,60+(i%7),75,i*120,i*120+116,i*2,i*2+1) for i in range(24)]
        eng.hardware_targets.add((121,15,24));rec=eng.recommend(ctx,notes,{'ticks_per_beat':192,'controllers':{},'pitch_bend_events':0,'aftertouch_events':0,'existing_fx':{91:[],93:[]}})
        mid=mido.MidiFile(type=1,ticks_per_beat=192);tr=mido.MidiTrack();mid.tracks.append(tr)
        tr.extend([
            mido.Message('control_change',channel=0,control=0,value=0,time=0),
            mido.Message('control_change',channel=0,control=0,value=121,time=120),
            mido.Message('control_change',channel=0,control=32,value=8,time=0),
            mido.Message('control_change',channel=0,control=0,value=121,time=0),
            mido.Message('control_change',channel=0,control=32,value=8,time=0),
            mido.Message('program_change',channel=0,program=24,time=0),
            mido.Message('control_change',channel=0,control=32,value=8,time=120),
        ])
        changed,status=eng.apply_sound(mid,ctx,rec)
        self.assertTrue(changed);self.assertEqual(status,'applied_redundant_bank_sequence')
        self.assertTrue(all(m.value==121 for m in tr if m.type=='control_change' and m.control==0))
        self.assertTrue(all(m.value==15 for m in tr if m.type=='control_change' and m.control==32))

    def test_safe_gm_upgrade_requires_same_program_and_large_evidence_gap(self):
        reg=ProfileRegistry();eng=SoundFxIntelligence(reg);target=reg.by_address[(121,15,24)][0]
        gm=TrackContext(0,0,'SONG',SoundIdentity(121,0,24,'Nylon Guitar GM','GUITAR'),family='GUITAR',resolution_status='EXACT_ADDRESS')
        self.assertTrue(eng._safe_gm_upgrade(gm,target,18.0,9.0,1.0))
        steel=TrackContext(0,0,'SONG',SoundIdentity(121,0,25,'Steel Guitar GM','GUITAR'),family='GUITAR',resolution_status='EXACT_ADDRESS')
        self.assertFalse(eng._safe_gm_upgrade(steel,target,18.0,9.0,1.0))
        self.assertFalse(eng._safe_gm_upgrade(gm,target,9.9,9.0,1.0))

    def test_factory_ranking_emits_safe_gm_upgrade_for_strong_same_program_fit(self):
        reg=ProfileRegistry();eng=SoundFxIntelligence(reg)
        ctx=TrackContext(0,0,'SONG',SoundIdentity(121,0,24,'Nylon Guitar GM','GUITAR'),family='GUITAR',resolution_status='EXACT_ADDRESS')
        notes=[NoteEvent(0,0,66+(i%7),70,i*120,i*120+116,i*2,i*2+1) for i in range(24)]
        rec=eng.recommend(ctx,notes,{'ticks_per_beat':192,'controllers':{},'pitch_bend_events':0,'aftertouch_events':0,'existing_fx':{91:[],93:[]}})
        self.assertEqual(rec.action,'SAFE_GM_UPGRADE');self.assertEqual(tuple(rec.candidate_address),(121,15,24))
        self.assertGreaterEqual(rec.improvement,10);self.assertGreaterEqual(rec.margin,7);self.assertGreaterEqual(rec.confidence,.95)

    def test_contextual_fx_is_drier_for_dense_material_and_bounded(self):
        reg=ProfileRegistry();eng=SoundFxIntelligence(reg);p=reg.by_address[(121,3,0)][0]
        ctx=TrackContext(0,0,'ACC1',SoundIdentity(121,3,0,p['identity']['sound'],'PIANO'),family='PIANO',resolution_status='EXACT_ADDRESS')
        sparse=[NoteEvent(0,0,60,80,i*768,i*768+300,i*2,i*2+1) for i in range(8)]
        dense=[NoteEvent(0,0,60+(i%8),80,i*20,i*20+20,i*2,i*2+1) for i in range(40)]
        base={'ticks_per_beat':192,'controllers':{},'pitch_bend_events':0,'aftertouch_events':0,'existing_fx':{91:[100],93:[100]}}
        a=eng.recommend(ctx,sparse,base);b=eng.recommend(ctx,dense,base)
        self.assertLess(b.fx['reverb'],a.fx['reverb'])
        mid=mido.MidiFile(type=1,ticks_per_beat=192);tr=mido.MidiTrack();mid.tracks.append(tr)
        tr.append(mido.Message('control_change',channel=0,control=91,value=100,time=0));tr.append(mido.Message('control_change',channel=0,control=93,value=100,time=0))
        self.assertEqual(eng.apply_fx_sends(mid,ctx,b),2)
        self.assertTrue(all(90<=msg.value<=100 for msg in tr))

    def test_fx_contour_breakpoints_are_preserved_by_common_offset(self):
        reg=ProfileRegistry();eng=SoundFxIntelligence(reg);ctx=TrackContext(0,0,'SONG',SoundIdentity(121,3,0,'Grand Piano','PIANO'),family='PIANO')
        rec=eng.recommend(ctx,[NoteEvent(0,0,60,80,0,96,0,1)]*8,{'ticks_per_beat':192,'controllers':{},'pitch_bend_events':0,'aftertouch_events':0,'existing_fx':{91:[20,50,80],93:[]},'level_values':{7:[100],11:[127]}})
        mid=mido.MidiFile(type=1,ticks_per_beat=192);tr=mido.MidiTrack();mid.tracks.append(tr)
        for value in (20,50,80):tr.append(mido.Message('control_change',channel=0,control=91,value=value,time=96))
        before=[m.value for m in tr];eng.apply_fx_sends(mid,ctx,rec);after=[m.value for m in tr]
        assert [b-a for a,b in zip(before[1:],before)]==[b-a for a,b in zip(after[1:],after)]

    def test_voice_aesthetic_models_have_distinct_scores(self):
        reg=ProfileRegistry();profile={'identity':{'sound':'Stereo Studio Grand','program':0},'support':{'notes':10000}}
        ctx=TrackContext(0,0,'SONG',SoundIdentity(121,0,0,'Classic Grand Piano GM','PIANO'),family='PIANO')
        class Config:voice_aesthetic='original';hardware_evidence_path=None;voice_hardware_whitelist_path=None
        original=SoundFxIntelligence(reg,Config())._aesthetic_score(profile,ctx);Config.voice_aesthetic='modern';modern=SoundFxIntelligence(reg,Config())._aesthetic_score(profile,ctx)
        assert original==0 and modern>0 and original!=modern

if __name__=='__main__': unittest.main()