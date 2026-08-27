# PA800 Factory Styles — FULL ATOMIC MAX Analysis

## 1. Corpus integrity and scope

- **252/252** Factory Style MIDI files analyzed.
- **1,430,602 valid Note-On atoms** retained.
- **31,070 exact context/sound-state segments** identified.
- Analysis unit: `Style → Style Element → CV → role → exact Sound state → bar → beat → subdivision → onset group → note atom`.
- The tolerant parser keeps valid data from malformed exports and quarantines invalid channel events instead of clipping them into fake MIDI values.
- Exact manual DNC addresses observed in this Factory corpus: **0**. Therefore Factory calibrates arranger/performance behavior, while exact DNC Sound behavior remains manual-driven.

## 2. Element anatomy

| Element | Notes | Median bars | Median active roles | Median notes/bar | Median onsets/bar | Median bar-repeat |
|---|---:|---:|---:|---:|---:|---:|
| Variation 1 | 149,169 | 4.0 | 5.0 | 7.75 | 5.0 | 0.83333 |
| Variation 2 | 150,605 | 4.0 | 6.0 | 7.0 | 4.625 | 0.8 |
| Variation 3 | 192,788 | 4.0 | 7.0 | 8.0 | 5.125 | 0.79654 |
| Variation 4 | 252,169 | 8.0 | 7.0 | 8.5 | 6.0 | 0.77551 |
| Intro 1 | 205,415 | 6.0 | 7.0 | 6.8 | 4.8 | 0.5968 |
| Intro 2 | 55,959 | 4.0 | 6.0 | 7.0 | 4.75 | 0.59615 |
| Intro 3 | 5,319 | 1.0 | 2.0 | 8.0 | 7.0 | 0.5 |
| Fill 1 | 27,164 | 1.0 | 6.0 | 10.0 | 6.5 | 0.14286 |
| Fill 2 | 35,378 | 1.0 | 7.0 | 11.0 | 7.0 | 0.5 |
| Break | 12,850 | 1.0 | 5.5 | 4.0 | 3.0 | 0.0 |
| Ending 1 | 236,075 | 5.0 | 8.0 | 8.4 | 5.42857 | 0.52392 |
| Ending 2 | 74,444 | 3.0 | 7.0 | 7.5 | 5.0 | 0.44444 |
| Ending 3 | 33,267 | 2.0 | 7.0 | 7.0 | 5.0 | 0.11111 |

**Observed arranger architecture:** Variations are mostly 4 or 8 bars, Fills are overwhelmingly 1 bar, Break is overwhelmingly 1 bar and sparse, Intro 1 is much longer (median ~6 bars), Ending 1 ~5 bars, while Intro 3 is usually 1 bar and Ending 3 ~2 bars. Fill 1/2 are denser than Variations; Break is intentionally sparse.

## 3. The strongest V1→V4 finding: orchestration grows before velocity

Factory does **not** mainly create stronger Variations by pushing every note louder. Median velocity change across V1→V2, V2→V3 and V3→V4 is generally **0**. The dominant mechanisms are adding roles/layers and increasing note/onset density.

| Variation | DRUM | PERC | BASS | ACC1 | ACC2 | ACC3 | ACC4 | ACC5 | Median active roles |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Variation 1 | 0.951 | 0.696 | 0.966 | 0.787 | 0.764 | 0.513 | 0.249 | 0.140 | 5.0 |
| Variation 2 | 0.970 | 0.794 | 0.972 | 0.909 | 0.819 | 0.757 | 0.453 | 0.283 | 6.0 |
| Variation 3 | 0.984 | 0.864 | 0.975 | 0.920 | 0.926 | 0.912 | 0.622 | 0.439 | 7.0 |
| Variation 4 | 0.976 | 0.902 | 0.970 | 0.926 | 0.952 | 0.934 | 0.733 | 0.605 | 7.0 |

In concrete terms, ACC4 presence rises from about **25% in V1 to 73% in V4**, and ACC5 from about **14% to 61%**. Drum/Bass are already present in almost every Variation; higher Variations are primarily built by adding accompaniment/percussion detail around that stable core.

Arrangement-level transition medians:

