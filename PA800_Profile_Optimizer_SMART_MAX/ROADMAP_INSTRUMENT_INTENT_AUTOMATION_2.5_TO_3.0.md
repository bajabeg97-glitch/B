# Roadmap 2.5–3.0 — Instrument Intent & Musical Automation

## Cilj

Alat ne smije samo prepoznati Sound ili porodicu. Mora odvojeno odgovoriti:

1. **Šta instrument jeste?** — tačan Pa800/GM identitet i porodica.
2. **Koju ulogu trenutno ima?** — foundation, comp, pad, riff, lead, counter,
   ornament ili FX.
3. **Šta nota ili fraza pokušava uraditi?** — anchor, passing, pickup, fill,
   accent, ghost, sustain, release, answer, swell, stab, strum ili articulacija.
4. **Šta sekcija radi?** — intro, verse/body, pre-chorus/build, chorus, bridge,
   solo, break, fill, ending ili UNKNOWN.
5. **Kako instrument djeluje na ostale?** — lock, support, call/response,
   doubling, masking, tension ili release.
6. **Šta automatika smije promijeniti?** — ništa, suggestion, safe bounded
   shaping, user-confirmed edit ili hardware-confirmed AUTO.

`Program/Bank`, naziv tracka ili velika količina Factory podataka nikada sami
ne dokazuju muzičku namjeru.

## Trenutni jaz

Postojeći analyzer već opisuje osnovne track funkcije, fraze, chord-shape,
Drum/Bass odnos, section trajectory i call-response kandidate. Postojeći
autopilot, međutim, prvenstveno bira režim iz content confidencea, exact/trusted
Factory coveragea te conflict/sensitive udjela. Roadmap zatvara upravo vezu
koja nedostaje: automation odluka mora zavisiti i od kalibrirane namjere fraze,
sekcije i ansambla, a ne samo od dostupnosti profila.

## Novi model dokaza

| Sloj | Rezultat | Minimalni dokaz | Mutacijski autoritet |
|---|---|---|---|
| I0 Identitet | Sound/family/conflict | serialized Bank/Program | samo kontekst |
| I1 Uloga | npr. LEAD ili HARMONIC_COMP | više nezavisnih strukturnih signala | analyzer/suggest |
| I2 Namjera | npr. bass approach ili drum fill | family model + fraza + sekcija | bounded shaping |
| I3 Ansambl | lock/call-response/masking | korelacija više trackova | preserve ili bounded group edit |
| I4 Automatika | konkretna dozvola po događaju | kalibriran confidence + svi guardovi | safe AUTO |
| I5 Hardware | DNC/timbar/FX rezultat | fizički Pa800 A/B | E3 AUTO koridor |

Svaki rezultat mora sadržati `label`, `confidence`, `evidence_level`,
`support`, `alternatives`, `unknown_reasons`, `protected_dependencies` i
`allowed_actions`. Confidence bez kalibracije nije autoritet.

## Kanonske uloge i namjere po instrumentu

