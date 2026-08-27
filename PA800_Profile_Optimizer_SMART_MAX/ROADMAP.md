# PA800 Factory Performance Profile Research — NO DNA

> Aktivni završni plan nakon verzije 2.1 nalazi se u `ROADMAP_FULL_FACTORY_2.2_TO_3.0.md`. Precizan audit korištenja korpusa nalazi se u `FACTORY_USAGE_AUDIT_2.1.md`. Ovaj dokument ostaje evidencijski Factory research roadmap.

## Scope and method

This report treats the official Korg manuals as **device semantics** and `Factory Styles.zip` as **empirical performance observations**. No DNA/Gold/neural evidence chain is used. Factory data can prove that an event/pattern occurs; it cannot by itself prove the internal RX/DNC meaning of a note or controller.

## 1. Corpus integrity

- 252/252 Style MIDI files were parsed with a tolerant raw Standard MIDI File parser.
- All files are Format 1, 192 PPQ, 50 tracks.
- 1,430,602 valid Note-On events retained for analysis.
- 2,798 invalid channel-data events were flagged and skipped, not clipped. Dominant malformed form is Note-On note=0 velocity=255 (2,228 events). Clipping these to 127 would create fake velocity maxima, so the optimizer/parser must never use `clip=True` as a repair strategy.
- 542 exported address+name Sound identities observed across 526 unique MIDI addresses. 12 addresses have conflicting exported names and are `IDENTITY_CONFLICT` until resolved by the official Factory registry/manual.
- 48 RX-named Sound/Kit identities occur in Factory styles. **0 DNC-named identities occur in this corpus**, therefore DNC behavior must not be inferred from Factory naming/patterns alone.

### Style structure observed

Element Note-On counts: Variation 4 252,169; Ending 1 236,075; Intro 1 205,415; Variation 3 192,788; Variation 2 150,605; Variation 1 149,169; Ending 2 74,444; Intro 2 55,959; Fill 2 35,378; Ending 3 33,267; Fill 1 27,164; Break 12,850; Intro 3 5,319. No literal `Fill 3` label was observed in this export corpus; `Break` is exported separately with 12,850 Note-On events, so the optimizer must preserve the source label instead of assuming whether Break and Fill 3 are equivalent.

CV event support: CV1 776,674; CV2 488,178; CV3 122,859; CV4 27,038; CV5 11,498; CV6 4,355. Meter distribution: 218×4/4, 18×3/4, 8×2/4, 6×6/8, 2×6/4. Approximate tempo span 57–196 BPM, median ~110 BPM.

## 2. Parent role observations (not optimizer targets)

| Role | Note-On | V P10 | V median | V P90 | duration median ticks |
|---|---:|---:|---:|---:|---:|
| DRUM | 332,550 | 49 | 93 | 122 | 2 |
| PERC | 215,306 | 46 | 81 | 116 | 2 |
| BASS | 99,803 | 78 | 102 | 122 | 86 |
| ACC1 | 198,828 | 60 | 88 | 111 | 63 |
| ACC2 | 261,208 | 53 | 84 | 114 | 48 |
| ACC3 | 169,195 | 50 | 84 | 113 | 48 |
| ACC4 | 96,089 | 51 | 90 | 114 | 49 |
| ACC5 | 57,623 | 53 | 90 | 115 | 49 |

These values are only parent envelopes. They are too coarse for direct optimization.

## 3. Why the profile must be hierarchical

Three-fold split testing of the 148 STRONG/GOOD exact Sound profiles found: {'CONTEXT_DEPENDENT': 110, 'MODERATE': 15, 'STABLE': 5, 'INSUFFICIENT_SPLIT_SUPPORT': 18}. Of 443 sufficiently supported Sound+Element cells: {'CONTEXT_DEPENDENT': 381, 'MODERATE': 48, 'STABLE': 9, 'INSUFFICIENT_SPLIT_SUPPORT': 5}. The large `CONTEXT_DEPENDENT` count means a single exact-Sound curve is still too coarse; style/element/CV/function/local contour must condition the transform. Global exact-Sound statistics remain a fallback envelope, not a fixed target.