| Transition | Δ active roles median | Δ notes/bar median | % contexts with more notes/bar | Δ velocity median |
|---|---:|---:|---:|---:|
| V1->V2 | 1.000 | 9.000 | 0.886 | 0.000 |
| V2->V3 | 1.000 | 11.750 | 0.852 | 0.000 |
| V3->V4 | 0.000 | 12.077 | 0.876 | 0.000 |

## 4. Rhythm skeleton continuity across Variations

V1→V2 often keeps the **same rhythmic skeleton** for an existing role and adds arrangement layers. Later transitions modify accompaniment patterns more strongly, while Drum/Perc remain comparatively stable.

| Transition / role | Rhythm Jaccard median | Exact same rhythm-mask | Same Sound identity | Δ notes/bar median |
|---|---:|---:|---:|---:|
| V1->V2 DRUM | 1.0 | 0.540 | 0.964 | 0.25 |
| V1->V2 PERC | 1.0 | 0.624 | 0.990 | 0.0 |
| V1->V2 BASS | 1.0 | 0.561 | 0.967 | 0.0 |
| V1->V2 ACC1 | 1.0 | 0.517 | 0.910 | 0.0 |
| V1->V2 ACC2 | 1.0 | 0.506 | 0.911 | 0.0 |
| V1->V2 ACC3 | 0.77778 | 0.437 | 0.878 | 0.0 |
| V1->V2 ACC4 | 1.0 | 0.541 | 0.919 | 0.0 |
| V1->V2 ACC5 | 1.0 | 0.614 | 0.965 | 0.0 |
| V2->V3 DRUM | 0.9 | 0.444 | 0.968 | 0.5 |
| V2->V3 PERC | 0.88889 | 0.457 | 0.994 | 0.875 |
| V2->V3 BASS | 0.8 | 0.392 | 0.980 | 0.0 |
| V2->V3 ACC1 | 0.69231 | 0.338 | 0.907 | 0.0 |
| V2->V3 ACC2 | 0.76697 | 0.416 | 0.957 | 0.0 |
| V2->V3 ACC3 | 0.6 | 0.334 | 0.891 | 0.25 |
| V2->V3 ACC4 | 0.76389 | 0.374 | 0.911 | 0.0 |
| V2->V3 ACC5 | 1.0 | 0.530 | 0.922 | 0.0 |
| V3->V4 DRUM | 0.90909 | 0.449 | 0.957 | 1.0 |
| V3->V4 PERC | 0.92857 | 0.481 | 0.993 | 2.0 |
| V3->V4 BASS | 0.83333 | 0.422 | 0.967 | 0.0 |
| V3->V4 ACC1 | 0.6875 | 0.390 | 0.874 | 0.0 |
| V3->V4 ACC2 | 0.83333 | 0.421 | 0.907 | 0.0 |
| V3->V4 ACC3 | 0.66667 | 0.334 | 0.906 | 0.0 |
| V3->V4 ACC4 | 0.71429 | 0.415 | 0.905 | 0.0 |
| V3->V4 ACC5 | 0.625 | 0.402 | 0.899 | 0.25 |

This supports an optimizer rule: **do not reinvent V2/V3/V4 from scratch**. Prefer preserving lower-Variation skeletons, then add density, extra ACC/Perc layers, fills and selective pattern changes where Factory evidence supports them.

## 5. CV logic: rhythm is often preserved while chord adaptation changes content

Across Variations, CV1↔CV2 shows extremely high rhythm-mask equality and almost always the same Sound identity. This is strong empirical evidence that CVs are usually harmonic/chord-condition variants of the same arranger idea rather than unrelated grooves.

| Role | CV1↔CV2 comparisons | Rhythm Jaccard median | Exact same rhythm mask | Same Sound |
|---|---:|---:|---:|---:|
| DRUM | 539 | 1.000 | 0.915 | 1.000 |
| PERC | 454 | 1.000 | 0.976 | 1.000 |
| BASS | 538 | 1.000 | 0.801 | 1.000 |
| ACC1 | 500 | 1.000 | 0.830 | 1.000 |
| ACC2 | 483 | 1.000 | 0.814 | 1.000 |
| ACC3 | 436 | 1.000 | 0.839 | 1.000 |
| ACC4 | 281 | 1.000 | 0.804 | 1.000 |
| ACC5 | 187 | 1.000 | 0.856 | 0.995 |

