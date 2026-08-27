from tools.corrupt_midi_corpus import generate


def test_eighty_golden_mid_kar_containers_are_deterministically_rejected(tmp_path):
    rows=generate(tmp_path/'corrupt')
    assert len(rows)==80 and len({row['name'] for row in rows})==80
    assert sum(row['file'].endswith('.kar') for row in rows)==10
    assert all(not row['pass'] and row['errors'] for row in rows)