Recommended profile key: `device + MSB + LSB + Program + exported Sound + role + element + CV + musical_function`. Fallback: remove `musical_function`, then CV, then element, then role; if support remains weak, preserve.

## 4. Profile dimensions

Every supported profile should store: identity/support; normal and special-candidate pitch clusters; velocity histogram/modes and seven-zone curve (raw min, working min, ideal min/center/max, working max, raw max); straight/triplet timing residual models; duration and gate-to-next-onset; density; polyphony/chord-size; signed intervals; bar/beat position; accent contour; phrase/repetition; controller/PB/AT activity; element/CV breakdown; interaction offsets to other roles.

`raw_min/raw_max` are observations, never forced limits. `working` and `ideal` zones are derived from robust quantiles only after special-event candidates are separated. Multimodal distributions use multiple modes instead of one median. Randomization is deterministic sampling from residual distributions, never uniform ±N.

## 5. Instrument-family coverage

| Engineering bucket* | Profiles | Notes | Strong | Good | RX | Key optimizer focus |
|---|---:|---:|---:|---:|---:|---|
| DRUM_KIT | 52 | 541,908 | 17 | 10 | 19 | Exact kit+key modes, beat position, accents, fills, note-off/exclusive-group safety |
| GUITAR | 103 | 409,453 | 10 | 33 | 19 | Normal vs special pitch clusters, chord/strum spread, PB/CC, RX/Guitar Mode guard |
| PIANO | 60 | 136,661 | 6 | 12 | 4 | Chordal density, velocity contour, CC64/pedal, Grand Piano RX safety |
| BASS | 45 | 98,247 | 10 | 5 | 5 | Root/passing/approach function, kick relation, velocity/gate, special-range protection |
| BRASS | 61 | 59,403 | 3 | 9 | 0 | Section/line role, accents, articulation/gate, PB/CC1 preservation |
| ORGAN | 40 | 42,449 | 1 | 3 | 0 | Sustain/overlap/expression, chordal vs rhythmic role |
| ENSEMBLE | 39 | 37,773 | 5 | 8 | 0 | Sustain vs short articulation, overlap/gate, phrase swells |
| ACCORDION_REED | 12 | 27,888 | 1 | 2 | 0 | Repeated chord/line intent, phrase accents, shorter gate behavior |
| REED | 23 | 15,499 | 1 | 2 | 0 | Monophonic/section phrase, PB/CC1, legato/staccato |
| SYNTH_PAD | 35 | 14,337 | 2 | 2 | 0 | Long gate, chord size, low-density background role |
| CHROMATIC_PERC | 9 | 9,114 | 0 | 3 | 0 | One-shot/key behavior, velocity/metric accent, duration cautious |
| STRINGS | 7 | 8,535 | 0 | 2 | 0 | Separate pizzicato from sustained/arco; radically different gate profiles |
| SFX | 6 | 8,315 | 0 | 1 | 1 | Preserve unusual registers/events; no generic melodic cleanup |
| SYNTH_LEAD | 20 | 7,664 | 0 | 0 | 0 | Low support: family/role fallback or preserve |
| ETHNIC | 10 | 5,846 | 0 | 0 | 0 | Low style diversity: exact profile rarely authoritative |
| PIPE | 8 | 3,228 | 0 | 0 | 0 | Phrase/legato analysis but mostly insufficient support |
| SYNTH_FX | 9 | 2,154 | 0 | 0 | 0 | Preserve/context only unless exact support improves |
| PERCUSSIVE | 3 | 2,128 | 0 | 0 | 0 | Per-key/per-hit role where mapping is known; otherwise preserve |

\*Engineering buckets are organizational labels for the code; exact Korg address+name remains the primary identity.

## 6. Detailed evidence by instrument