| Porodica | Uloge | Namjere koje treba razlikovati | Automatska granica |
|---|---|---|---|
| Drum/Perc | pulse, backbeat, subdivision, fill, transition, ornament | main hit, ghost, flam, drag, pickup, fill run, crash/transition, ensemble hit | Kit+Key exact; groove fingerprint obavezan |
| Bass | foundation, riff, pedal, melodic fill | root/anchor, approach, passing, repeated, dead/mute, slide/noise, phrase release | mora čuvati Drum/Bass odnos i special pitch |
| Guitar | strum comp, arpeggio, riff, lead, texture | down/up strum, chord member, pickup, repeated riff, mute, harmonic, slide/noise | group edit; Guitar Mode/NTT nije inferiran iz SMF-a |
| Piano/EP | melody, comp, chord, arpeggio, fill | chord anchor, inner voice, pickup, cadence, grace, pedal-sustained release | chord balance i CC64 stanje obavezni |
| Organ | comp, pad, lead, stab | held chord, legato line, percussion attack, rotary gesture candidate | velocity nije glavni expression signal |
| Strings/Pad/Choir | sustain bed, swell, ostinato, accent, counter | phrase arc, swell/release, chord sustain, pizzicato candidate, ostinato pulse | simultanost, voice leading i tail zaštita |
| Brass | section, solo, stab, sustain, accent | breath attack, phrase peak/end, fall/doit candidate, ensemble stab | PB/CC1/note-off noise blokiraju generic rewrite |
| Reed/Pipe/Harmonica/Accordion | lead, counter, breath phrase, pad/comp | legato, breath pickup/release, bellows arc, key/noise candidate | monofonija i controller state moraju biti dokazani |
| Mallet/Pluck/Ethnic | transient melody, ostinato, accent, drone | transient accent, repeated cell, roll/tremolo candidate, ornament | exact-only dok nema šireg supporta |
| Synth Lead | lead, riff, texture | bend phrase, modulation arc, portamento candidate | PB/modulation contour immutable bez posebnog modela |
| SFX/Cycle/Random | effect/transition | samo opaženi event pattern; semantika UNKNOWN | trajni preserve/suggest-only bez E3 |

## Faze implementacije

### 2.5.0 — Intent Schema V3 i stress generator

- uvesti `PA800_INSTRUMENT_INTENT_V3` sa zasebnim track, phrase, note,
  section i ensemble nivoom;
- dodati `intent_id` koji se može pratiti do svake mutacijske odluke;
- napraviti deterministički generator pozitivnih, negativnih i adversarial
  MIDI/KAR fixturea iz matrice ispod;
- analyzer mora vratiti UNKNOWN kada nedostaju minimalni signali.

**PASS:** schema roundtrip, 100% event attribution, nula mutacija analyzer sloja,
isti ulaz daje byte-identičan report osim vremenskog metadata polja.

### 2.5.1 — Ground-truth uloga i kalibracija

- ručno označiti najmanje 100 Song, 100 Style i 30 KAR;
- oznake: `FOUNDATION_DRUM`, `FOUNDATION_PERC`, `FOUNDATION_BASS`,
  `HARMONIC_COMP`, `PAD_BACKGROUND`, `RIFF_OSTINATO`, `LEAD`, `COUNTER_LINE`,
  `ORNAMENT_FX`, `UNKNOWN`;
- dopustiti promjenu uloge kroz vrijeme na istom tracku;
- evaluaciju razdvojiti po porodici, sadržaju, žanru, supportu i izvoru fajla;
- split raditi po cijelom fajlu/Styleu, nikada po notama istog izvora.

**Ciljni gate:** macro-F1 ≥0,90 za foundation/background/foreground superklase,
macro-F1 ≥0,82 za fine uloge, UNKNOWN precision ≥0,95 i expected calibration
error ≤0,05. Dok gate nije postignut, uloga ostaje E1 suggestion.

### 2.5.2 — Family Intent modeli

- prioritet A: Drum, Bass, Guitar, Piano/EP;
- prioritet B: Organ, Strings/Pad/Choir, Brass, Reed/Pipe/Accordion;
- prioritet C: Mallet/Pluck/Ethnic/Synth Lead; SFX ostaje preserve;
- koristiti lokalnu frazu, metar, susjedne note, controller state, sekciju i
  odnose s drugim instrumentima;
- jedna nota može imati primarnu i alternativnu namjeru, ali samo primarna sa
  kalibriranim dokazom ulazi u automation planner.

**PASS:** per-family confusion matrix, grouped holdout, nula leakagea između
Factory varijacija istog Stylea i nula special-pitch/controller regresija.

**Lokalni 2.5.2 proxy status:** Drum/Bass/Guitar/Piano analyzer i integracija
su završeni; 38/38 real-SMF slučajeva i 19/19 adversarial parova prolazi.
Ovo je strukturni/stress PASS, ne per-family confusion-matrix PASS: ručno
označeni family ground truth i fizički Pa800 A/B još su obavezni.

### 2.5.3 — Section & Narrative V3

