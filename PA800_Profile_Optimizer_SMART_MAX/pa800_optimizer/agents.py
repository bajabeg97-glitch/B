"""Deterministic, provider-neutral Premium agent mesh.

The Codex and ChatGPT roles below are local policy adapters in this release.
They never call an external service, access source files, or mutate MIDI.  A
future opt-in provider adapter must still produce this exact fail-closed
contract before its output can be displayed to the user.
"""
from __future__ import annotations

import hashlib
import json


_SCHEMA = 'PA800_AGENT_MESH_V1'
_PROPOSAL_SCHEMA = 'PA800_AGENT_PROPOSAL_V1'
_AGENT_SPECS = (
    {
        'agent_id': 'codex_song_auditor',
        'provider': 'codex',
        'role': 'AUDIT',
        'capabilities': ['ANALYZE', 'SUGGEST', 'PRESERVE'],
        'mutation_capabilities': [],
    },
    {
        'agent_id': 'chatgpt_musical_critic',
        'provider': 'chatgpt',
        'role': 'MUSICAL_CRITIC',
        'capabilities': ['ANALYZE', 'SUGGEST', 'PRESERVE'],
        'mutation_capabilities': [],
    },
)
_ALLOWED_ACTIONS = {'SUGGEST', 'PRESERVE'}


def _digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode('utf-8')).hexdigest()


def _safe_summary(musical_context, understanding, narrative, family_intent, instrument_intent, song_map=None, phrase_doctor=None):
    return {
        'context': musical_context.get('summary', {}),
        'understanding': {
            'observations': len(understanding.get('observations', [])),
            'uncertainties': len(understanding.get('uncertainties', [])),
        },
        'narrative': narrative.get('summary', {}),
        'family': family_intent.get('summary', {}),
        'instrument': instrument_intent.get('summary', {}),
        'song_map': (song_map or {}).get('summary', {}),
        'phrase_doctor': (phrase_doctor or {}).get('summary', {}),
    }


def _proposal(spec, source_digest, findings, requested_action):
    payload = {
        'schema': _PROPOSAL_SCHEMA,
        'agent_id': spec['agent_id'],
        'provider': spec['provider'],
        'role': spec['role'],
        'execution': 'LOCAL_POLICY_ADAPTER',
        'source_contract_digest': source_digest,
        'scope': {'kind': 'song', 'section_index': None, 'track': None, 'channel': None},
        'findings': findings,
        'requested_action': requested_action,
        'allowed_mutation_classes': [],
        'mutations': 0,
        'authority_granted': False,
    }
    return {'proposal_id': _digest(payload)[:24], **payload}


def _run_agent_mesh(config, musical_context, understanding, narrative, family_intent, instrument_intent, song_map=None, phrase_doctor=None):
    """Return deterministic Codex/ChatGPT reviews with no mutation authority."""
    summary = _safe_summary(musical_context, understanding, narrative, family_intent, instrument_intent, song_map, phrase_doctor)
    source_digest = _digest(summary)
    unknown_tracks = int(summary['instrument'].get('unknown_tracks', 0) or 0)
    protected_rows = int(summary['family'].get('protected_rows', 0) or 0)
    sections = int(summary['narrative'].get('sections', summary['context'].get('sections', 0)) or 0)
    codex_findings = []
    if unknown_tracks or protected_rows:
        codex_findings.append({
            'kind': 'PRESERVE', 'severity': 'warning',
            'reason': 'Unknown or protected musical evidence is present; retain the original events.',
            'evidence_refs': ['song:instrument_intent', 'song:family_intent'],
            'confidence': 1.0, 'uncertainty': 0.0, 'protected_dependencies': ['PA800_RX_DNC_PRESERVE'],
        })
        codex_action = 'PRESERVE'
    else:
        codex_findings.append({
            'kind': 'AUDIT_READY', 'severity': 'info',
            'reason': 'No agent-visible protected or unknown-track conflict requires a whole-song preserve decision.',
            'evidence_refs': ['song:instrument_intent'],
            'confidence': 0.75, 'uncertainty': 0.25, 'protected_dependencies': [],
        })
        codex_action = 'SUGGEST'
    chatgpt_findings = [{
        'kind': 'MUSICAL_REVIEW', 'severity': 'info',
        'reason': 'Review the mapped phrases and section dynamics before accepting any Repair, Natural, or Expressive preview.',
        'evidence_refs': ['song:song_map', 'song:section_narrative'],
        'confidence': 0.6 if sections else 0.4,
        'uncertainty': 0.4 if sections else 0.6,
        'protected_dependencies': [],
    }]
    proposals = [_proposal(_AGENT_SPECS[0], source_digest, codex_findings, codex_action), _proposal(_AGENT_SPECS[1], source_digest, chatgpt_findings, 'SUGGEST')]
    consensus = 'PRESERVE' if any(row['requested_action'] == 'PRESERVE' for row in proposals) else 'SUGGEST'
    payload = {
        'schema': _SCHEMA,
        'agents': [dict(row) for row in _AGENT_SPECS],
        'source_contract_digest': source_digest,
        'proposals': proposals,
        'consensus': consensus,
        'applied_actions': 0,
        'mutations': 0,
        'authority_granted': False,
    }
    return {**payload, 'mesh_digest': _digest(payload)}


def _valid_agent_mesh(mesh):
    if not isinstance(mesh, dict) or mesh.get('schema') != _SCHEMA:
        return False
    if mesh.get('authority_granted') is not False or int(mesh.get('mutations', -1)) != 0 or int(mesh.get('applied_actions', -1)) != 0:
        return False
    proposals = mesh.get('proposals') or []
    if {row.get('agent_id') for row in proposals} != {row['agent_id'] for row in _AGENT_SPECS}:
        return False
    for row in proposals:
        if row.get('schema') != _PROPOSAL_SCHEMA or row.get('requested_action') not in _ALLOWED_ACTIONS:
            return False
        if row.get('authority_granted') is not False or int(row.get('mutations', -1)) != 0 or row.get('allowed_mutation_classes') != []:
            return False
        for finding in row.get('findings') or []:
            confidence = float(finding.get('confidence', -1)); uncertainty = float(finding.get('uncertainty', -1))
            if not 0 <= confidence <= 1 or not 0 <= uncertainty <= 1 or abs(confidence + uncertainty - 1.0) > 1e-9:
                return False
    payload = {key: value for key, value in mesh.items() if key != 'mesh_digest'}
    return mesh.get('mesh_digest') == _digest(payload)