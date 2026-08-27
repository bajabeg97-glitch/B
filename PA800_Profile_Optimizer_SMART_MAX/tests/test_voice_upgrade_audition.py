import csv,json
import mido
from tools.voice_upgrade_audition import generate


def test_voice_upgrade_audition_contains_only_same_program_pairs(tmp_path):
    output=generate(tmp_path/'voice')
    manifest=json.loads((output/'VOICE_UPGRADE_MANIFEST.json').read_text(encoding='utf-8'))
    rows=list(csv.DictReader((output/'VOICE_UPGRADE_SCORE.csv').open(encoding='utf-8-sig')))
    assert rows and len(rows)==len(manifest['pairs'])
    for row in rows:
        assert row['source_address'].split('.')[-1]==row['target_address'].split('.')[-1]
    for path in (output/'MIDI').glob('*.mid'):
        assert len(mido.MidiFile(str(path)).tracks)==1