- Style Element/CV ostaje E2 serialized section dokaz;
- Song/KAR sekcije uče se iz promjene uloga, patterna, harmonijskog ritma,
  gustoće, markera i ponavljanja — ne samo iz velocityja;
- razlikovati build od glasnijeg istog patterna i chorus od slučajno guste
  četverotaktne sekcije;
- dozvoliti pickup, anacrusis, one-bar break i preklop prijelaza.

**Ciljni gate:** section-boundary F1 ≥0,85 sa tolerancijom ±1 takt,
macro-F1 ≥0,80 za section label i false chorus rate ≤5%.

**Lokalni 2.5.3 proxy status:** analyzer, Intent V3 integracija i quality gate
su završeni; 24/24 real-SMF slučaja i 12/12 adversarial parova prolazi.
Velocity-only granice se odbijaju, Style/marker dokaz se čuva, a overlap note
ostaju preserve. Ciljni F1 i false-chorus prag još nisu proglašeni PASS bez
ručno označenog Song/Style/KAR korpusa.

### 2.5.4 — Ensemble Intent Graph

- čvorovi su track/fraza namjere, veze su lock, support, doubling,
  call-response, masking i handoff;
- Drum/Bass, chord group, pedal/tail i expressive-controller veze postaju
  obavezni invariant prije i poslije optimizacije;
- fokus se procjenjuje po sekciji, ne jednom globalno za cijelu pjesmu.

**PASS:** ≥95% retention opaženih groove/chord/phrase fingerprinta, nula
uništenih call-response praznina i nula novog controller-state bleeda.

### 2.5.5 — Intent-Aware Automation Planner

Planner odlučuje zasebno po `track + channel + program state + section +
phrase + protected state`, ne jednom globalnom snagom.

| Rezultat | Dopuštena akcija |
|---|---|
| E0/UNKNOWN ili konflikt | preserve + objašnjenje |
| E1 uloga/namjera | suggestion/preview |
| E2 exact profil, kalibrirana namjera i svi invarianti PASS | bounded velocity/timing/gate |
| E2 dokumentovan trigger | user-confirmed artikulacija |
| E3 hardware potvrda | dozvoljeni Sound/FX/articulation AUTO koridor |

AUTO se blokira ako je alternativa namjere blizu pobjedniku, sekcija je
nepoznata, kanal mijenja Program, postoji osjetljiv controller, događaj je
RX/DNC/special-pitch ili bi edit promijenio ansamblsku korelaciju.

**PASS:** svaka primijenjena promjena ima `intent_id`, dokaz, confidence,
before/after vrijednost, authority izvor i verifier rezultat; nula implicitnih
globalnih odluka.

### 2.5.6 — Counterfactual i metamorphic stress

- transpozicija mora sačuvati ulogu i ritmičku namjeru kada porodica ostaje
  ista;
- globalna velocity promjena ne smije promijeniti section label bez drugih
  strukturnih signala;
- promjena track imena ne smije nadjačati suprotne note/controller dokaze;
- permutacija trackova i drugačiji SMF running status ne smiju mijenjati
  rezultat;
- dodavanje neaktivnog tracka, praznih meta događaja ili CC duplikata ne smije
  promijeniti namjere aktivnih nota;
- uklanjanje ključnog dokaza mora spustiti confidence ili dati UNKNOWN.

**PASS:** svi metamorphic invarianti PASS i confidence je monotono vezan za
dokaz, ne za slučajni redoslijed događaja.

### 2.5.7 — Real-Mido/Windows compatibility campaign

- najmanje 100 jedinstvenih Song, 100 Style i 30 KAR fajlova;
- Python 3.10–3.14, Windows 10/11, pravi Mido i instalirani wheel;
- usporediti analyzer report prije i poslije save/reload;
- posebno mjeriti duge fajlove, više Program stanja, Type-0/Type-1 i velike
  SysEx/meta blokove.

**PASS:** nula crasha, nula izgubljenih eventa, stabilan intent digest i svi
quality/verifier gateovi PASS.

