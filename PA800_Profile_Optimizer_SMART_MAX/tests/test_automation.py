from pa800_optimizer.automation import AutomationDecision,decide_automation,materialize_config
from pa800_optimizer.config import OptimizeConfig
from pa800_optimizer.models import NoteEvent,SoundIdentity,TrackContext


class Registry:
    def __init__(self,grade='STRONG',styles=20,found=True):
        self.grade=grade;self.styles=styles;self.found=found

    def resolve_identity(self,*_args):
        if not self.found:return None,'NO_EXACT_PROFILE'
        return {'support':{'grade':self.grade,'styles':self.styles}},'EXACT_ADDRESS'

    def auto_candidate_allowed(self,profile):
        support=profile['support']
        ok=support['grade'] in ('STRONG','GOOD') and support['styles']>=5
        return ok,'test_gate'


def fixture(count=240,conflict=False,sensitive=False):
    identity=SoundIdentity(121,3,0,'Factory Piano','PIANO',sensitive,False,conflict)
    ctx=TrackContext(0,0,'ACC1',identity,'Variation 2',1,'PIANO','Variation 2 ACC1 CV1','style','EXACT_ADDRESS')
    contexts={(0,0):ctx}
    notes=[NoteEvent(0,0,60,90,i*48,i*48+36,i*2,i*2+1) for i in range(count)]
    return contexts,notes


def test_high_confidence_style_uses_strong_apply():
    contexts,notes=fixture()
    d=decide_automation(contexts,notes,Registry(),{'content_type':'style','confidence':.99,'ambiguous':False})
    assert (d.mode,d.smart_policy)==('strong','apply')


def test_maximum_confidence_large_style_uses_max_apply():
    contexts,notes=fixture(600)
    d=decide_automation(contexts,notes,Registry(),{'content_type':'style','confidence':.99,'ambiguous':False})
    assert (d.mode,d.smart_policy)==('max','apply')


def test_ambiguous_input_falls_back_to_preserve_suggest():
    contexts,notes=fixture()
    d=decide_automation(contexts,notes,Registry(),{'content_type':'song','confidence':.65,'ambiguous':True})
    assert (d.mode,d.smart_policy)==('preserve','suggest')


def test_missing_factory_coverage_falls_back_to_preserve():
    contexts,notes=fixture()
    d=decide_automation(contexts,notes,Registry(found=False),{'content_type':'style','confidence':.99,'ambiguous':False})
    assert (d.mode,d.smart_policy)==('preserve','suggest')


def test_exact_but_weak_current_profile_can_use_per_context_apply_gate():
    contexts,notes=fixture()
    d=decide_automation(contexts,notes,Registry(grade='FALLBACK',styles=2),{'content_type':'style','confidence':.99,'ambiguous':False})
    assert (d.mode,d.smart_policy)==('natural','apply')


def test_preserve_blocks_forced_apply_override():
    source=OptimizeConfig.for_mode('auto');source.smart_policy_override='apply'
    d=AutomationDecision('preserve','suggest',0,0,0,0,10,[])
    cfg,policy=materialize_config(source,d)
    assert policy=='suggest'
    assert cfg.apply_high_confidence_sound_changes is False
    assert cfg.preserve_controllers is True


def test_auto_preserve_is_strict_when_evidence_is_insufficient():
    source=OptimizeConfig.for_mode('auto')
    d=AutomationDecision('preserve','suggest',0.2,0,0,0,100,[])
    cfg,policy=materialize_config(source,d)
    assert policy=='suggest'
    assert cfg.velocity_conductor_strength==0
    assert cfg.enable_velocity_conductor is False
    assert cfg.enable_velocity is False
    assert cfg.apply_high_confidence_sound_changes is False
    assert cfg.auto_apply_safe_voice_upgrades is False
    assert cfg.autopilot is True


def test_explicit_preserve_is_strict_and_gentle_is_separate():
    cfg=OptimizeConfig.for_mode('preserve')
    assert cfg.velocity_conductor_strength==0
    assert OptimizeConfig.for_mode('gentle').velocity_conductor_strength==0.20

def test_autopilot_materialization_preserves_baja_factory_gold_neural_authority_flags():
    from types import SimpleNamespace
    from pa800_optimizer.automation import materialize_config
    src=OptimizeConfig.for_mode('max').enable_autonomous_baja_max()
    src.apply_trained_rhythm_model=True;src.trained_rhythm_model_path='encoder.json'
    decision=SimpleNamespace(mode='live',smart_policy='apply')
    cfg,policy=materialize_config(src,decision)
    assert cfg.autopilot and cfg.factory_gold_max and cfg.apply_baja_stage_profile
    assert cfg.apply_trained_rhythm_model and cfg.trained_rhythm_model_path=='encoder.json'
    assert cfg.ai_resource_policy=='auto' and policy=='apply'
