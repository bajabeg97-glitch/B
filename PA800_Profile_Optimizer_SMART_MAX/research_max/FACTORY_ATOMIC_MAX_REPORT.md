# PA800 Factory Styles — ATOMIC MAX forensic analysis (NO DNA)
## Scope
- Styles: **252**
- Valid Note-On atoms: **1,430,602**
- Context/sound-state segments: **31,070**
- Unit of analysis: `Style → Element → CV → role → exact Sound state → bar/beat/subdivision → onset group → note atom`.
Factory proves observed arranger behavior; it does not by itself name internal RX/DNC oscillator semantics. Manual DNC addresses observed in this Factory corpus: **0**.
## Element anatomy
- **Variation 1**: notes=149,169, median bars=4.0, active-role median=5.0, notes/bar median=7.75, onset/bar median=5.0.
- **Variation 2**: notes=150,605, median bars=4.0, active-role median=6.0, notes/bar median=7.0, onset/bar median=4.625.
- **Variation 3**: notes=192,788, median bars=4.0, active-role median=7.0, notes/bar median=8.0, onset/bar median=5.125.
- **Variation 4**: notes=252,169, median bars=8.0, active-role median=7.0, notes/bar median=8.5, onset/bar median=6.0.
- **Intro 1**: notes=205,415, median bars=6.0, active-role median=7.0, notes/bar median=6.8, onset/bar median=4.8.
- **Intro 2**: notes=55,959, median bars=4.0, active-role median=6.0, notes/bar median=7.0, onset/bar median=4.75.
- **Intro 3**: notes=5,319, median bars=1.0, active-role median=2.0, notes/bar median=8.0, onset/bar median=7.0.
- **Fill 1**: notes=27,164, median bars=1.0, active-role median=6.0, notes/bar median=10.0, onset/bar median=6.5.
- **Fill 2**: notes=35,378, median bars=1.0, active-role median=7.0, notes/bar median=11.0, onset/bar median=7.0.
- **Break**: notes=12,850, median bars=1.0, active-role median=5.5, notes/bar median=4.0, onset/bar median=3.0.
- **Ending 1**: notes=236,075, median bars=5.0, active-role median=8.0, notes/bar median=8.4, onset/bar median=5.42857.
- **Ending 2**: notes=74,444, median bars=3.0, active-role median=7.0, notes/bar median=7.5, onset/bar median=5.0.
- **Ending 3**: notes=33,267, median bars=2.0, active-role median=7.0, notes/bar median=7.0, onset/bar median=5.0.

## Variation progression — strongest structural finding
The corpus does **not** primarily build V1→V4 by simply raising velocity. The dominant growth mechanism is orchestration/density: more ACC/Perc roles become active, and V3/V4 more often add note/onset detail while many existing role rhythm masks remain highly similar. This supports a layered arranger model: preserve the skeleton, add layers/detail by higher Variations.
- V1->V2|DRUM: rhythm Jaccard median=1.0, exact-mask fraction=0.53957, same-Sound fraction=0.96403; Δnotes/bar median=0.25.
- V2->V3|DRUM: rhythm Jaccard median=0.9, exact-mask fraction=0.44369, same-Sound fraction=0.96847; Δnotes/bar median=0.5.
- V3->V4|DRUM: rhythm Jaccard median=0.90909, exact-mask fraction=0.44902, same-Sound fraction=0.95662; Δnotes/bar median=1.0.
- V1->V2|BASS: rhythm Jaccard median=1.0, exact-mask fraction=0.56057, same-Sound fraction=0.96675; Δnotes/bar median=0.0.
- V2->V3|BASS: rhythm Jaccard median=0.8, exact-mask fraction=0.39189, same-Sound fraction=0.97973; Δnotes/bar median=0.0.
- V3->V4|BASS: rhythm Jaccard median=0.83333, exact-mask fraction=0.42232, same-Sound fraction=0.96718; Δnotes/bar median=0.0.
- V1->V2|ACC1: rhythm Jaccard median=1.0, exact-mask fraction=0.51734, same-Sound fraction=0.9104; Δnotes/bar median=0.0.
- V2->V3|ACC1: rhythm Jaccard median=0.69231, exact-mask fraction=0.33835, same-Sound fraction=0.90727; Δnotes/bar median=0.0.
- V3->V4|ACC1: rhythm Jaccard median=0.6875, exact-mask fraction=0.39048, same-Sound fraction=0.87381; Δnotes/bar median=0.0.
- V3->V4|PERC: rhythm Jaccard median=0.92857, exact-mask fraction=0.48139, same-Sound fraction=0.99256; Δnotes/bar median=2.0.
- V1->V2|PERC: rhythm Jaccard median=1.0, exact-mask fraction=0.62376, same-Sound fraction=0.9901; Δnotes/bar median=0.0.
- V2->V3|PERC: rhythm Jaccard median=0.88889, exact-mask fraction=0.45739, same-Sound fraction=0.99432; Δnotes/bar median=0.875.
- V1->V2|ACC2: rhythm Jaccard median=1.0, exact-mask fraction=0.50633, same-Sound fraction=0.91139; Δnotes/bar median=0.0.
- V2->V3|ACC2: rhythm Jaccard median=0.76697, exact-mask fraction=0.41622, same-Sound fraction=0.95676; Δnotes/bar median=0.0.
- V3->V4|ACC2: rhythm Jaccard median=0.83333, exact-mask fraction=0.4213, same-Sound fraction=0.90741; Δnotes/bar median=0.0.