### 2.6 — Pa800 hardware intent i DNC mapa

- svih 23 dokumentovanih DNC Soundova;
- najmanje 30 A/B po Voice familiji i FX ulozi;
- fizički potvrditi SC1/SC2, joystick, damper, aftertouch, legato, noise,
  phrase-end i note-off ponašanje;
- nijedan forumski opis ne prelazi u AUTO bez ponovljivog hardware dokaza.

**PASS:** verzioniran OS/Musical Resources/SET/audio chain, top-1 i
false-positive metričke granice te nula kritičnih playback kvarova.

### 3.0 — Hardware-Proven Musical Automation

FULL je dostignut tek kada su istovremeno zatvoreni ground truth, stress,
Windows/real-Mido, family holdout, authority ledger i Pa800 A/B gateovi.
Do tada proizvod ostaje: **razumijevanje i transparentna preporuka široko,
AUTO samo u uskim dokazanim koridorima**.

## Kanonska MIDI stress matrica

Svaki scenario mora imati pozitivnu i negativnu varijantu, očekivanu namjeru,
očekivanu automatiku i before/after fingerprint.

| ID | Scenario | Očekivani rezultat |
|---|---|---|
| INT-001 | isti Piano Sound: monofona melodija naspram blok akorda | LEAD naspram HARMONIC_COMP |
| INT-002 | isti Guitar Sound: strum, arpeggio, riff i solo u četiri sekcije | uloga se mijenja po sekciji |
| INT-003 | Bass u visokom registru, ali zaključan s kickom | FOUNDATION_BASS, ne LEAD |
| INT-004 | niska monofona melodija bez Drum odnosa | ne smije automatski postati Bass |
| INT-005 | Pad sa kratkim staccato notama | ne forsirati PAD_BACKGROUND |
| INT-006 | Lead track nazvan `PAD` | struktura mora nadjačati pogrešan naziv |
| INT-007 | Comp track nazvan `SOLO` | konflikt signala spušta confidence/UNKNOWN |
| INT-008 | jedan track mijenja Program i ulogu usred pjesme | segmentirati ili preserve cijeli kanal |
| INT-009 | isti kanal na dva tracka i isti Program | track/channel identitet ostaje odvojen |
| INT-010 | sparse track sa 1–3 note | UNKNOWN, bez AUTO |
| DRM-001 | kick/snare groove sa tihim ghost snareovima | ghost velocity i položaj sačuvani |
| DRM-002 | fill koji počinje prije granice takta | FILL/PICKUP, ne timing greška |
| DRM-003 | flam/drag note udaljene 1–6 tickova | ne kvantizirati u jedan hit |
| DRM-004 | crash na prijelazu sekcije | TRANSITION, ne slučajni accent |
| DRM-005 | drum kit na kanalu koji nije 10 | identitet iz Bank/Program, ne kanal pretpostavka |
| DRM-006 | melodic percussion na kanalu 10 | ne forsirati Drum bez identity dokaza |
| BAS-001 | root–passing–approach–root fraza | četiri različite note namjere |
| BAS-002 | ponovljen ton kao pedal naspram dead/mute kandidata | UNKNOWN bez timbralnog/hardware dokaza |
| BAS-003 | bass 20 tickova iza kicka kroz cijelu pjesmu | čuvati stabilni laid-back offset |
| BAS-004 | bass slučajno blizu jednog snarea | ne zaključiti groove lock iz jednog para |
| BAS-005 | slide/noise special pitch između root nota | note-level protected |
| GTR-001 | down-strum i up-strum sa suprotnim spreadom | smjer i relativni velocity nagib očuvani |
| GTR-002 | near-onset arpeggio iznad grupnog prozora | ne spajati u strum |
| GTR-003 | single-note riff s ponavljanjem | RIFF_OSTINATO, ne LEAD po defaultu |
| GTR-004 | RX mute/harmonic/noise note | preserve bez E3 semantike |
| PNO-001 | chord s unutrašnjom melodijskom notom | chord balance i top voice očuvani |
| PNO-002 | CC64 prelazi granicu akorda | gate/overlap računa damper state |
| PNO-003 | arpeggio razmaknut 4/8/16/32 ticka | stabilna granica chord/arpeggio klasifikacije |
| PNO-004 | grace note velocity 1 prije glavne note 127 | ne flattenirati ekstremnu ekspresiju |
| EXP-001 | Organ legato s konstantnim velocityjem | nema piano-like pumpanja |
| EXP-002 | Brass phrase s PB i CC1 pri kraju | phrase-end events potpuno očuvani |
| EXP-003 | Clarinet monofoni legato naspram kratke polifonije | nema lažnog legato triggera |
| EXP-004 | Accordion CC11/Aftertouch luk | bellows-like contour ostaje invariant |
| EXP-005 | Synth Lead PB/modulation kroz više sekcija | contour ne curi između sekcija |
| SEC-001 | chorus je gušći zbog novih slojeva, bez jačeg velocityja | CHORUS/BUILD kandidat |
| SEC-002 | ista orkestracija samo +20 velocity | ne proglasiti novu sekciju samo zbog glasnoće |
| SEC-003 | one-bar break i pickup u sljedeću sekciju | obje granice u toleranciji |
| SEC-004 | 3/4, 6/8 i promjena metra | takt/granice bez 4/4 pretpostavke |
| SEC-005 | marker kaže Chorus, struktura kaže tiha strofa | prijaviti konflikt, ne slijepo vjerovati markeru |
| ENS-001 | lead i counter se smjenjuju po taktovima | CALL_RESPONSE_CANDIDATE i prostor očuvan |
| ENS-002 | lead/counter stalno se preklapaju | COUPLED_OR_COMPETING upozorenje |
| ENS-003 | Piano i Guitar dupliraju isti voicing | DOUBLING, ne dvije nezavisne melodije |
| ENS-004 | Pad i Strings maskiraju lead samo u chorusu | section-local masking upozorenje |
| AUT-001 | visoki profile coverage, ali role confidence nizak | suggestion, bez AUTO |
| AUT-002 | visoka namjera, identity conflict | preserve |
| AUT-003 | siguran exact profil, ali aktivan CC/PB | note shaping samo ako family policy dopušta |
| AUT-004 | confidence 0,79/0,80/0,81 oko praga | bez diskontinuirane velike mutacije |
| AUT-005 | dvije skoro jednake intent alternative | UNKNOWN ili user confirm |
| AUT-006 | Vocal Friendly pogrešno prepozna comp kao lead | confidence guard sprečava preširoku zaštitu |
| AUT-007 | forced `smart apply` uz preserve odluku | materializacija ostaje suggest/preserve |
| IO-001 | Type-0 naspram ekvivalentnog Type-1 | ista semantička namjera |
| IO-002 | running status i drugačiji event ordering istog ticka | stabilan intent digest |
| IO-003 | zero-duration, overlapping same-pitch i hanging note | Doctor popravka ne mijenja dokazanu ulogu |
| IO-004 | veliki delta, 16 kanala, 100k nota | bounded memorija i determinističan rezultat |
| IO-005 | SysEx/unknown meta između controllera i note | state ne curi niti se briše |

## Obavezni izvještaji

- `INSTRUMENT_INTENT_GROUND_TRUTH.json`
- `INSTRUMENT_INTENT_METRICS.json`
- `INSTRUMENT_INTENT_STRESS_MANIFEST.json`
- `INSTRUMENT_INTENT_STRESS_RESULT.json`
- `INTENT_AUTOMATION_AUTHORITY_LEDGER.json`
- `INTENT_AUTOMATION_BEFORE_AFTER.csv`
- `PA800_INTENT_HARDWARE_CAMPAIGN.csv`

Nijedan report ne smije koristiti prazan skup kao PASS. Svaka faza završava
sa `PASS`, `FAIL`, `UNKNOWN` ili `EXTERNAL_REQUIRED`.