### Bass
- `121.6.33 Finger Bass 2` — N=17,943, styles=42, STRONG; V P10/P25/P50/P75/P90=83/98/109/118/124; primary pitch=24–48; special clusters=1; gate center=0.717.
- `121.0.33 Finger Bass GM` — N=11,038, styles=31, STRONG; V P10/P25/P50/P75/P90=82/94/108/115/122; primary pitch=24–50; special clusters=0; gate center=0.851.
- `121.3.34 Stein Bass` — N=7,283, styles=19, STRONG; V P10/P25/P50/P75/P90=78/94/102/114/118; primary pitch=24–48; special clusters=0; gate center=0.812.
- `121.13.33 Finger Bass RX` — N=4,774, styles=10, STRONG; V P10/P25/P50/P75/P90=76/86/90/96/102; primary pitch=26–48; special clusters=2; gate center=0.734.
- `121.4.36 SlapFing Bass RX` — N=5,573, styles=17, STRONG; V P10/P25/P50/P75/P90=72/84/92/100/109; primary pitch=24–48; special clusters=0; gate center=0.844.
- `121.10.34 Picked Bass RX` — N=1,071, styles=4, LIMITED; V P10/P25/P50/P75/P90=50/76/84/90/97; primary pitch=24–48; special clusters=1; gate center=0.802.
Build note-function classes only after harmony/phrase analysis. Protect high detached pitch clusters as `SPECIAL_CANDIDATE` until manual/hardware identifies them. Couple onset timing to kick; gate correction is allowed only on normal musical notes.

### Guitar
- `121.15.25 Steel Guitar RX1` — N=31,627, styles=19, STRONG; V P10/P25/P50/P75/P90=53/61/77/91/99; primary pitch=43–72; special clusters=2; gate center=0.97.
- `121.14.28 Clean Guitar RX1` — N=21,847, styles=17, STRONG; V P10/P25/P50/P75/P90=32/52/67/100/126; primary pitch=43–72; special clusters=2; gate center=0.703.
- `121.10.28 Clean Funk RX1` — N=20,433, styles=17, STRONG; V P10/P25/P50/P75/P90=51/67/83/97/112; primary pitch=45–76; special clusters=1; gate center=0.814.
- `121.12.24 Nylon Gtr RX1` — N=9,271, styles=8, GOOD; V P10/P25/P50/P75/P90=50/56/67/84/93; primary pitch=41–67; special clusters=1; gate center=0.964.
- `121.13.24 Nylon Gtr RX2` — N=9,075, styles=8, GOOD; V P10/P25/P50/P75/P90=50/62/80/90/96; primary pitch=43–72; special clusters=2; gate center=0.938.
- `121.11.28 Clean Funk RX2` — N=7,785, styles=12, STRONG; V P10/P25/P50/P75/P90=73/96/106/115/122; primary pitch=36–72; special clusters=1; gate center=0.542.
Profile chord groups, onset spread, velocity slope and releases. High pitch clusters are common in RX guitars; never key-range-clean them blindly. Ordinary guitar and confirmed Guitar Mode must use separate engines.

### Piano / EP
- `121.3.0 Grand Piano` — N=56,049, styles=68, STRONG; V P10/P25/P50/P75/P90=63/77/89/102/114; primary pitch=36–96; special clusters=0; gate center=0.849.
- `121.10.0 Grand Piano RX` — N=3,056, styles=6, GOOD; V P10/P25/P50/P75/P90=67/92/118/122/122; primary pitch=32–84; special clusters=3; gate center=0.982.
- `121.18.4 Tine E.Piano RX` — N=3,424, styles=13, STRONG; V P10/P25/P50/P75/P90=68/78/86/98/107; primary pitch=36–72; special clusters=0; gate center=0.661.
- `121.4.4 Vintage EP` — N=4,938, styles=13, STRONG; V P10/P25/P50/P75/P90=52/65/76/91/105; primary pitch=43–79; special clusters=0; gate center=0.74.
- `121.11.4 Club E. Piano` — N=5,296, styles=11, STRONG; V P10/P25/P50/P75/P90=74/84/93/102/108; primary pitch=48–84; special clusters=0; gate center=0.823.
Optimize chordal dynamics/density/gate with pedal-state awareness. CC64 is protected; Grand Piano RX is specifically damper/resonance-sensitive.