## CV logic
CVs must remain separate. `CV1` is the best-supported reference, but CV2–CV6 can preserve a rhythm skeleton while changing pitch/register/Sound or can be genuinely specialized. The CSV `factory_cv_contrast_max.csv` records rhythm Jaccard, density ratio, velocity delta, register delta and Sound identity equality for every supported CV1↔CVn pair.

## Playing-technique candidate layer
The analysis now measures, without claiming undocumented semantics: ghost/secondary-hit candidates, accent candidates, staccato, legato/overlap, tenuto, short/dead/mute candidates, near-onset guitar strums and direction, repeated-note runs, trill/tremolo/grace candidates, special-pitch/RX candidates, exact chord groups and phrase/bar contours. These are candidates derived from MIDI context; manual/hardware remains the authority for an RX/DNC articulation name.

## Noise / special pitch logic
- Exact Sound profiles with observed special-pitch activity in this pass: **176**.
- For each one, special notes are separated from the primary musical range and classified by timing relation: BEFORE_NORMAL / AFTER_NORMAL / ISOLATED, plus velocity and duration distributions. This is the required basis for fret/release/pick/noise hypotheses without deleting out-of-range RX events.

## Controllers and performance events
- cc:0: 31,217
- cc:1: 18,551
- cc:10: 1
- cc:100: 99
- cc:101: 13
- cc:103: 70
- cc:104: 1
- cc:105: 5
- cc:106: 1
- cc:108: 3
- cc:11: 31,223
- cc:110: 60
- cc:111: 10
- cc:114: 26
- cc:115: 36
- cc:116: 33
- cc:117: 2
- cc:119: 1
- cc:121: 42
- cc:127: 4
- cc:13: 2
- cc:14: 1
- cc:17: 1
- cc:18: 1
- cc:19: 42
- cc:2: 4
- cc:20: 1
- cc:22: 125,493
- cc:3: 5
- cc:30: 1
- cc:31: 3,276
- cc:32: 31,351
- cc:38: 1
- cc:4: 8
- cc:49: 1
- cc:5: 16
- cc:51: 1
- cc:6: 58
- cc:64: 5,792
- cc:66: 72
- cc:67: 178
- cc:69: 4
- cc:7: 31,231
- cc:71: 6
- cc:72: 1
- cc:78: 1
- cc:8: 154
- cc:80: 9
- cc:86: 1
- cc:87: 1
- cc:88: 1
- cc:90: 2
- cc:97: 21
- pb: 52,542
NRPN/RPN sequences, PB sign/range/reset behavior, CC value distributions, CC1/CC2/CC64/CC80/CC81 threshold populations, aftertouch and SysEx inventories are stored in the MAX controller artifacts.

## What the optimizer can now use
1. Exact per-note Element/CV/Sound state.
2. 1–127 velocity histogram + modes/valleys + context.
3. 8th/16th/32nd and triplet grid residuals + 24-phase groove histogram.
4. Gate/overlap/staccato/tenuto distributions.
5. Variation and CV structural relationships.
6. Per-role density, polyphony, register and phrase contour.
7. Drum/Perc ghost/accent candidates and per-key profiles.
8. Guitar strum candidates and spread/direction/velocity slope.
9. Special/RX pitch timing relationships.
10. Cross-role timing lock (Drum↔Bass, Drum↔Perc, Bass↔ACC).
11. Pattern fingerprints to identify reused Factory skeletons.
12. Controller/NRPN/PB/AT state evidence.

## Hard limits / NOT OBSERVABLE from this Factory SMF alone
- Exact internal oscillator selected by Cycle/Random.
- Exact per-Sound RX/DNC semantic name when the manual/Sound Edit does not expose the mapping.
- NTT/Trigger Mode/Tension parameter value when it is not serialized in this export.
- Actual audible timbre/sample result without Pa800 playback/audio capture.
These remain protected/unknown instead of guessed.
