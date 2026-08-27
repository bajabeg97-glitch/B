import csv
import json

import mido

from tools.articulation_audition import generate


def test_audition_generator_covers_all_manual_dnc_sounds(tmp_path):
    output=generate(tmp_path/'audition')
    manifest=json.loads((output/'ARTICULATION_AUDITION_MANIFEST.json').read_text(encoding='utf-8'))
    files=list((output/'MIDI').glob('*.mid'))
    rows=list(csv.DictReader((output/'ARTICULATION_AUDITION_SCORE.csv').open(encoding='utf-8-sig')))
    assert len(manifest['sounds'])==23 and len(files)==23
    assert len(rows)>23
    assert {'BASE','SC1_CC80','SC2_CC81'}<=set(row['variant'] for row in rows)
    for path in files:
        mid=mido.MidiFile(str(path));assert len(mid.tracks)==1