import copy, json, os, shutil
from contextlib import ExitStack
from dataclasses import asdict
from collections import defaultdict,Counter
from pathlib import Path
from .profiles.registry import ProfileRegistry
from .core.midi_io import load_midi,load_midi_with_recovery,save_midi,extract_notes
from .analysis.context import build_contexts, detect_content_type_details
from .analysis.intent import classify_intents
from .safety.rx_dnc import protect_note
from .engines.velocity import optimize_velocity
from .engines.velocity_conductor import normalize_velocity
from .engines.timing import optimize_timing
from .engines.gate import optimize_gate
from .intelligence import SoundFxIntelligence
from .verifier import verify
from .models import Change,OptimizationReport
from .runtime_safety import OutputLock, temp_path_for, commit_artifacts
from .automation import decide_automation,materialize_config
from .midi_doctor import repair_midi,scan_midi_health,verify_repair_replay,repair_midi_transaction
from .articulation_director import ArticulationDirector
from .core.smf_preflight import require_valid_smf
from .analysis.musical_context import analyze_musical_context,evidence_for_context
from .analysis.musical_understanding import analyze_musical_understanding
from .analysis.instrument_intent import analyze_instrument_intent
from .analysis.family_intent import analyze_family_intents
from .analysis.section_narrative import analyze_section_narrative
from .engines.performance_director import run_performance_director
from .audition_queue import build_audition_queue
from .mix_fx_director import run_mix_fx_director
from .compatibility import analyze_compatibility,create_recovery_package
from .quality_gate import evaluate_quality_gate
from .analysis.factory_usage import build_factory_usage_meter
from .analysis.instrument_fingerprints import snapshot_instrument_state,audit_instrument_fingerprints
from .analysis.style_import_contract import analyze_style_import_contract
from .instruments.policies import FAMILY_CUMULATIVE_VELOCITY_CAP,policy_for
from .musician_workflow import build_musician_workflow,vocal_protected_keys
from .agents import _run_agent_mesh
from .analysis.song_map import _build_song_map
from .analysis.phrase_doctor import _analyze_phrase_doctor
from .analysis.repair_previews import _build_repair_previews,_filter_protected_repair_previews
from .neural.pattern_advisor import analyze_pattern_advisor
from .runtime_assets import _RuntimeAssetGuard
from .user_stage_profile import apply_stage_sound_defaults, apply_percussion_40_percent
from .structural_proposals import (clone_midi as clone_structural_midi, build_sound_address_proposals, arbitrate_sound_address_proposals, commit_sound_address_proposals, build_articulation_insert_proposals, commit_articulation_insert_proposals, verify_sound_transaction_replay, verify_articulation_transaction_replay)
from .ai_brain import AIResourceBrain, govern_config, resource_snapshot
from .musical_brain import build_musical_decision_plan
from .mutation_arbiter import audit_mutation_arbitration, build_pre_apply_mutation_policy, build_proposal_arbitration, filter_notes_by_proposal
from .quality_score import evidence_quality_snapshot, compare_quality
from .premium_control import audit_performance_budget, apply_selective_budget_rollback, reconcile_change_ledger_after_selective_rollback, recovery_record
from .event_proposals import (generate_dimension_proposals, arbitrate_event_proposals, commit_event_proposals,
    generate_refiner_proposals, arbitrate_controller_proposals, commit_controller_proposals,
    generate_velocity_budget_proposals, generate_mix_fx_proposals, generate_controller_diff_proposals)
from .transaction_coverage import audit_transaction_coverage


class OptimizationBlocked(RuntimeError):
    """Bounded machine-readable failure without embedding huge mutation ledgers."""
    def __init__(self,stage,diagnostics):
        self.stage=str(stage);self.diagnostics=diagnostics
        super().__init__('%s blocked output commit: %s' % (self.stage,json.dumps(diagnostics,ensure_ascii=False,sort_keys=True,default=str)))