### Accordion
- `121.25.21 Steirisch.Akk.1` — N=16,541, styles=12, STRONG; V P10/P25/P50/P75/P90=72/85/97/104/114; primary pitch=51–79; special clusters=1; gate center=0.457.
- `121.23.21 Master Accordion` — N=1,275, styles=6, GOOD; V P10/P25/P50/P75/P90=59/78/93/105/117; primary pitch=63–91; special clusters=0; gate center=0.458.
- `121.18.21 French Musette` — N=2,319, styles=3, LIMITED; V P10/P25/P50/P75/P90=55/64/74/88/100; primary pitch=55–87; special clusters=0; gate center=0.326.
Use phrase/repetition and chord/line role. Factory shows substantially shorter gate behavior than sustained strings/pads; do not borrow organ/string profiles.

### Strings / Ensemble
- `121.6.49 Movie Strings 2` — N=4,835, styles=21, STRONG; V P10/P25/P50/P75/P90=47/53/76/95/106; primary pitch=36–91; special clusters=0; gate center=0.997.
- `121.3.48 Stereo Strings` — N=4,443, styles=26, STRONG; V P10/P25/P50/P75/P90=49/64/89/104/114; primary pitch=29–89; special clusters=0; gate center=0.75.
- `121.7.48 Arco Strings` — N=3,936, styles=12, STRONG; V P10/P25/P50/P75/P90=70/84/100/108/114; primary pitch=36–89; special clusters=0; gate center=0.438.
- `121.5.48 i3 Strings` — N=3,483, styles=19, STRONG; V P10/P25/P50/P75/P90=66/82/98/106/116; primary pitch=43–91; special clusters=0; gate center=0.87.
- `121.1.45 Pizz. Ensemble` — N=2,211, styles=5, GOOD; V P10/P25/P50/P75/P90=70/85/93/111/127; primary pitch=28–79; special clusters=0; gate center=0.222.
Split sustained/arco versus pizzicato before any gate model. Pizzicato center gate is dramatically shorter than sustained ensemble examples.

### Brass / reeds
- `121.13.61 Fat Brass` — N=6,518, styles=10, STRONG; V P10/P25/P50/P75/P90=67/80/99/113/121; primary pitch=42–84; special clusters=0; gate center=0.514.
- `121.2.61 Tight Brass 3` — N=5,146, styles=11, STRONG; V P10/P25/P50/P75/P90=60/80/97/114/123; primary pitch=43–86; special clusters=0; gate center=0.654.
- `121.1.71 Jazz Clarinet` — N=2,925, styles=10, STRONG; V P10/P25/P50/P75/P90=88/96/103/114/116; primary pitch=43–86; special clusters=0; gate center=0.812.
- `121.1.66 Tenor Sax Noise1` — N=3,006, styles=5, GOOD; V P10/P25/P50/P75/P90=54/68/82/99/110; primary pitch=46–72; special clusters=0; gate center=0.875.
Separate section/chordal from monophonic line. Preserve PB/CC1; classify phrase accents and legato/staccato from actual context.

### Pads
- `121.11.91 Fresh Air 2` — N=2,578, styles=14, STRONG; V P10/P25/P50/P75/P90=66/82/107/115/122; primary pitch=36–84; special clusters=0; gate center=0.947.
- `121.6.89 Dark Pad` — N=1,503, styles=15, STRONG; V P10/P25/P50/P75/P90=58/70/82/96/111; primary pitch=36–91; special clusters=0; gate center=0.999.
- `121.8.89 Analog Pad 1` — N=1,082, styles=9, GOOD; V P10/P25/P50/P75/P90=53/66/78/100/108; primary pitch=32–84; special clusters=0; gate center=0.979.
Long-gate, low-density background profiles; priority is overlap, chord size and background intensity rather than note randomization.

