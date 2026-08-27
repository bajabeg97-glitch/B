# AUTONOMOUS PREMIUM R12 CHECKPOINT

## Structural Proposal Arbiter

R12 moves structural MIDI mutations behind proposal/arbitration/commit boundaries.

### Atomic Sound Address transaction
- Generic Sound/Kit selector and explicit BAJA stage defaults execute on a sandbox copy.
- Production MIDI is unchanged during recommendation/application planning.
- The sandbox diff is converted into one atomic `(Bank MSB, Bank LSB, Program Change)` proposal per track/channel.
- No new Bank Select or Program Change events are invented.
- Multiple Program Change contexts remain blocked as ambiguous.
- Repeated existing Bank Select setup events are rewritten consistently as one voice-address transaction.
- The final target must agree with the authorized sound ledger.
- Commit is all-or-nothing at the voice-address level.

### Structural articulation insertion transaction
- Articulation Director executes on a sandbox copy.
- DNC trigger insertions become structural insert proposals rather than direct production mutations.
- Only complete controller pulse pairs `{127, 0}` are accepted.
- Supported inserted trigger controls remain CC80/CC81.
- Each pulse pair is bound to stable note identity `(track, channel, note, occurrence, onset)`.
- Commit rebuilds delta-time ordering from absolute events.
- Verifier-compatible authorized insertion rows are generated only after commit.

### Runtime phases
- `STRUCTURAL_SOUND_COMMIT`
- `STRUCTURAL_ARTICULATION_COMMIT`

The report phase contract also now includes the existing R9 refiner phases that were already emitted at runtime.

## Validation
- Structural/Sound/Articulation/Optimizer focused block: 37 PASS / 0 FAIL.
- BAJA Stage/Verifier/Factory-Gold/RX/Neural/Workstation safety block: 47 PASS / 0 FAIL.
- Total completed R12 blocks: 84 PASS / 0 FAIL (disjoint selected test files).
- Public API inventory: 116 modules / 387 public functions / 0 unclassified.

## Remaining structural direct-mutation work
Legacy existing-FX direct mode (`apply_existing_fx_sends` when Mix FX Director is disabled), MIDI Doctor repair operations, and any future insertion/deletion features remain separate mutation classes and should not be silently generalized into the structural arbiter without dedicated ordering contracts.

This is a software checkpoint, not physical Pa800 hardware certification.