class Optimizer:
    def __init__(self, config, registry=None, phase_callback=None):
        self.config=config; self.registry=registry or ProfileRegistry();self.phase_callback=phase_callback;self._completed_phases=[]
        model_path=(config.trained_rhythm_model_path if getattr(config,'trained_rhythm_model_path',None) else Path(__file__).resolve().parents[1]/'models'/'encoder.json')
        # One exact baseline per batch: avoids repeatedly copying the large
        # Factory corpus while still allowing atomic rollback on any mutation.
        self._runtime_asset_guard=_RuntimeAssetGuard(self.registry.data_dir,model_path)

    def _phase(self,name,details=None):
        self._completed_phases.append(name)
        if self.phase_callback:
            try:self.phase_callback(name,details or {})
            except Exception:pass

    def optimize(self,input_path,output_path,report_path=None):
        resolved_input=Path(input_path).resolve();resolved_output=Path(output_path).resolve();resolved_report=Path(report_path).resolve() if report_path else None
        if resolved_input==resolved_output:
            raise ValueError('Input and output must be different files.')
        if resolved_report and resolved_report in (resolved_input,resolved_output):
            raise ValueError('Report path must be different from input and output files.')
        out=Path(output_path);asset_guard=self._runtime_asset_guard;asset_guard.assert_unchanged()
        try:
            with ExitStack() as stack:
                for target in sorted({resolved_output,*([] if resolved_report is None else [resolved_report])},key=str):stack.enter_context(OutputLock(target))
                result=self._optimize_locked(input_path,output_path,report_path,asset_guard);asset_guard.assert_unchanged();return result
        except Exception as exc:
            message=str(exc)
            if any(marker in message for marker in ('UNRECOVERABLE_','MIDI Doctor could not establish structural integrity')):
                recovery=create_recovery_package(input_path,output_path,'preflight_parse_or_timing_map',message)
                raise RuntimeError(message+'; RECOVERY_PACKAGE='+str(recovery)) from exc
            raise

    def _optimize_locked(self,input_path,output_path,report_path=None,asset_guard=None):
        self._completed_phases=[]
        config=copy.deepcopy(self.config)
        if config.mode=='preserve' or config.export_preset=='preserve':config.lock_preserve()
        if getattr(config,'apply_trained_rhythm_model',False) and not getattr(config,'trained_rhythm_model_path',None):
            bundled=Path(__file__).resolve().parents[1]/'models'/'encoder.json'
            if bundled.is_file():config.trained_rhythm_model_path=str(bundled)
            else:config.apply_trained_rhythm_model=False
        strict_preserve=config.mode=='preserve' or config.export_preset=='preserve'
        smf_preflight=require_valid_smf(input_path,allow_zero_division_repair=config.enable_midi_repair)
        self._phase('PREFLIGHT',{'bytes':smf_preflight.get('bytes'),'format':smf_preflight.get('format'),'tracks':smf_preflight.get('declared_tracks')})
        if config.enable_midi_repair:
            raw_mid,load_repairs=load_midi_with_recovery(input_path,preflight=False)
            mid,repair_audit=repair_midi_transaction(raw_mid)
            if load_repairs:
                repair_audit['repairs']=load_repairs+repair_audit['repairs'];repair_audit['repair_count']=len(repair_audit['repairs']);repair_audit['load_recovery']=True
            repair_audit['smf_preflight']=smf_preflight
        else:
            mid=load_midi(input_path,preflight=False);repair_audit={'enabled':False,'before':scan_midi_health(mid),'after':scan_midi_health(mid),'repairs':[],'repair_count':0,'canonical_replay':{'pass':True,'disabled':True}}
            repair_audit['smf_preflight']=smf_preflight
        if config.enable_midi_repair and (not repair_audit.get('pass') or not repair_audit.get('canonical_replay',{}).get('pass')):
            raise RuntimeError('MIDI Doctor could not establish structural integrity: %r' % repair_audit.get('after'))
        self._phase('DOCTOR',{'repairs':repair_audit.get('repair_count',0),'pass':repair_audit.get('pass',True)})
        compatibility=analyze_compatibility(mid,input_path)
        if not compatibility.get('safe_for_optimization'):
            raise RuntimeError('UNRECOVERABLE_TIMING_MAP_CONFLICT: conflicting same-tick tempo or meter events require source re-export/manual review')
        self._phase('COMPATIBILITY',{'safe':compatibility.get('safe_for_optimization'),'multi_program_channels':compatibility.get('program_map',{}).get('multi_program_channels',0)})
        original=copy.deepcopy(mid)
        detection=detect_content_type_details(mid,config.content_type);content_type=detection['content_type']
        contexts=build_contexts(mid,self.registry,content_type); notes=extract_notes(mid); classify_intents(notes,contexts,mid.ticks_per_beat)
        # Central compute governor: musical authority stays unchanged.  The brain
        # may cap scientific-library threads or defer optional neural inference
        # under real memory/CPU pressure, falling back to Factory/Gold rules.
        resource_brain=AIResourceBrain(getattr(config,'ai_resource_policy','auto'))
        brain_snapshot=resource_snapshot()
        brain_decision=resource_brain.decide(input_path=input_path,note_count=len(notes),context_count=len(contexts),neural_requested=bool(getattr(config,'apply_trained_rhythm_model',False)),snapshot=brain_snapshot)
        requested_neural=bool(getattr(config,'apply_trained_rhythm_model',False))
        runtime_limits=resource_brain.apply_runtime_limits(brain_decision)
        config=govern_config(config,brain_decision)
        multi_program_keys={(int(row['track']),int(row['channel'])-1) for row in compatibility.get('program_map',{}).get('channels',[]) if row.get('multi_program')}
        for key in multi_program_keys:
            if key in contexts:
                contexts[key].identity.conflict=True;contexts[key].resolution_status='MULTI_PROGRAM_PRESERVE'
        notes_by_ctx=defaultdict(list)
        for n in notes: notes_by_ctx[(n.track_index,n.channel)].append(n)
        automation={}
        if config.autopilot:
            decision=decide_automation(contexts,notes,self.registry,detection);config,policy=materialize_config(config,decision)
            if config.mode=='preserve' or config.export_preset=='preserve':config.lock_preserve();policy='suggest'
            automation=decision.to_dict();automation['enabled']=True;automation['effective_smart_policy']=policy
        else:automation={'enabled':False,'mode':config.mode,'effective_smart_policy':config.smart_policy_override or ('apply' if config.apply_high_confidence_sound_changes else ('suggest' if config.enable_sound_kit_selector else 'off'))}
        rep=OptimizationReport(str(input_path),str(output_path),content_type=content_type,content_detection=detection,automation_decision=automation,midi_repair=repair_audit,compatibility=compatibility,workstation={'schema':'PA800_WORKSTATION_RUN_V1','export_preset':getattr(config,'export_preset','auto'),'musical_preset':getattr(config,'musical_preset','custom'),'phase_contract':['PREFLIGHT','DOCTOR','COMPATIBILITY','AI_RESOURCE_BRAIN','CONTEXT','VOICE_FX','STRUCTURAL_SOUND_COMMIT','ARTICULATION','STRUCTURAL_ARTICULATION_COMMIT','MUSICAL_CONTEXT','MUSICAL_UNDERSTANDING','SECTION_NARRATIVE','FAMILY_INTENT','INSTRUMENT_INTENT','PATTERN_ADVISOR','SONG_MAP','PHRASE_DOCTOR','REPAIR_PREVIEWS','AGENT_MESH','MUSICIAN_WORKFLOW','MIX_FX','MUSICAL_DECISION_BRAIN','PROPOSAL_ARBITRATION','EVENT_PROPOSAL_GENERATION','EVENT_PROPOSAL_COMMIT','REFINER_PROPOSAL_GENERATION','REFINER_PROPOSAL_COMMIT','PERFORMANCE_SHAPING','TRANSACTION_COVERAGE','MUTATION_ARBITER','QUALITY_DELTA','VERIFY','COMMIT']})
        rep.workstation['ai_resource_brain']={**brain_decision.to_dict(),'snapshot':brain_snapshot.to_dict(),'runtime_limits':runtime_limits,'neural_requested':requested_neural,'neural_effective':bool(getattr(config,'apply_trained_rhythm_model',False)),'musical_authority_changed':False}
        if requested_neural and not getattr(config,'apply_trained_rhythm_model',False):
            rep.warnings.append('AI resource brain deferred neural timing/gate inference; Factory/Gold deterministic fallback remains active.')
        self._phase('AI_RESOURCE_BRAIN',{'tier':brain_decision.tier,'threads':brain_decision.max_cpu_threads,'neural_requested':requested_neural,'neural_allowed':brain_decision.neural_allowed,'advisory_level':brain_decision.advisory_level})
        rep.style_import_contract=analyze_style_import_contract(mid) if content_type=='style' else {'schema':'PA800_STYLE_IMPORT_CONTRACT_V1','applicable':False,'mutations':0}
        self._phase('CONTEXT',{'content_type':content_type,'contexts':len(contexts),'notes':len(notes)})
        if detection.get('ambiguous'):
            rep.warnings.append('ambiguous_content_type: choose --content-type style or song explicitly; evidence=%r' % detection.get('reasons'))
        for channel in compatibility.get('program_map',{}).get('channels',[]):
            if channel.get('multi_program'):
                rep.warnings.append('multi_program_preserved track=%d ch=%d segments=%d addresses=%r' % (channel['track'],channel['channel'],channel['segment_count'],channel['unique_addresses']))

        # Smart Sound/Kit + FX decision layer runs before performance shaping.
        intel=SoundFxIntelligence(self.registry,config);rep.hardware_evidence=intel.hardware_evidence.summary()
        sound_changed=False
        sound_targets={}
        voice_sandbox=clone_structural_midi(mid)
        structural_sound_audit={'schema':'PA800_STRUCTURAL_SOUND_ARBITRATION_V1','accepted':[],'rejected':[],'pass':True}
        fx_channels=set()
        fx_event_authorizations=[]
        legacy_fx_sandbox=copy.deepcopy(mid)
        legacy_fx_requested=False
        legacy_fx_rows={}
        if config.enable_sound_kit_selector or config.enable_fx_intelligence:
            for key,ctx in contexts.items():
                features=intel.channel_features(mid,ctx)
                rec=intel.recommend(ctx,notes_by_ctx.get(key,[]),features)
                row=rec.to_dict()
                safe_auto=(config.autopilot and config.auto_apply_safe_voice_upgrades and rec.action=='SAFE_GM_UPGRADE')
                if config.enable_sound_kit_selector and (config.apply_high_confidence_sound_changes or safe_auto):
                    changed,status=intel.apply_sound(voice_sandbox,ctx,rec)
                    row['sound_apply_status']=status
                    sound_changed = sound_changed or changed
                    if changed:
                        sound_targets[key]=tuple(rec.candidate_address)
                else:
                    row['sound_apply_status']='disabled'
                sensitive_context=bool(ctx.identity.rx_named or ctx.identity.dnc_named)
                fx_safe=(not sensitive_context) and (rec.action not in ('AUTO_CANDIDATE','SAFE_GM_UPGRADE') or str(row.get('sound_apply_status','')).startswith('applied') or row.get('sound_apply_status')=='already_target')
                if config.enable_fx_intelligence and not config.enable_mix_fx_director and config.apply_existing_fx_sends and not config.preserve_controllers and fx_safe:
                    legacy_fx_requested=True
                    row['fx_send_changes']=intel.apply_fx_sends(legacy_fx_sandbox,ctx,rec,None)
                    legacy_fx_rows[key]=row
                    if row['fx_send_changes']:
                        row['fx_apply_status']='proposed_bounded_contextual_blend'
                    elif not sum((rec.fx.get('existing_send_events') or {}).values()):
                        row['fx_apply_status']='recommendation_only_no_existing_cc91_cc93'
                    else:row['fx_apply_status']='already_within_contextual_target'
                else:
                    row['fx_send_changes']=0
                    if config.enable_mix_fx_director and config.enable_fx_intelligence:
                        row['fx_apply_status']='deferred_to_mix_fx_director'
                    elif config.apply_existing_fx_sends and config.preserve_controllers:
                        row['fx_apply_status']='blocked_by_preserve_controllers'
                    elif config.apply_existing_fx_sends and not fx_safe:
                        row['fx_apply_status']='blocked_sensitive_or_unapplied_sound_candidate'
                rep.intelligence.append(row)
        if legacy_fx_requested:
            legacy_fx_props,legacy_fx_gen=generate_controller_diff_proposals(mid,legacy_fx_sandbox,(91,93),'LEGACY_FX_INTELLIGENCE')
            legacy_fx_arb=arbitrate_controller_proposals(legacy_fx_props)
            if not legacy_fx_arb.get('pass'):
                raise OptimizationBlocked('LEGACY_FX_PROPOSAL_ARBITRATION',{'conflicts':legacy_fx_arb.get('conflicts',[])[:20]})
            legacy_fx_commit=commit_controller_proposals(mid,legacy_fx_arb)
            fx_event_authorizations.extend(legacy_fx_commit.get('mutations',[]))
            for mutation in legacy_fx_commit.get('mutations',[]):fx_channels.add((int(mutation['track']),int(mutation['channel'])))
            rep.workstation['legacy_fx_transaction']={'generation':legacy_fx_gen,'arbitration':legacy_fx_arb,'commit':legacy_fx_commit}
            for key,row in legacy_fx_rows.items():
                if key in fx_channels:row['fx_apply_status']='applied_bounded_contextual_blend_via_transaction'
        else:
            rep.workstation['legacy_fx_transaction']={'schema':'PA800_LEGACY_FX_TRANSACTION_V1','enabled':False,'pass':True}

        # Explicit MAX-button stage defaults override the generic selector.
        # This is user authority, isolated from normal/autopilot modes.
        if getattr(config,'apply_baja_stage_profile',False):
            forced_targets,forced_rows=apply_stage_sound_defaults(voice_sandbox,contexts)
            if forced_targets:
                sound_targets.update(forced_targets);sound_changed=True
            rep.intelligence.extend([{'action':'USER_FORCED_STAGE_DEFAULT','confidence':1.0,**row} for row in forced_rows])
            rep.workstation['baja_stage_profile']={'enabled':True,'sound_defaults':forced_rows}
        # Structural Sound transaction: sandbox diff -> atomic address arbitration -> commit.
        structural_sound_proposals=build_sound_address_proposals(mid,voice_sandbox,source='sound_selector_or_baja_stage')
        structural_sound_audit=arbitrate_sound_address_proposals(structural_sound_proposals,sound_targets)
        sound_before_commit=copy.deepcopy(mid)
        committed_sound=commit_sound_address_proposals(mid,structural_sound_audit.get('accepted',[]))
        structural_sound_audit['canonical_replay']=verify_sound_transaction_replay(sound_before_commit,mid,structural_sound_audit.get('accepted',[]))
        if not structural_sound_audit['canonical_replay'].get('pass'):
            raise OptimizationBlocked('STRUCTURAL_SOUND_REPLAY',structural_sound_audit['canonical_replay'])
        sound_changed=bool(committed_sound)
        rep.workstation['structural_sound_transaction']={**structural_sound_audit,'committed':committed_sound}
        self._phase('VOICE_FX',{'recommendations':len(rep.intelligence),'sound_changed':sound_changed})
        self._phase('STRUCTURAL_SOUND_COMMIT',{'proposed':len(structural_sound_proposals),'accepted':len(structural_sound_audit.get('accepted',[])),'committed':len(committed_sound),'rejected':len(structural_sound_audit.get('rejected',[]))})

        # Rebuild contexts after an authorized sound rewrite so downstream Factory
        # profiles match the actual output address.
        if sound_changed:
            contexts=build_contexts(mid,self.registry,content_type)
            for key in multi_program_keys:
                if key in contexts:
                    contexts[key].identity.conflict=True;contexts[key].resolution_status='MULTI_PROGRAM_PRESERVE'
            notes=extract_notes(mid); classify_intents(notes,contexts,mid.ticks_per_beat)
            notes_by_ctx=defaultdict(list)
            for n in notes: notes_by_ctx[(n.track_index,n.channel)].append(n)

        articulation_insertions=[]
        articulation_structural_audit={'schema':'PA800_STRUCTURAL_INSERT_ARBITRATION_V1','accepted':[],'rejected':[],'pass':True}
        if config.enable_articulation_director:
            articulation_sandbox=clone_structural_midi(mid)
            rep.articulations,planned_insertions=ArticulationDirector(self.registry,config.hardware_evidence_path).process(articulation_sandbox,contexts,notes,apply=config.apply_articulation_triggers)
            articulation_structural_audit=build_articulation_insert_proposals(planned_insertions)
            articulation_before_commit=copy.deepcopy(mid)
            articulation_insertions=commit_articulation_insert_proposals(mid,articulation_structural_audit.get('accepted',[]))
            articulation_structural_audit['canonical_replay']=verify_articulation_transaction_replay(articulation_before_commit,mid,articulation_structural_audit.get('accepted',[]))
            if not articulation_structural_audit['canonical_replay'].get('pass'):
                raise OptimizationBlocked('STRUCTURAL_ARTICULATION_REPLAY',articulation_structural_audit['canonical_replay'])
            rep.articulations['applied_triggers']=len(articulation_insertions)//2
            rep.articulations['inserted_events']=len(articulation_insertions)
            rep.articulations['structural_transaction']=articulation_structural_audit
            if articulation_insertions:
                notes=extract_notes(mid);classify_intents(notes,contexts,mid.ticks_per_beat);notes_by_ctx=defaultdict(list)
                for n in notes:notes_by_ctx[(n.track_index,n.channel)].append(n)
        else:rep.articulations={'enabled':False,'policy':'off','contexts':[],'applied_triggers':0,'inserted_events':0}
        self._phase('ARTICULATION',{'applied_triggers':rep.articulations.get('applied_triggers',0)})
        self._phase('STRUCTURAL_ARTICULATION_COMMIT',{'accepted':len(articulation_structural_audit.get('accepted',[])),'rejected':len(articulation_structural_audit.get('rejected',[])),'inserted_events':len(articulation_insertions)})

        rep.audition_queue=build_audition_queue(rep.intelligence,rep.articulations)

        rep.musical_context=analyze_musical_context(mid,notes,contexts,content_type)
        self._phase('MUSICAL_CONTEXT',{'sections':rep.musical_context.get('summary',{}).get('sections',0),'tracks':rep.musical_context.get('summary',{}).get('tracks',0)})
        rep.musical_understanding=analyze_musical_understanding(mid,notes,contexts,rep.musical_context)
        self._phase('MUSICAL_UNDERSTANDING',{'observations':len(rep.musical_understanding.get('observations',[])),'suggestions':len(rep.musical_understanding.get('suggestions',[])),'uncertainties':len(rep.musical_understanding.get('uncertainties',[]))})
        rep.section_narrative=analyze_section_narrative(mid,notes,contexts,rep.musical_context,rep.musical_understanding)
        self._phase('SECTION_NARRATIVE',{'sections':rep.section_narrative.get('summary',{}).get('sections',0),'explicit_sections':rep.section_narrative.get('summary',{}).get('explicit_sections',0),'rejected_velocity_only':rep.section_narrative.get('summary',{}).get('rejected_velocity_only',0),'authority_granted':False})
        rep.family_intent=analyze_family_intents(mid,notes,contexts,rep.musical_context,rep.section_narrative)
        self._phase('FAMILY_INTENT',{'classified_notes':rep.family_intent.get('summary',{}).get('classified_notes',0),'protected_rows':rep.family_intent.get('summary',{}).get('protected_rows',0),'authority_granted':False})
        rep.instrument_intent=analyze_instrument_intent(mid,notes,contexts,rep.musical_context,rep.musical_understanding,rep.family_intent,rep.section_narrative)
        self._phase('INSTRUMENT_INTENT',{'tracks':rep.instrument_intent.get('summary',{}).get('tracks',0),'notes':rep.instrument_intent.get('summary',{}).get('notes',0),'unknown_tracks':rep.instrument_intent.get('summary',{}).get('unknown_tracks',0),'authority_granted':False})
        rep.pattern_advisor=analyze_pattern_advisor(notes,contexts,content_type)
        self._phase('PATTERN_ADVISOR',{'candidates':rep.pattern_advisor.get('summary',{}).get('candidates',0),'heads':len(rep.pattern_advisor.get('summary',{}).get('heads',{})),'authority_granted':False})
        rep.song_map=_build_song_map(notes,rep.musical_context,rep.section_narrative,rep.instrument_intent)
        self._phase('SONG_MAP',{'bars':rep.song_map.get('summary',{}).get('bars',0),'sections':rep.song_map.get('summary',{}).get('sections',0),'phrases':rep.song_map.get('summary',{}).get('phrases',0),'authority_granted':False})
        rep.phrase_doctor=_analyze_phrase_doctor(notes,rep.song_map,mid.ticks_per_beat)
        self._phase('PHRASE_DOCTOR',{'phrases':rep.phrase_doctor.get('summary',{}).get('phrases_considered',0),'findings':rep.phrase_doctor.get('summary',{}).get('findings',0),'authority_granted':False})
        rep.repair_previews=_build_repair_previews(notes,rep.phrase_doctor)
        self._phase('REPAIR_PREVIEWS',{'previews':rep.repair_previews.get('summary',{}).get('previews',0),'candidates':rep.repair_previews.get('summary',{}).get('candidates',0),'authority_granted':False})
        rep.audition_queue=build_audition_queue(rep.intelligence,rep.articulations,rep.repair_previews)
        rep.agent_mesh=_run_agent_mesh(config,rep.musical_context,rep.musical_understanding,rep.section_narrative,rep.family_intent,rep.instrument_intent,rep.song_map,rep.phrase_doctor)
        self._phase('AGENT_MESH',{'agents':len(rep.agent_mesh.get('agents',[])),'consensus':rep.agent_mesh.get('consensus'),'authority_granted':False})
        intent_unknown_keys={(int(row['track']),int(row['channel'])-1) for row in rep.instrument_intent.get('track_intents',[]) if row.get('label')=='UNKNOWN' and row.get('evidence_level')=='E0'}
        rep.musician_workflow=build_musician_workflow(config,rep.musical_context,rep.musical_understanding,rep.agent_mesh,rep.song_map,rep.phrase_doctor,rep.repair_previews)
        vocal_keys=vocal_protected_keys(rep.musical_context,config.vocal_friendly_mode)
        self._phase('MUSICIAN_WORKFLOW',{'preset':rep.musician_workflow.get('preset'),'vocal_protected_contexts':len(vocal_keys),'creative_policy':config.creative_policy})

        if config.enable_mix_fx_director and config.enable_fx_intelligence:
            mix_fx_props,rep.mix_fx_director,mix_fx_channels,mix_updates=generate_mix_fx_proposals(mid,contexts,rep.musical_context,rep.intelligence,config)
            mix_fx_arb=arbitrate_controller_proposals(mix_fx_props)
            if not mix_fx_arb.get('pass'):
                raise OptimizationBlocked('MIX_FX_PROPOSAL_ARBITRATION',{'conflicts':mix_fx_arb.get('conflicts',[])[:20]})
            mix_fx_commit=commit_controller_proposals(mid,mix_fx_arb)
            rep.workstation['mix_fx_proposal_arbitration']=mix_fx_arb
            rep.workstation['mix_fx_proposal_commit']=mix_fx_commit
            fx_channels.update(mix_fx_channels)
            fx_event_authorizations.extend(mix_fx_commit.get('mutations',[]))
            rep.mix_fx_director['mutations']=mix_fx_commit.get('changes_committed',0)
            rep.mix_fx_director['event_mutations']=mix_fx_commit.get('mutations',[])
            for row in rep.intelligence:
                key=(int(row.get('track',-1)),int(row.get('channel',0))-1)
                if key in mix_updates:row.update(mix_updates[key])
        else:
            rep.mix_fx_director={'schema':'PA800_MIX_FX_DIRECTOR_V1','enabled':False,'policy':'off','mutations':0,'contexts':[]}
        self._phase('MIX_FX',{'mutations':rep.mix_fx_director.get('mutations',0),'policy':rep.mix_fx_director.get('policy'),'proposal_mode':bool(rep.mix_fx_director.get('proposal_mode',False))})

        profiles={}
        usage={}
        for key,ctx in contexts.items():
            if ctx.identity.conflict:
                p,status=None,ctx.resolution_status or 'CONFLICT_PRESERVE'
            else:p,status=self.registry.resolve_identity(ctx.identity.msb,ctx.identity.lsb,ctx.identity.program,ctx.role)
            ctx.resolution_status=status
            element_used=False
            if p and content_type=='style' and ctx.element:
                p=self.registry.choose_element_profile(p,ctx.element); element_used=bool(p.get('_element_override'))
            if p:
                stability=self.registry.profile_stability(p);p=dict(p);p['_profile_stability']=stability
            semantic_status='DISABLED'
            if p and config.use_factory_velocity_semantics:
                semantic,semantic_status=self.registry.resolve_velocity_semantics(
                    ctx.identity.msb,ctx.identity.lsb,ctx.identity.program,ctx.identity.name,
                    ctx.role,ctx.element if content_type=='style' else None,ctx.cv if content_type=='style' else None)
                if semantic:
                    p=dict(p); p['velocity']=semantic.get('velocity',p.get('velocity',{}))
                    p['_velocity_modes']=semantic.get('modes',[]); p['_velocity_semantics']=semantic_status
            profiles[key]=p
            atom=self.registry.arranger_element_role(ctx.element,ctx.role) if content_type=='style' and ctx.element else None
            atom_summary=None
            if atom:
                atom_summary={k:atom.get(k) for k in ('segments','styles','notes','notes_per_bar_median','onsets_per_bar_median','velocity_p50_median','bar_repeat_similarity_median')}
            usage[key]={'identity_profile':status,'element_profile':element_used,'velocity_semantics':semantic_status,'arranger_evidence':atom_summary}
        for key,ctx in contexts.items():
            rep.contexts.append({'track':ctx.track_index,'channel':ctx.channel+1,'content_type':content_type,'role':ctx.role,'family':ctx.family,'address':ctx.identity.address(),'sound':ctx.identity.name,'element':ctx.element,'cv':ctx.cv,'conflict':ctx.identity.conflict,'evidence_level':evidence_for_context(ctx),'instrument_policy':policy_for(ctx.family)})
            rep.factory_usage.append({'track':ctx.track_index,'channel':ctx.channel+1,'sound':ctx.identity.name,'role':ctx.role,**usage[key]})
        intent_preserve_keys={(int(row['track']),int(row['channel'])-1) for row in rep.instrument_intent.get('track_intents',[]) if row.get('label')=='UNKNOWN' and row.get('evidence_level')=='E0'}
        rep.musical_decision_plan=build_musical_decision_plan(contexts,profiles,rep.instrument_intent,notes=notes,song_map=rep.song_map,phrase_doctor=rep.phrase_doctor,preserve_keys=intent_preserve_keys,user_stage=bool(getattr(config,'apply_baja_stage_profile',False)),ticks_per_beat=mid.ticks_per_beat)
        rep.workstation['pre_apply_mutation_policy']=build_pre_apply_mutation_policy(rep.musical_decision_plan,config)
        rep.workstation['proposal_arbitration']=build_proposal_arbitration(rep.musical_decision_plan,config)
        if not rep.workstation['proposal_arbitration'].get('pass'):
            raise OptimizationBlocked('PROPOSAL_ARBITRATION',rep.workstation['proposal_arbitration'])
        if not rep.workstation['pre_apply_mutation_policy'].get('pass'):
            raise OptimizationBlocked('PRE_APPLY_MUTATION_POLICY',rep.workstation['pre_apply_mutation_policy'])
        quality_before=evidence_quality_snapshot(mid,contexts,profiles)
        self._phase('MUSICAL_DECISION_BRAIN',{'contexts':rep.musical_decision_plan.get('summary',{}).get('contexts',0),'preserve':rep.musical_decision_plan.get('summary',{}).get('preserve',0)})
        self._phase('PROPOSAL_ARBITRATION',{'pass':rep.workstation['proposal_arbitration'].get('pass'),'accepted':rep.workstation['proposal_arbitration'].get('accepted_proposals',0),'rejected':rep.workstation['proposal_arbitration'].get('rejected_proposals',0)})

        rep.workstation['instrument_application']={
            'schema':'PA800_INSTRUMENT_APPLICATION_V1',
            'velocity_authority':'RESOLVED_FACTORY_GOLD_PROFILE_ONLY',
            'neural_authority':'TIMING_GATE_ONLY',
            'contexts':[
                {'track':row['track'],'channel':row['channel'],'sound':row['sound'],'role':row['role'],'family':row['family'],
                 'policy_family':row['instrument_policy'].get('policy_family'),'timing_mode':row['instrument_policy'].get('timing_mode'),
                 'timing_scale':row['instrument_policy'].get('timing_scale'),'gate_mode':row['instrument_policy'].get('gate_mode'),
                 'gate_scale':row['instrument_policy'].get('gate_scale'),'group_mode':row['instrument_policy'].get('group_mode'),
                 'authority_head':row['instrument_policy'].get('authority_head'),'controllers':row['instrument_policy'].get('controllers')}
                for row in rep.contexts
            ]}
        protected_counts=Counter();protected_samples=defaultdict(list)
        for n in notes:
            key=(n.track_index,n.channel);ctx=contexts.get(key);p=profiles.get(key)
            if key in vocal_keys:n.protected,reason=True,'VOCAL_FRIENDLY_FOREGROUND'
            elif key in intent_unknown_keys:n.protected,reason=True,'INTENT_UNKNOWN_PRESERVE'
            else:n.protected,reason=protect_note(n,ctx,p,config,manual_dnc=self.registry.resolve_manual_dnc(ctx.identity.msb,ctx.identity.lsb,ctx.identity.program) if ctx else None)
            if n.protected and reason:
                warning_key=(n.track_index,n.channel,reason);protected_counts[warning_key]+=1
                if len(protected_samples[warning_key])<8:protected_samples[warning_key].append(n.note)
        for (track,channel,reason),count in sorted(protected_counts.items()):
            rep.warnings.append('protected track=%d ch=%d count=%d sample_notes=%s: %s' % (track,channel+1,count,protected_samples[(track,channel,reason)],reason))
        rep.repair_previews=_filter_protected_repair_previews(rep.repair_previews,notes)
        rep.audition_queue=build_audition_queue(rep.intelligence,rep.articulations,rep.repair_previews)
        rep.musician_workflow=build_musician_workflow(config,rep.musical_context,rep.musical_understanding,rep.agent_mesh,rep.song_map,rep.phrase_doctor,rep.repair_previews)
        instrument_baseline=snapshot_instrument_state(mid,notes,contexts)
        performance_checkpoint=copy.deepcopy(mid)
        performance_change_start=len(rep.changes)
        rep.workstation.setdefault('self_healing_recovery',[])
        # R8 transactional proposal pipeline: mature engines run against isolated
        # MIDI copies first. Production MIDI remains untouched until the central
        # event arbiter resolves every velocity/onset/duration proposal.
        velocity_notes=filter_notes_by_proposal(notes,rep.workstation['proposal_arbitration'],'velocity')
        timing_notes=filter_notes_by_proposal(notes,rep.workstation['proposal_arbitration'],'timing')
        gate_notes=filter_notes_by_proposal(notes,rep.workstation['proposal_arbitration'],'gate')
        event_proposals=[];proposal_sources=[]
        velocity_props,velocity_summary=generate_dimension_proposals(mid,velocity_notes,contexts,profiles,self.registry,config,'velocity')
        event_proposals.extend(velocity_props);proposal_sources.append(velocity_summary)
        try:
            timing_props,timing_summary=generate_dimension_proposals(mid,timing_notes,contexts,profiles,self.registry,config,'timing')
            event_proposals.extend(timing_props);proposal_sources.append(timing_summary)
            trained=(timing_summary.get('workstation') or {}).get('trained_rhythm_application')
            if trained:rep.workstation['trained_rhythm_application']=trained
        except Exception as exc:
            autonomous_fallback=bool(getattr(config,'autopilot',False) or getattr(config,'factory_gold_max',False))
            neural_active=bool(getattr(config,'apply_trained_rhythm_model',False))
            if not (autonomous_fallback and neural_active):
                raise
            config.apply_trained_rhythm_model=False;config.trained_rhythm_only=False
            rep.workstation['self_healing_recovery'].append(recovery_record(stage='EVENT_PROPOSAL_GENERATION',reason='neural_inference_failure',action='FACTORY_GOLD_DETERMINISTIC_PROPOSAL_FALLBACK',error=exc,changes_rolled_back=0))
            rep.warnings.append('Neural timing proposal generation failed; deterministic Factory/Gold proposals were regenerated without touching production MIDI.')
            timing_props,timing_summary=generate_dimension_proposals(mid,timing_notes,contexts,profiles,self.registry,config,'timing')
            event_proposals.extend(timing_props);proposal_sources.append(timing_summary)
            rep.workstation['trained_rhythm_application']={'schema':'PA800_TRAINED_MUSIC_APPLICATION_FALLBACK_V2','requested':True,'applied':False,'fallback':'FACTORY_GOLD_DETERMINISTIC_PROPOSALS','authority_granted':False}
        gate_props,gate_summary=generate_dimension_proposals(mid,gate_notes,contexts,profiles,self.registry,config,'gate')
        event_proposals.extend(gate_props);proposal_sources.append(gate_summary)
        rep.workstation['event_proposal_generation']={'schema':'PA800_EVENT_PROPOSAL_GENERATION_V1','sources':proposal_sources,'proposals':len(event_proposals),'production_midi_mutated':False}
        self._phase('EVENT_PROPOSAL_GENERATION',{'proposals':len(event_proposals),'sources':len(proposal_sources),'production_midi_mutated':False})
        rep.workstation['event_proposal_arbitration']=arbitrate_event_proposals(event_proposals,rep.workstation['proposal_arbitration'],rep.musical_decision_plan)
        if not rep.workstation['event_proposal_arbitration'].get('pass'):
            raise OptimizationBlocked('EVENT_PROPOSAL_ARBITRATION',{'conflicts':rep.workstation['event_proposal_arbitration'].get('conflicts',[])[:20]})
        rep.workstation['event_proposal_commit']=commit_event_proposals(mid,rep.workstation['event_proposal_arbitration'],rep)
        self._phase('EVENT_PROPOSAL_COMMIT',{'accepted':rep.workstation['event_proposal_arbitration'].get('accepted_count',0),'rejected':rep.workstation['event_proposal_arbitration'].get('rejected_count',0),'changes_committed':rep.workstation['event_proposal_commit'].get('changes_committed',0)})

        # R9 transactional refinement pipeline. Conductor -> Performance Director
        # -> BAJA stage run in one sandbox preserving their proven legacy order.
        # Production MIDI receives only centrally arbitrated event/controller commits.
        notes=extract_notes(mid);classify_intents(notes,contexts,mid.ticks_per_beat)
        for n in notes:
            key=(n.track_index,n.channel);ctx=contexts.get(key);p=profiles.get(key)
            if key in vocal_keys or key in intent_unknown_keys:n.protected=True
            else:n.protected,_=protect_note(n,ctx,p,config,manual_dnc=self.registry.resolve_manual_dnc(ctx.identity.msb,ctx.identity.lsb,ctx.identity.program) if ctx else None)
        velocity_notes=filter_notes_by_proposal(notes,rep.workstation['proposal_arbitration'],'velocity')
        refiner_velocity,refiner_controllers,refiner_summary=generate_refiner_proposals(
            mid,velocity_notes,contexts,profiles,self.registry,rep.musical_context,config)
        rep.workstation['refiner_proposal_generation']=refiner_summary
        rep.velocity_conductor=refiner_summary.get('velocity_conductor') or {'enabled':False,'contexts':[],'pass':True}
        rep.performance_director=refiner_summary.get('performance_director') or {'enabled':False,'policy':'off','applied_changes':0,'phrases':[],'interactions':[]}
        self._phase('REFINER_PROPOSAL_GENERATION',{'velocity_proposals':len(refiner_velocity),'controller_proposals':len(refiner_controllers),'production_midi_mutated':False})
        rep.workstation['refiner_event_arbitration']=arbitrate_event_proposals(refiner_velocity,rep.workstation['proposal_arbitration'],rep.musical_decision_plan)
        if not rep.workstation['refiner_event_arbitration'].get('pass'):
            raise OptimizationBlocked('REFINER_EVENT_ARBITRATION',{'conflicts':rep.workstation['refiner_event_arbitration'].get('conflicts',[])[:20]})
        rep.workstation['refiner_controller_arbitration']=arbitrate_controller_proposals(refiner_controllers)
        if not rep.workstation['refiner_controller_arbitration'].get('pass'):
            raise OptimizationBlocked('REFINER_CONTROLLER_ARBITRATION',{'conflicts':rep.workstation['refiner_controller_arbitration'].get('conflicts',[])[:20]})
        rep.workstation['refiner_event_commit']=commit_event_proposals(mid,rep.workstation['refiner_event_arbitration'],rep)
        rep.workstation['refiner_controller_commit']=commit_controller_proposals(mid,rep.workstation['refiner_controller_arbitration'])
        expression_event_authorizations=list(rep.workstation['refiner_controller_commit'].get('mutations',[]))
        perc_changes=sum(1 for row in rep.workstation['refiner_event_arbitration'].get('accepted',[]) if str(row.get('final_change_kind'))=='baja_percussion_40pct')
        if getattr(config,'apply_baja_stage_profile',False):
            rep.workstation.setdefault('baja_stage_profile',{})['percussion_40pct_changes']=perc_changes
        self._phase('REFINER_PROPOSAL_COMMIT',{'velocity_changes':rep.workstation['refiner_event_commit'].get('changes_committed',0),'controller_changes':rep.workstation['refiner_controller_commit'].get('changes_committed',0),'baja_percussion_changes':perc_changes})
        notes=extract_notes(mid);classify_intents(notes,contexts,mid.ticks_per_beat)
        budget_props,budget_summary=generate_velocity_budget_proposals(mid,notes,contexts,instrument_baseline)
        budget_arb=arbitrate_event_proposals(budget_props,rep.workstation['proposal_arbitration'],rep.musical_decision_plan)
        if not budget_arb.get('pass'):
            raise OptimizationBlocked('VELOCITY_BUDGET_ARBITRATION',{'conflicts':budget_arb.get('conflicts',[])[:20]})
        budget_commit=commit_event_proposals(mid,budget_arb,rep)
        rep.workstation['velocity_budget_projection']={**budget_summary,'projected_notes':budget_commit.get('changes_committed',0),'arbitration':{'accepted_count':budget_arb.get('accepted_count',0),'rejected_count':budget_arb.get('rejected_count',0)},'commit':budget_commit}
        self._phase('PERFORMANCE_SHAPING',{'changes':len(rep.changes),'velocity_budget_proposals':len(budget_props),'velocity_budget_committed':budget_commit.get('changes_committed',0)})
        final_notes=extract_notes(mid);classify_intents(final_notes,contexts,mid.ticks_per_beat)
        rep.workstation['mutation_budget_audit']=audit_performance_budget(instrument_baseline,final_notes,rep.musical_decision_plan)
        preliminary_quality_after=evidence_quality_snapshot(mid,contexts,profiles)
        preliminary_quality_delta=compare_quality(quality_before,preliminary_quality_after)
        rollback_reason=None
        if not rep.workstation['mutation_budget_audit'].get('pass') and not strict_preserve:
            selective=apply_selective_budget_rollback(mid,instrument_baseline,rep.musical_decision_plan)
            rep.workstation['selective_budget_rollback']=selective
            final_notes=extract_notes(mid);classify_intents(final_notes,contexts,mid.ticks_per_beat)
            rep.changes=reconcile_change_ledger_after_selective_rollback(rep.changes,instrument_baseline,final_notes,selective)
            post_selective=audit_performance_budget(instrument_baseline,final_notes,rep.musical_decision_plan)
            rep.workstation['mutation_budget_audit_after_selective_rollback']=post_selective
            rep.workstation['self_healing_recovery'].append(recovery_record(stage='PERFORMANCE_SHAPING',reason='mutation_budget_exceeded',action='SELECTIVE_EVENT_DIMENSION_ROLLBACK',changes_rolled_back=selective.get('rolled_notes',0)))
            if not post_selective.get('pass'):
                rollback_reason='mutation_budget_exceeded_after_selective_rollback'
        if preliminary_quality_delta.get('regression'):
            rollback_reason='factory_evidence_quality_regression'
        if rollback_reason and not strict_preserve:
            rolled=max(0,len(rep.changes)-performance_change_start)
            mid=performance_checkpoint
            del rep.changes[performance_change_start:]
            expression_event_authorizations=[]
            rep.workstation['self_healing_recovery'].append(recovery_record(stage='PERFORMANCE_SHAPING',reason=rollback_reason,action='FALLBACK_ROLLBACK_TO_PRE_PERFORMANCE_SNAPSHOT',changes_rolled_back=rolled))
            rep.warnings.append('Premium safety rolled back the performance stage after selective recovery could not prove safety: '+rollback_reason)
            rep.velocity_conductor={'schema':'PA800_VELOCITY_CONDUCTOR_ROLLED_BACK_V1','contexts':[],'rolled_back':True,'reason':rollback_reason}
            rep.performance_director={'schema':'PA800_PERFORMANCE_DIRECTOR_ROLLED_BACK_V1','enabled':False,'pass':True,'rolled_back':True,'reason':rollback_reason,'expression_event_mutations':[],'expression_inserts':0}
            final_notes=extract_notes(mid);classify_intents(final_notes,contexts,mid.ticks_per_beat)
            rep.workstation['mutation_budget_audit_after_rollback']=audit_performance_budget(instrument_baseline,final_notes,rep.musical_decision_plan)
        rep.instrument_director=audit_instrument_fingerprints(instrument_baseline,mid,final_notes,contexts)
        rep.factory_usage_meter=build_factory_usage_meter(final_notes,contexts,profiles,self.registry,rep.changes,config)
        rep.change_summary={'total':len(rep.changes),'by_kind':dict(sorted(Counter(change.kind for change in rep.changes).items()))}
        rep.workstation['transaction_coverage']=audit_transaction_coverage(config,rep)
        if not rep.workstation['transaction_coverage'].get('pass'):
            raise OptimizationBlocked('TRANSACTION_COVERAGE',rep.workstation['transaction_coverage'])
        self._phase('TRANSACTION_COVERAGE',{'pass':True,'covered':rep.workstation['transaction_coverage'].get('covered_domains'),'domains':rep.workstation['transaction_coverage'].get('mutation_domains')})

        rep.mutation_arbitration=audit_mutation_arbitration(rep.changes)
        self._phase('MUTATION_ARBITER',{'pass':rep.mutation_arbitration.get('pass'),'stacked_events':rep.mutation_arbitration.get('stacked_events',0),'conflicts':len(rep.mutation_arbitration.get('conflicts',[]))})
        if not rep.mutation_arbitration.get('pass'):
            raise OptimizationBlocked('MUTATION_ARBITER',{'conflicts':rep.mutation_arbitration.get('conflicts',[])[:10],'identity_violations':rep.mutation_arbitration.get('identity_violations',[])[:10]})
        quality_after=evidence_quality_snapshot(mid,contexts,profiles)
        rep.quality_delta=compare_quality(quality_before,quality_after)
        if rep.quality_delta.get('regression'):
            rep.warnings.append('Evidence quality metric regressed by more than 5 points; verifier remains final authority because this metric is not a subjective musical score.')
        self._phase('QUALITY_DELTA',{'velocity_factory_corridor_delta':rep.quality_delta.get('velocity_factory_corridor_delta'),'regression':rep.quality_delta.get('regression')})
        rep.verifier=verify(original,mid,sound_targets,fx_channels,articulation_insertions,rep.changes,fx_event_authorizations,expression_event_authorizations)
        if not rep.verifier.get('pass'):
            failed=[key for key,value in rep.verifier.items() if isinstance(value,bool) and not value]
            raise OptimizationBlocked('VERIFY',{'failed_checks':failed,'note_diff_diagnostics':rep.verifier.get('note_diff_diagnostics'),'authorized_note_changes':rep.verifier.get('authorized_note_changes'),'authorized_fx_events':rep.verifier.get('authorized_fx_events')})
        sound_ledger=[]
        for index,(key,target) in enumerate(sorted(sound_targets.items())):
            sound_ledger.append({'authority_id':'SOUND-%06d'%(index+1),'mutation':'SOUND_ADDRESS','track':key[0],'channel':key[1],'target':list(target)})
        rep.mutation_ledger=sound_ledger+list(rep.verifier.get('mutation_ledger',[]))
        rep.authority_ledger,rep.quality_gate=evaluate_quality_gate(rep,config)
        if not rep.quality_gate.get('pass'):
            instrument=rep.instrument_director or {}
            raise OptimizationBlocked('QUALITY_GATE',{'failed_checks':rep.quality_gate.get('failed_checks',[]),'score_percent':rep.quality_gate.get('score_percent'),'instrument_failed_checks':[key for key,value in instrument.get('checks',{}).items() if not value],'instrument_summary':{key:value for key,value in instrument.items() if key in ('bass','guitar','piano','sustain','organ','expressive_controllers')}})
        self._phase('VERIFY',{'pass':True,'authorized_sound_channels':rep.verifier.get('authorized_sound_channels',0),'authorized_fx_channels':rep.verifier.get('authorized_fx_channels',0)})
        rep.workstation['completed_phases_before_commit']=list(self._completed_phases)
        rep.workstation['runtime_asset_immutability']=asset_guard.assert_unchanged() if asset_guard else {'pass':True,'files':0}
        out=Path(output_path); out.parent.mkdir(parents=True,exist_ok=True)
        tmp=temp_path_for(out,'.tmp.mid'); rtmp=None
        try:
            if strict_preserve:
                shutil.copyfile(input_path,tmp)
            else:
                save_midi(mid,str(tmp))
            persisted=load_midi(str(tmp))
            disk_verify=verify(original,persisted,sound_targets,fx_channels,articulation_insertions,rep.changes,fx_event_authorizations,expression_event_authorizations)
            if not disk_verify.get('pass'):
                failed=[key for key,value in disk_verify.items() if isinstance(value,bool) and not value]
                raise OptimizationBlocked('PERSISTED_VERIFY',{'failed_checks':failed,'note_diff_diagnostics':disk_verify.get('note_diff_diagnostics')})
            rep.verifier=disk_verify;rep.mutation_ledger=sound_ledger+list(disk_verify.get('mutation_ledger',[]))
            rep.authority_ledger,rep.quality_gate=evaluate_quality_gate(rep,config)
            if not rep.quality_gate.get('pass'):
                raise OptimizationBlocked('PERSISTED_QUALITY_GATE',{'failed_checks':rep.quality_gate.get('failed_checks',[]),'score_percent':rep.quality_gate.get('score_percent')})
            pairs=[(tmp,out)]
            self._phase('COMMIT',{'output':str(out),'report':str(report_path) if report_path else None})
            rep.workstation['completed_phases']=list(self._completed_phases)
            if report_path:
                rp=Path(report_path);rtmp=temp_path_for(rp,'.tmp.json')
                payload=asdict(rep);max_details=2000
                if len(payload['changes'])>max_details:
                    payload['changes']=payload['changes'][:max_details]
                    payload['change_summary']['details_recorded']=max_details;payload['change_summary']['details_truncated']=rep.change_summary['total']-max_details
                with rtmp.open('w',encoding='utf-8') as f:json.dump(payload,f,indent=2,ensure_ascii=False)
                pairs.append((rtmp,rp))
            commit_artifacts(pairs)
        finally:
            for p in (tmp,rtmp):
                if p:
                    try:Path(p).unlink()
                    except FileNotFoundError:pass
        rep.workstation['ai_resource_brain']['gc_collected_after_file']=resource_brain.collect_if_needed(brain_decision)
        return rep