## 7. RX-specific empirical inventory

Factory contains **48 RX-named identities**. The complete list is exported as `factory_rx_profiles_v1.csv`. Representative evidence:

- `120.0.5 Standard Kit RX1` — N=50,228, styles=34, STRONG; V P10/P25/P50/P75/P90=46/68/99/114/124; primary pitch=0–57; special clusters=0; gate center=0.062.
- `120.0.2 Standard Kit RX3` — N=27,939, styles=24, STRONG; V P10/P25/P50/P75/P90=49/67/95/114/120; primary pitch=35–59; special clusters=1; gate center=0.312.
- `120.0.34 Jazz Kit RX2` — N=42,237, styles=32, STRONG; V P10/P25/P50/P75/P90=48/67/93/112/123; primary pitch=35–70; special clusters=1; gate center=0.031.
- `120.0.42 Brush Kit RX1` — N=23,964, styles=22, STRONG; V P10/P25/P50/P75/P90=39/55/74/92/108; primary pitch=32–59; special clusters=3; gate center=0.021.
- `121.13.33 Finger Bass RX` — N=4,774, styles=10, STRONG; V P10/P25/P50/P75/P90=76/86/90/96/102; primary pitch=26–48; special clusters=2; gate center=0.734.
- `121.4.36 SlapFing Bass RX` — N=5,573, styles=17, STRONG; V P10/P25/P50/P75/P90=72/84/92/100/109; primary pitch=24–48; special clusters=0; gate center=0.844.
- `121.14.28 Clean Guitar RX1` — N=21,847, styles=17, STRONG; V P10/P25/P50/P75/P90=32/52/67/100/126; primary pitch=43–72; special clusters=2; gate center=0.703.
- `121.10.28 Clean Funk RX1` — N=20,433, styles=17, STRONG; V P10/P25/P50/P75/P90=51/67/83/97/112; primary pitch=45–76; special clusters=1; gate center=0.814.
- `121.15.25 Steel Guitar RX1` — N=31,627, styles=19, STRONG; V P10/P25/P50/P75/P90=53/61/77/91/99; primary pitch=43–72; special clusters=2; gate center=0.97.
- `121.12.24 Nylon Gtr RX1` — N=9,271, styles=8, GOOD; V P10/P25/P50/P75/P90=50/56/67/84/93; primary pitch=41–67; special clusters=1; gate center=0.964.
- `121.13.24 Nylon Gtr RX2` — N=9,075, styles=8, GOOD; V P10/P25/P50/P75/P90=50/62/80/90/96; primary pitch=43–72; special clusters=2; gate center=0.938.
- `121.10.0 Grand Piano RX` — N=3,056, styles=6, GOOD; V P10/P25/P50/P75/P90=67/92/118/122/122; primary pitch=32–84; special clusters=3; gate center=0.982.
- `121.18.4 Tine E.Piano RX` — N=3,424, styles=13, STRONG; V P10/P25/P50/P75/P90=68/78/86/98/107; primary pitch=36–72; special clusters=0; gate center=0.661.
- `121.3.120 Vox Wah Chick RX` — N=7,285, styles=9, GOOD; V P10/P25/P50/P75/P90=52/67/89/102/113; primary pitch=44–77; special clusters=1; gate center=0.604.

No DNC-named Sound is present in Factory Styles. DNC remains a manual/Sound-profile/hardware concern, not a Factory-pattern inference.

## 8. RX/special pitch-range evidence

