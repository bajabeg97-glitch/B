from types import SimpleNamespace

from pa800_optimizer.neural.pattern_advisor import analyze_pattern_advisor, validate_pattern_advisor


def _context(family, role):
    return SimpleNamespace(identity=SimpleNamespace(org_family=family, role=role), role=role)


def _note(track, channel, pitch, onset):
    return SimpleNamespace(track_index=track, channel=channel, note=pitch, onset=onset)


def test_pattern_advisor_covers_requested_heads_without_velocity_or_mutations():
    contexts={(0,9):_context('DRUM_KIT','FILL'),(1,0):_context('BASS','BASS'),
              (2,1):_context('GUITAR','ACC2'),(3,2):_context('BRASS','ACC3'),
              (4,3):_context('SYNTH_PAD','ACC4'),(5,4):_context('REED','SOLO')}
    notes=[_note(track,channel,60+track,index*48) for track,channel in contexts for index in range(4)]
    report=analyze_pattern_advisor(notes,contexts,'style')
    heads={row['head'] for row in report['candidates']}
    expected={'FILL_STRUCTURE','FILL_CONTENT','DRUM_PATTERN','BASS_PATTERN','GUITAR_MODE',
              'GUITAR_STRUM','POWERCHORD_VOICING','POWERCHORD_RIFF','BRASS_PATTERN',
              'STRINGS_PAD_PATTERN','SOLO_PHRASE','EXPRESSION_CC11','ORNAMENT'}
    assert expected <= heads
    assert validate_pattern_advisor(report)['pass'] is True
    assert report['mutations']==0 and report['authority_granted'] is False
