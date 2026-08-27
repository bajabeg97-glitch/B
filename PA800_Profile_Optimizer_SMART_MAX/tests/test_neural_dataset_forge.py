import copy
from pathlib import Path
from pa800_optimizer.neural.dataset_forge import CORRUPTION_TYPES,audit_dataset_manifest,balanced_group_splits,forge_dataset
from tests.test_neural_event_contract import _midi

def test_dataset_v2_covers_all_corruptions_and_preserves_sources(tmp_path):
    source=_midi(tmp_path/'source.mid');before=source.read_bytes();manifest=forge_dataset([source],tmp_path/'dataset','TEST_LICENSE','UNIT_TEST','CERTIFICATION');audit=audit_dataset_manifest(manifest)
    assert audit['pass'] and set(manifest['summary']['corruption_types'])==set(CORRUPTION_TYPES)
    assert source.read_bytes()==before and manifest['mutations_to_original_sources']==0 and manifest['authority_granted'] is False
    assert all(row['change_mask'] and not(set(row['changed_note_keys'])&set(row['protected_note_keys'])) for row in manifest['cases'])

def test_protected_only_source_becomes_hard_negative_not_corruption(tmp_path):
    source=_midi(tmp_path/'pedal.mid',controller=True);manifest=forge_dataset([source],tmp_path/'dataset','TEST_LICENSE','UNIT_TEST','CERTIFICATION')
    assert manifest['summary']['cases']==0 and manifest['summary']['protected_only_sources']==1
    assert manifest['summary']['hard_negatives']==12 and all(row['expected_action']=='PRESERVE' for row in manifest['hard_negatives'])

def test_training_requires_license_and_provenance(tmp_path):
    source=_midi(tmp_path/'source.mid');manifest=forge_dataset([source],tmp_path/'dataset',dataset_use='TRAINING');audit=audit_dataset_manifest(manifest);assert not audit['pass'] and 'missing_training_provenance' in audit['errors']

def test_audit_rejects_group_leakage_and_protected_change(tmp_path):
    source=_midi(tmp_path/'source.mid');manifest=forge_dataset([source],tmp_path/'dataset','TEST_LICENSE','UNIT_TEST','CERTIFICATION');bad=copy.deepcopy(manifest);bad['cases'][0]['split']='validation' if bad['cases'][1]['split']!='validation' else 'test';bad['cases'][0]['protected_note_keys']=[bad['cases'][0]['changed_note_keys'][0]];audit=audit_dataset_manifest(bad)
    assert not audit['pass'] and 'source_group_split_leakage' in audit['errors'] and any(error.startswith('protected_note_changed') for error in audit['errors'])

def test_byte_duplicate_source_is_rejected_once(tmp_path):
    one=_midi(tmp_path/'one.mid');two=tmp_path/'two.mid';two.write_bytes(one.read_bytes());manifest=forge_dataset([one,two],tmp_path/'dataset','TEST_LICENSE','UNIT_TEST','CERTIFICATION');assert manifest['summary']['unique_sources']==1 and manifest['summary']['duplicates_rejected']==1

def test_balanced_group_split_is_deterministic_and_non_empty():
    groups=['group-%02d'%index for index in range(12)];one=balanced_group_splits(groups);two=balanced_group_splits(reversed(groups));assert one==two and set(one.values())=={'train','validation','test'}