Separate pitch clusters occur in 37 of the 48 RX-named profiles. This is strong empirical evidence for a `normal musical range` plus one or more `special candidate ranges`, but it does **not** identify the special range as fret noise/slide/mute/etc. by itself. Examples:
- Finger Bass RX: primary={'min': 26, 'max': 48, 'center': 36.67, 'count': 3674, 'fraction': 0.76959}; special=[{'min': 97, 'max': 101, 'center': 99.84, 'count': 829, 'fraction': 0.17365}, {'min': 110, 'max': 116, 'center': 113.19, 'count': 54, 'fraction': 0.01131}]
- Clean Guitar RX1: primary={'min': 43, 'max': 72, 'center': 59.8, 'count': 18028, 'fraction': 0.82519}; special=[{'min': 96, 'max': 105, 'center': 99.39, 'count': 2538, 'fraction': 0.11617}, {'min': 120, 'max': 124, 'center': 122.68, 'count': 428, 'fraction': 0.01959}]
- Clean Funk RX1: primary={'min': 45, 'max': 76, 'center': 61.7, 'count': 14194, 'fraction': 0.69466}; special=[{'min': 96, 'max': 105, 'center': 100.17, 'count': 5500, 'fraction': 0.26917}]
- Steel Guitar RX1: primary={'min': 43, 'max': 72, 'center': 57.86, 'count': 24595, 'fraction': 0.77766}; special=[{'min': 96, 'max': 105, 'center': 99.54, 'count': 5460, 'fraction': 0.17264}, {'min': 126, 'max': 127, 'center': 126.48, 'count': 631, 'fraction': 0.01995}]
- Nylon Gtr RX1: primary={'min': 41, 'max': 67, 'center': 58.71, 'count': 7498, 'fraction': 0.80876}; special=[{'min': 96, 'max': 105, 'center': 101.43, 'count': 1539, 'fraction': 0.166}]
- Nylon Gtr RX2: primary={'min': 43, 'max': 72, 'center': 60.09, 'count': 6760, 'fraction': 0.7449}; special=[{'min': 96, 'max': 109, 'center': 101.03, 'count': 1750, 'fraction': 0.19284}, {'min': 121, 'max': 127, 'center': 124.89, 'count': 290, 'fraction': 0.03196}]
- SlapPick Bass RX: primary={'min': 28, 'max': 50, 'center': 37.23, 'count': 491, 'fraction': 0.57159}; special=[{'min': 99, 'max': 108, 'center': 100.74, 'count': 357, 'fraction': 0.4156}]

Optimizer rule: special candidate ranges are preserve/protect by default. Only a verified Sound profile may assign articulation semantics or insert events.

## 9. Drum evidence — exact kit + exact key

2,004 kit-key profiles were built across 52 observed Drum Kit identities. One global kit velocity curve is invalid. Examples:
- `Standard Kit RX1` KEY_036: N=6,301, styles=23; V P10/P25/P50/P75/P90=80/102/110/118/120
- `Standard Kit RX1` KEY_038: N=4,539, styles=25; V P10/P25/P50/P75/P90=31/49/100/124/124
- `Standard Kit RX1` KEY_042: N=10,426, styles=27; V P10/P25/P50/P75/P90=51/68/98/114/120
- `Standard Kit RX3` KEY_036: N=3,465, styles=17; V P10/P25/P50/P75/P90=80/100/114/120/122
- `Standard Kit RX3` KEY_038: N=3,277, styles=19; V P10/P25/P50/P75/P90=36/58/98/120/124
- `Standard Kit RX3` KEY_042: N=6,556, styles=20; V P10/P25/P50/P75/P90=44/58/91/114/118
- `Jazz Kit RX2` KEY_036: N=4,491, styles=25; V P10/P25/P50/P75/P90=90/102/114/125/126
- `Jazz Kit RX2` KEY_042: N=9,652, styles=32; V P10/P25/P50/P75/P90=54/67/82/103/116
- `Brush Kit RX1` KEY_038: N=4,625, styles=22; V P10/P25/P50/P75/P90=39/53/73/90/108

Do not label KEY_036 as Kick or KEY_038 as Snare purely by GM convention for an arbitrary RX/User kit. Use exact per-kit mapping when sourced; until then key identity remains numeric. Drum Note-Off/gate must be preserved rather than normalized because Pa800 supports per-key Note Off Receive and Single Trigger behavior.