CVs therefore stay **separate profiles** for pitch/harmony/velocity/gate evidence, but the optimizer can use their strong rhythmic relationship as a structural consistency constraint.

## 6. Cross-role timing lock

The MAX pass measures exact onset coincidence and nearest-onset distance between role pairs for every Style/Element/CV. This is not yet a kick-only or snare-only interpretation; Drum keys remain numeric until a sourced per-kit map is available.

- **Variation 4|DRUM|PERC**: median exact-onset fraction of role A = 0.66667; median nearest distance = 0.0 quarter-notes; onset Jaccard median = 0.5.
- **Variation 4|DRUM|BASS**: median exact-onset fraction of role A = 0.41026; median nearest distance = 0.08333 quarter-notes; onset Jaccard median = 0.38462.
- **Variation 4|BASS|ACC1**: median exact-onset fraction of role A = 0.37037; median nearest distance = 0.02083 quarter-notes; onset Jaccard median = 0.2037.
- **Variation 4|BASS|ACC2**: median exact-onset fraction of role A = 0.4375; median nearest distance = 0.01042 quarter-notes; onset Jaccard median = 0.17188.

This becomes the basis for ensemble optimization: Bass timing should be corrected relative to the actual Drum pattern, not by independent randomization.

## 7. Playing-technique candidate engine

The corpus is now scanned for contextual **candidates** rather than hard-coded technique labels: ghost/secondary hits, accents, staccato, legato/overlap, tenuto, dead/mute candidates, strums, repeated runs, trill/tremolo/grace patterns and special-pitch events. Candidate semantics are intentionally conservative: MIDI context can suggest a technique, but undocumented RX/DNC names are not invented.

Selected high-support examples:

- `DRUM_KIT/DRUM/Variation 4` — notes 54,823; ghost candidate 0.255; staccato 0.694; legato/overlap 0.147; dead/mute 0.000; strum candidates 340; grace 3565; special-pitch 3620.
- `DRUM_KIT/DRUM/Ending 1` — notes 53,735; ghost candidate 0.268; staccato 0.729; legato/overlap 0.141; dead/mute 0.000; strum candidates 198; grace 4919; special-pitch 4669.
- `DRUM_KIT/DRUM/Intro 1` — notes 45,946; ghost candidate 0.256; staccato 0.759; legato/overlap 0.125; dead/mute 0.000; strum candidates 138; grace 4810; special-pitch 4490.
- `DRUM_KIT/DRUM/Variation 3` — notes 42,766; ghost candidate 0.252; staccato 0.713; legato/overlap 0.140; dead/mute 0.000; strum candidates 196; grace 2666; special-pitch 3542.
- `DRUM_KIT/PERC/Variation 4` — notes 39,751; ghost candidate 0.288; staccato 0.662; legato/overlap 0.141; dead/mute 0.000; strum candidates 354; grace 3719; special-pitch 3704.
- `DRUM_KIT/DRUM/Variation 1` — notes 38,384; ghost candidate 0.295; staccato 0.594; legato/overlap 0.307; dead/mute 0.000; strum candidates 245; grace 2164; special-pitch 2172.
- `DRUM_KIT/PERC/Ending 1` — notes 37,051; ghost candidate 0.295; staccato 0.686; legato/overlap 0.167; dead/mute 0.000; strum candidates 180; grace 3822; special-pitch 3789.
- `DRUM_KIT/DRUM/Variation 2` — notes 35,218; ghost candidate 0.246; staccato 0.706; legato/overlap 0.138; dead/mute 0.000; strum candidates 265; grace 2968; special-pitch 2480.
- `GUITAR/ACC2/Variation 4` — notes 29,346; ghost candidate 0.000; staccato 0.124; legato/overlap 0.694; dead/mute 0.035; strum candidates 1535; grace 338; special-pitch 3165.
- `DRUM_KIT/PERC/Intro 1` — notes 28,730; ghost candidate 0.288; staccato 0.722; legato/overlap 0.154; dead/mute 0.000; strum candidates 176; grace 3281; special-pitch 3148.
- `DRUM_KIT/PERC/Variation 3` — notes 28,433; ghost candidate 0.293; staccato 0.713; legato/overlap 0.138; dead/mute 0.000; strum candidates 172; grace 3008; special-pitch 2347.
- `GUITAR/ACC2/Variation 3` — notes 25,615; ghost candidate 0.000; staccato 0.144; legato/overlap 0.668; dead/mute 0.049; strum candidates 1421; grace 359; special-pitch 2567.
- `GUITAR/ACC2/Ending 1` — notes 21,881; ghost candidate 0.000; staccato 0.152; legato/overlap 0.643; dead/mute 0.056; strum candidates 635; grace 281; special-pitch 2865.
- `GUITAR/ACC2/Variation 1` — notes 21,785; ghost candidate 0.000; staccato 0.126; legato/overlap 0.735; dead/mute 0.039; strum candidates 2070; grace 146; special-pitch 1529.
- `DRUM_KIT/PERC/Variation 1` — notes 20,684; ghost candidate 0.340; staccato 0.542; legato/overlap 0.366; dead/mute 0.000; strum candidates 44; grace 1877; special-pitch 2012.
- `GUITAR/ACC2/Variation 2` — notes 20,465; ghost candidate 0.000; staccato 0.152; legato/overlap 0.680; dead/mute 0.052; strum candidates 967; grace 186; special-pitch 2371.
- `DRUM_KIT/PERC/Variation 2` — notes 19,157; ghost candidate 0.285; staccato 0.685; legato/overlap 0.183; dead/mute 0.000; strum candidates 128; grace 1905; special-pitch 1599.
- `GUITAR/ACC2/Intro 1` — notes 18,693; ghost candidate 0.000; staccato 0.144; legato/overlap 0.653; dead/mute 0.056; strum candidates 525; grace 163; special-pitch 2263.
- `DRUM_KIT/DRUM/Ending 2` — notes 18,089; ghost candidate 0.260; staccato 0.645; legato/overlap 0.210; dead/mute 0.000; strum candidates 95; grace 1794; special-pitch 1765.
- `PIANO/ACC1/Ending 1` — notes 16,382; ghost candidate 0.000; staccato 0.240; legato/overlap 0.439; dead/mute 0.000; strum candidates 192; grace 143; special-pitch 37.
- `PIANO/ACC1/Variation 4` — notes 16,266; ghost candidate 0.000; staccato 0.285; legato/overlap 0.400; dead/mute 0.000; strum candidates 396; grace 98; special-pitch 220.
- `PIANO/ACC1/Intro 1` — notes 14,562; ghost candidate 0.000; staccato 0.266; legato/overlap 0.439; dead/mute 0.000; strum candidates 144; grace 222; special-pitch 157.
- `GUITAR/ACC3/Variation 4` — notes 14,214; ghost candidate 0.000; staccato 0.153; legato/overlap 0.572; dead/mute 0.050; strum candidates 308; grace 262; special-pitch 1954.
- `BASS/BASS/Variation 4` — notes 14,102; ghost candidate 0.000; staccato 0.168; legato/overlap 0.269; dead/mute 0.070; strum candidates 0; grace 356; special-pitch 1457.
- `DRUM_KIT/DRUM/Intro 2` — notes 13,213; ghost candidate 0.218; staccato 0.691; legato/overlap 0.176; dead/mute 0.000; strum candidates 54; grace 1177; special-pitch 825.

**Important:** Drum gate-based staccato/legato numbers are descriptive only and are **not** used as drum articulation targets because Pa800 Drum Kit keys can have Single Trigger / Note Off Receive semantics.

## 8. RX / noise / special-pitch evidence

This pass found **176 exact Sound identities** with special-pitch activity according to their separated pitch clusters. Instead of deleting them as outliers, the analyzer measures whether they occur before, after or isolated from normal musical notes.

