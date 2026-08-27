"""Evidence-safe Factory/Gold corpus inventory and feature authority routing."""
from __future__ import annotations

import hashlib
import json
import zipfile
from pathlib import Path, PurePosixPath

SCHEMA = 'PA800_FACTORY_GOLD_CORPUS_V1'
MIDI_SUFFIXES = {'.mid', '.midi', '.kar'}

# Factory is the PA800 arranger grammar/safety authority. Gold supplies Balkan
# performance evidence. Velocity is deliberately outside every neural route.
ROUTES = {
    'FILL_STRUCTURE': {'factory': .70, 'gold': .30, 'mode': 'FACTORY_PRIOR'},
    'FILL_CONTENT': {'factory': .35, 'gold': .65, 'mode': 'BLENDED_CANDIDATE'},
    'GUITAR_MODE': {'factory': .90, 'gold': .10, 'mode': 'FACTORY_VETO'},
    'GUITAR_STRUM': {'factory': .45, 'gold': .55, 'mode': 'BLENDED_CANDIDATE'},
    'POWERCHORD_VOICING': {'factory': .75, 'gold': .25, 'mode': 'FACTORY_VETO'},
    'POWERCHORD_RIFF': {'factory': .30, 'gold': .70, 'mode': 'BLENDED_CANDIDATE'},
    'BRASS_PATTERN': {'factory': .60, 'gold': .40, 'mode': 'FACTORY_PRIOR'},
    'STRINGS_PAD_PATTERN': {'factory': .75, 'gold': .25, 'mode': 'FACTORY_PRIOR'},
    'DRUM_PATTERN': {'factory': .25, 'gold': .75, 'mode': 'GOLD_PERFORMANCE'},
    'BASS_PATTERN': {'factory': .30, 'gold': .70, 'mode': 'GOLD_PERFORMANCE'},
    'SOLO_PHRASE': {'factory': .15, 'gold': .85, 'mode': 'GOLD_PERFORMANCE'},
    'EXPRESSION_CC11': {'factory': .35, 'gold': .65, 'mode': 'REVIEW_CANDIDATE'},
    'ORNAMENT': {'factory': .15, 'gold': .85, 'mode': 'REVIEW_CANDIDATE'},
    'VELOCITY': {'factory': 0.0, 'gold': 0.0, 'mode': 'PROFILE_ONLY'},
}


def _sha256(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''): h.update(block)
    return h.hexdigest()


def _archive(path, kind):
    path = Path(path)
    rows = []
    with zipfile.ZipFile(path) as archive:
        for info in archive.infolist():
            suffix = PurePosixPath(info.filename).suffix.lower()
            if info.is_dir() or suffix not in MIDI_SUFFIXES: continue
            rows.append({'member': info.filename, 'bytes': info.file_size,
                         'crc32': '%08x' % info.CRC, 'corpus': kind})
    return {'kind': kind, 'archive': path.name, 'sha256': _sha256(path),
            'midi_files': len(rows), 'members': rows}


def build_corpus_manifest(factory_zip, gold_zip):
    corpora = [_archive(factory_zip, 'FACTORY'), _archive(gold_zip, 'GOLD')]
    payload = {'schema': SCHEMA, 'corpora': corpora, 'authority_routes': ROUTES,
               'velocity_neural_input': False, 'velocity_neural_output': False,
               'neural_mutation_authority': False,
               'policy': 'analyze_and_rank_only; deterministic engines apply; verifier proves'}
    canonical = json.dumps(payload, sort_keys=True, separators=(',', ':')).encode()
    payload['manifest_digest'] = hashlib.sha256(canonical).hexdigest()
    return payload


def route_authority(feature):
    key = str(feature).strip().upper()
    if key not in ROUTES: return {'feature': key, 'status': 'NO_EVIDENCE_NO_CHANGE'}
    return {'feature': key, 'status': 'ROUTED', **ROUTES[key],
            'neural_mutation_authority': False}


def validate_corpus_manifest(manifest):
    errors = []
    if manifest.get('schema') != SCHEMA: errors.append('schema')
    counts = {row.get('kind'): row.get('midi_files') for row in manifest.get('corpora', [])}
    if counts.get('FACTORY') != 252: errors.append('factory_count')
    if counts.get('GOLD') != 182: errors.append('gold_count')
    if manifest.get('velocity_neural_input') is not False: errors.append('velocity_input')
    if manifest.get('velocity_neural_output') is not False: errors.append('velocity_output')
    if (manifest.get('authority_routes') or {}).get('VELOCITY', {}).get('mode') != 'PROFILE_ONLY': errors.append('velocity_route')
    if manifest.get('neural_mutation_authority') is not False: errors.append('mutation_authority')
    return {'schema': 'PA800_FACTORY_GOLD_CORPUS_AUDIT_V1', 'pass': not errors,
            'errors': errors, 'counts': counts}