## 10. Controllers and performance events

Across the corpus the valid performance/control inventory includes approximately: CC22 125,493; Pitch Bend 52,542; CC32 31,351; CC7 31,231; CC11 31,223; CC0 31,217; CC1 18,551; CC64 5,792; CC31 3,276; CC67 178; CC66 72; CC2 only 4; Channel Aftertouch 0. This proves that Factory styles heavily use PB/CC1/CC64 on selected Sounds but provides almost no corpus support for generic CC2/aftertouch rules.

Examples: Pedal Steel Gtr1 has thousands of PB and CC1 events; Dist. Guitar RX2 has heavy PB use; Grand Piano has thousands of CC64 events; Jazz Clarinet has heavy CC1/PB; Clean Guitar RX1 and Nylon Gtr RX1 also carry PB/CC activity. Therefore controller thinning/smoothing must be exact-Sound aware and protected by default.

## 11. Identity conflicts found in Factory export

12 exact MIDI addresses carry more than one exported Sound name. Examples include 120.0.35 (`Jazz Kit RX2` / `Jazz Kit RX3`), 121.32.0 (`Classic Piano` / `Grand Piano`), 121.32.24 (multiple Nylon Guitar Pro names), and others. These are saved in `factory_address_name_conflicts_v1.csv`. Rule: never silently merge; resolve with official Factory registry or keep address+exported-name identity separate.

## 12. Manual facts that constrain optimization

- Pa800 Sound architecture supports up to 16 oscillators, high/low multisamples, velocity switch, velocity/key zones and Scaled Velocity.
- Korg explicitly demonstrates an RX guitar fret-noise zone at MIDI velocity 10–20 that is internally rescaled; low velocity is therefore not synonymous with a quiet normal note.
- DNC trigger modes include Normal, Legato, Staccato, controller-triggered, Cycle and Random behavior. Nylon Guitar DNC is the manual example for legato Max Range=5 semitones; ~15 ms is an example useful legato gap, not a universal constant.
- CC64/damper can control Resonance/Halo and special damper-trigger samples; Grand Piano RX and Harmonica DNC are documented examples.
- Drum Kits have per-key sample/layer logic, velocity switching, Single Trigger, Note Off Receive and Exclusive Groups.
- Guitar Mode and RX Noise use special control regions/events. OS 1.60 `Humanize GTR` affects position, velocity and length only on Guitar tracks. `RX Convert / Add RX Noises to Guitar track` shows Korg itself performs context-aware SMF guitar analysis, but its internal algorithm is not published.

These facts constrain the optimizer; Factory statistics supply the numeric performance envelopes.

## 13. Final profile schema

```text
SoundPerformanceProfile
  identity: device, MSB, LSB, Program, exported_name, canonical_name?, role
  support: notes, segments, styles, stability
  context: element, CV, musical_function, meter/groove class
  pitch: raw, primary musical clusters, protected/special candidates
  velocity: 127-bin histogram, modes, 7-zone curve, residual variance
  timing: candidate-grid residual distributions, systematic offset, variance
  gate: duration, IOI ratio, overlap/gap, articulation class
  density/polyphony: notes/bar, chord size, simultaneity
  interval/phrase: direction, repeat, phrase start/body/end
  controllers: CC/PB/AT state and trajectories
  interaction: kick↔bass, snare↔guitar, drum↔perc, lead↔background
  safety: RX/DNC protected zones/events, identity conflicts
```

## 14. Optimizer algorithm

1. Parse without destructive repair. 2. Resolve exact Sound identity; conflict => review/preserve. 3. Detect role/element/CV and musical function. 4. Separate normal musical events from protected/special candidates. 5. Select deepest supported profile. 6. Preserve original local contour. 7. Apply soft correction toward the relevant mode/curve. 8. Add deterministic residual randomization sampled from the matching Factory distribution. 9. Apply timing/gate only when instrument semantics allow it. 10. Preserve sensitive controllers/RX/DNC events. 11. Run ensemble interaction correction. 12. Event-level diff + structural verifier + rollback.