| Sound | Special notes | Fraction | Before normal | After normal | Isolated |
|---|---:|---:|---:|---:|---:|
| Steel Guitar RX1 | 6,091 | 0.219 | 4476 | 1612 | 3 |
| Jazz Kit RX2 | 5,994 | 0.208 | 4747 | 1247 | 0 |
| Finger Bass 2 | 5,866 | 0.434 | 5808 | 58 | 0 |
| Clean Funk RX1 | 5,500 | 0.371 | 3669 | 1811 | 20 |
| Steel Guitar Pro | 4,188 | 0.220 | 3297 | 891 | 0 |
| Brush Kit RX1 | 3,822 | 0.317 | 3080 | 742 | 0 |
| Pop Std. Kit 1 | 3,215 | 0.636 | 1600 | 1011 | 604 |
| 12 Strings Pro | 3,136 | 0.244 | 3014 | 122 | 0 |
| Clean Guitar RX1 | 3,103 | 0.175 | 2743 | 360 | 0 |
| Steel Guitar RX2 | 2,545 | 0.291 | 1716 | 129 | 700 |
| i30 Perc. Kit | 2,511 | 0.892 | 209 | 51 | 2251 |
| Percussion Kit | 2,420 | 0.145 | 1668 | 644 | 108 |
| House Kit RX1 | 2,198 | 0.207 | 1818 | 380 | 0 |
| Jazz Kit RX1 | 2,145 | 0.160 | 1633 | 512 | 0 |
| Latin Perc. Kit1 | 2,135 | 0.693 | 1318 | 674 | 143 |
| Nylon Gtr RX2 | 2,112 | 0.242 | 1544 | 568 | 0 |
| Stra. Vel. Pro | 1,865 | 0.258 | 1861 | 4 | 0 |
| Nylon Gtr Pro2 | 1,817 | 0.420 | 1452 | 365 | 0 |
| Steel Slide Pro2 | 1,739 | 0.253 | 1404 | 335 | 0 |
| Nylon Gtr Pro1 | 1,692 | 0.292 | 1524 | 168 | 0 |
| House Kit 1 | 1,671 | 0.292 | 1405 | 266 | 0 |
| Finger Bass 3 | 1,622 | 0.509 | 1507 | 85 | 30 |
| Brush Kit 1 | 1,622 | 0.395 | 1363 | 259 | 0 |
| Techno Kit 3 | 1,613 | 0.406 | 1467 | 127 | 19 |
| Clean Guitar RX4 | 1,561 | 0.391 | 909 | 426 | 226 |

For example, `Clean Guitar RX1` has thousands of events in detached special pitch clusters and most are positioned **before** normal musical events. This is precisely the sort of evidence needed for a future fret/pick/release/noise classifier, but the MAX system still labels them `SPECIAL_CANDIDATE` until manual/hardware identifies the actual articulation.

## 9. Controller / PB / RPN / DNC-state forensics

- CC22: **125,493** events; all observed values are 0. Preserve as structural/device data, do not normalize.
- Pitch Bend: **52,542** events.
- CC1: **18,551** events, of which 6,388 are ≥64.
- CC2: **4** events, all value 0 — no active Y− evidence in this corpus.
- CC64: **5,792** events, 2,677 are pedal-on values.
- CC80: **9** events across 6 exported Sound contexts; CC81: **0**. Since none of the 23 exact manual DNC addresses occur in this Factory corpus, these CC80 events are preserved but **not automatically called DNC SC1 articulations**.
- Channel Aftertouch: **0**; Poly Aftertouch: **0**.
- Standard NRPN sequences detected: **0** distinct; RPN sequences: **1** distinct.

The exact control inventory is exported with value histograms and Element/Role/CV context.

## 10. Pattern fingerprinting / Factory template reuse

Every segment receives two fingerprints: a transposition-independent **rhythm fingerprint** and a coarse **performance fingerprint**. This reveals where Korg reuses arranger skeletons across different Styles rather than treating every Style as unrelated data.

