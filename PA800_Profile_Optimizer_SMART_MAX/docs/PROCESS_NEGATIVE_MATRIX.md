# Process negative/recovery matrix

This matrix complements the end-to-end MIDI fixtures. It proves that each
critical process refuses unsafe input or restores the previous state after a
failure; happy-path success alone is not accepted as coverage.

| Process | Negative/recovery proof |
|---|---|
| Central authority | Conflict, Preserve, insufficient E3 and never-AUTO Insert/Master decisions are rejected with the expected reason. |
| Canonical verifier | Unlisted controllers, stale note authority, Bank/Program reordering and incomplete articulation pulses fail. |
| Style import contract | Every marker needs its own time signature; unsupported CC data prevents strict export. |
| Hardware campaign | UNKNOWN DNC, duplicate addresses and a false-positive rate above the exclusive limit cannot grant E3. |
| Output lock | A foreign-host lock is preserved; malformed local stale state is recovered. |
| Atomic commit | Failure while backing up the second artifact restores the first target and removes temporary files. |
| Rare families | Unstable and family-aggregate evidence cannot satisfy exact-only mutation authority. |
| Instrument guards | Sustained tails and expressive controller protection remain scoped to the correct track/channel. |

The executable source of truth is `tests/test_process_negative_matrix.py`.
All cases are deterministic and use the built-in test MIDI backend; the real
Mido/Windows and physical Pa800 campaigns remain separate external gates.