## 15. Roadmap — no DNA

1. P00 Tolerant byte-preserving MIDI parser + malformed-event quarantine
2. P01 Official PA800 device registry (canonical CC00.CC32.PC, Sound/Kit identity, manual mechanics)
3. P02 Factory structure extractor: Style/Element/CV/Role/window
4. P03 Raw measurement engine: note/vel/onset/duration/IOI/CC/PB/AT
5. P04 Factory Proof Registry: counts, style diversity, distributions, conflicts
6. P05 Pitch cluster engine: normal musical vs protected/special candidate ranges
7. P06 Velocity profile engine: histograms, modes, seven zones, curve, residual variance
8. P07 Timing profile engine: straight/triplet/shuffle candidate grids + microtiming residuals
9. P08 Gate/legato engine: non-drum duration/IOI/overlap/gap
10. P09 Drum per-kit/per-key profiler + beat-position modes
11. P10 Bass intent profiler: root/chord/passing/approach/repeat/transition + kick relation
12. P11 Guitar intent profiler: ordinary/Guitar Mode split, chord/strum/riff, spread and controller behavior
13. P12 Piano/keys profiler: chordal density, pedal state, phrase dynamics
14. P13 Organ/accordion profiler
15. P14 Strings/ensemble/pizzicato/pad profiler
16. P15 Brass/reed/pipe profiler
17. P16 Percussion/chromatic/ethnic/synth/SFX bounded fallback profiles
18. P17 Musical Intent Analyzer
19. P18 Velocity optimizer + deterministic randomizer
20. P19 Timing optimizer
21. P20 Gate optimizer
22. P21 Controller preservation/optimization engine
23. P22 RX/DNC protection state machine (no guessed insertions)
24. P23 Ensemble interaction engine
25. P24 Change Plan + event diff
26. P25 Structural/RX roundtrip verifier + rollback
27. P26 GUI Profile Inspector and before/after preview
28. P27 Synthetic + Factory regression suite
29. P28 Only after deterministic optimizer is stable: neural rebuild model, then new-MIDI generator.

## 16. Hard rules

- No DNA.zip dependency. No Gold requirement. No neural decision in V1.
- No `high note = RX articulation`, `low velocity = ghost`, `CC1 = DNC`, or GM drum-name guessing.
- No clamping malformed MIDI bytes into legal values for statistics.
- No one velocity curve per family, one curve per Sound, or one curve per Drum Kit.
- No uniform random humanize. Randomization is deterministic, conditional and distribution-derived.
- No automatic pitch/harmony/form changes in the optimizer.
- If the profile is weak/conflicted/special-sensitive: preserve beats guessing.

## 17. Generated research artifacts

- `factory_sound_profiles_v1.json`
- `factory_sound_profiles_v1.csv`
- `factory_drum_key_profiles_v1.json`
- `factory_drum_key_profiles_v1.csv`
- `factory_rx_profiles_v1.csv`
- `factory_family_summary_v1.csv`
- `factory_address_name_conflicts_v1.csv`
- `factory_profile_stability_v1.json`
- `factory_element_profile_stability_v1.json`
- `factory_controller_profiles.json`


## Implementation status in this bundle

- [x] Exact profile registry + identity-conflict guard
- [x] Role detection + Style Element/CV hints
- [x] Musical intent classifier
- [x] Velocity quantile-curve optimizer
- [x] Deterministic profile-derived randomize
- [x] Timing residual humanizer
- [x] Gate optimizer for safe melodic/chordal tracks
- [x] RX/special pitch protection
- [x] Controller preservation
- [x] Event-level diff report
- [x] Structural verifier
- [x] CLI + basic Tk GUI
- [x] Tests + Windows batch scripts
- [ ] Per-Sound hardware-confirmed RX/DNC trigger maps
- [ ] Physical Pa800 A/B capture oracle
- [ ] Neural rebuild/generation (future phase only)