- RHYTHM `ACC1/Break` fingerprint `cba2fdf5c5772adc` appears in **115 styles** (124 segments).
- RHYTHM `BASS/Break` fingerprint `cba2fdf5c5772adc` appears in **66 styles** (68 segments).
- RHYTHM `ACC2/Break` fingerprint `cba2fdf5c5772adc` appears in **53 styles** (62 segments).
- RHYTHM `ACC3/Break` fingerprint `cba2fdf5c5772adc` appears in **51 styles** (60 segments).
- RHYTHM `ACC5/Break` fingerprint `cba2fdf5c5772adc` appears in **51 styles** (58 segments).
- RHYTHM `ACC4/Break` fingerprint `cba2fdf5c5772adc` appears in **47 styles** (52 segments).
- RHYTHM `BASS/Break` fingerprint `54015302c3c0b258` appears in **44 styles** (49 segments).
- RHYTHM `ACC5/Fill 2` fingerprint `cba2fdf5c5772adc` appears in **41 styles** (47 segments).
- RHYTHM `BASS/Intro 3` fingerprint `9e34d20914f008da` appears in **31 styles** (31 segments).
- RHYTHM `ACC1/Fill 1` fingerprint `cba2fdf5c5772adc` appears in **28 styles** (33 segments).
- RHYTHM `ACC4/Fill 2` fingerprint `cba2fdf5c5772adc` appears in **28 styles** (30 segments).
- RHYTHM `ACC3/Fill 2` fingerprint `cba2fdf5c5772adc` appears in **27 styles** (32 segments).
- PERFORMANCE `ACC1/Break` fingerprint `cab2fb13ea1ad71d` appears in **27 styles** (30 segments).
- PERFORMANCE `BASS/Break` fingerprint `02a1f226febef658` appears in **26 styles** (26 segments).
- PERFORMANCE `ACC1/Break` fingerprint `cf40a5513b7006af` appears in **25 styles** (25 segments).

This should be used for train/test leakage protection and for deduplicating reference patterns: many Break/Fill skeletons recur across numerous Factory styles.

## 11. Full atom dimensions now available

For each context/sound-state segment the MAX warehouse includes: exact identity; Element/CV/role; bars/meter/PPQ; note and onset density; full velocity zones/modes/valleys; register/pitch-class entropy; duration/gate ratios; 8th/16th/32nd + triplet grid residuals; 24-phase groove histogram; bar-pattern repeat similarity; polyphony/chord groups; signed intervals; repeated/trill/tremolo/grace runs; strum spread/direction/velocity slope; ghost/accent/dead-mute candidates; four-part phrase contour; special-pitch timing relation; pattern fingerprints; and linked controller evidence.

## 12. Instrument-family coverage

All observed engineering families are covered. Exact Sound identity remains primary; family labels are organizational fallbacks for **analysis only**, never permission to mutate an unknown Sound. See `factory_analysis_coverage_max.csv`.

## 13. Hard boundaries — what Factory SMF cannot prove

- Which internal oscillator/sample was selected by Cycle/Random.
- Exact RX/DNC articulation name when no manual/Sound Edit mapping exists.
- NTT / Trigger Mode / Tension parameter value if the export does not serialize it.
- Audible timbre, sample identity or velocity-layer audio result without Pa800 playback.
- Per-kit semantic drum names unless a sourced Factory key map exists.

These are explicitly `NOT_OBSERVABLE` or `PROTECTED`, not guessed.

## 14. Optimizer consequences

1. **Variation optimizer:** preserve core Drum/Bass skeleton, grow orchestration and density first; velocity is a local/contextual adjustment, not the primary V1→V4 lever.
2. **CV optimizer:** enforce rhythmic consistency across CVs while keeping harmonic/pitch/gate profiles separate.
3. **Drum/Perc:** exact Kit+Key+Element+CV+beat profile; ghost/accent modes stay separate; no global drum velocity curve.
4. **Bass:** couple timing to Drum context; preserve repeated/root/passing contour; avoid global humanize.
5. **Guitar:** use near-onset strum groups, spread/direction/velocity slope, gate and special-pitch relations; confirmed Guitar Mode remains a separate engine.
6. **Noise/RX:** never key-range-clean special clusters; classify pre/post/isolated relation first.
7. **Controllers:** PB/CC1/CC64/CC80 and unusual CCs are exact-Sound/state evidence, protected before optimization.
8. **Randomize:** sample deterministic residuals from matching Factory context rather than uniform ±N.
9. **Verifier:** pitch, note count, Style Element boundaries, CV identity, Sound state, controllers and protected special events remain invariants unless a documented engine explicitly owns the change.