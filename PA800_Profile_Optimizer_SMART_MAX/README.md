# PA800 Profile Optimizer — Factory + Gold Neural Workstation

Current release: **SMART MAX 3.4.0-alpha2 — Exact Per-Instrument Neural Profiles**.

Najjednostavnije pokretanje na Windowsu:

1. raspakuj kompletan ZIP;
2. dvoklik na `INSTALL.bat` samo prvi put;
3. zatim uvijek pokreći `RUN_GUI.bat`.

GUI tab `Factory + Gold` certificira ugrađenih 252 Factory stilova i 182 Gold
MIDI izvedbe, priprema označeni combined training folder i šalje ga u tab
`Trening`. Velocity je potpuno izvan neuralnog ulaza i izlaza te ostaje pod
determinističkim instrument/role profilima.

GUI tab `Pattern Brain` prikazuje analysis-only kandidate za fill strukturu i
sadržaj, drum/bass pattern, Guitar Mode i strumming, PowerChord voicing/riff,
Brass, Strings/Pad, solo frazu, Expression CC11 i ukrase. Factory je PA800
strukturni/sigurnosni autoritet, a Gold balkanski izvedbeni dokaz. Sloj ne piše
MIDI; svaki budući apply mora proći Proposal → Policy → Simulator →
ChangeTransaction → Validation → Export.

`Pattern Brain` sada ima i poseban eksplicitni **GENERISI PATTERN IZ AKORDA**
prolaz. U tabu `Optimizer` odaberi Factory/Gold ili vlastiti provjereni MIDI
template, a u `Pattern Brain` upiši, na primjer, `C | Am | F | G7`. Generator
zadržava kompletan ritam, velocity, gate, Sound/Kit, bank/program, RX/DNC,
kontrolere, meta događaje, broj eventa i dužinu svakog tracka. Mijenja samo
pitch nezaštićenih tonalnih nota i za svaku promjenu zapisuje track/channel,
takt, izvorni i ciljni akord, instrument family i razlog.

Podržani su dur, mol, 7, maj7, m7, dim/dim7, aug, sus2/sus4, power5, slash bass
(`C/E`) i ponavljanje (`C*2`). Bass dobija root/fifth/slash-bass mapiranje,
Guitar/PowerChord čuva strum i voicing, Brass i Strings/Pad čuvaju akordske
grupe, a Solo/Lead skalu i ukrasni smjer. Drum, Perc, RX/DNC special pitch,
Guitar Mode kontrolne note, low-velocity RX triggeri i nepoznate/SFX note se
ne transponuju. Poseban pitch-only verifier blokira output ako se promijene
timing, velocity, gate, CC, Sound, struktura ili neautorizovana nota.

CLI primjer:

```bash
pa800-optimize template.mid novi_pattern.mid --content-type style --chords "C | Am | F | G7"
```

Ovaj generator ne koristi niti trenira neuronsku mrežu. Aktivni neuralni model
i dalje ostaje zaseban, ograničen isključivo na završnu timing/gate korekciju.

Plan hibridnog neuronskog MIDI restauratora i expressive performance sistema
nalazi se u `ROADMAP_NEURAL_MUSICIAN_3.1_TO_5.0.md`. Neuralni sloj je planirani
proposal/candidate sistem; postojeći deterministički safety kernel ostaje
konačni autoritet.

Deterministički MIDI optimizer za Korg Pa800 zasnovan na:

1. službenoj PA800 semantici (uređaj / RX / DNC sigurnost),
2. empirijskim Factory Performance profilima,
3. muzičkom kontekstu konkretnog MIDI-ja,
4. event-level verifieru.

Nema generičkog "AI scorea" ni neuronskog mutation authorityja. Postoji mali
proxy-trenirani encoder, ali nije produkcijski model.

## Exact profil za svaki instrument

`exact_instrument_neural_profiles_v1.json` sadrži tačno jednu Sound+role
karticu za svaki od 542 Factory profila i 23 manual-only DNC profila. Svaka
kartica nosi vlastiti dokazni vektor, family policy, protected zavisnosti,
dopuštene prijedloge i eksplicitnu granicu autoriteta.

Rezultat je 565/565 exact-resolved profila kroz 18 porodica: 85 protected,
480 suggestion-only i pet grouped-proxy profila. Produkcijski AUTO je 0.

Postojeći runtime engine primjenjuje profil po instrumentu, a ne jednu
univerzalnu korekciju. U reportu `workstation.instrument_application` za svaki
track/channel pišu izabrani Sound, family, timing/gate način, jačina, način
grupisanja, controller zaštita i Factory/Gold authority head:

| Instrument family | Timing primjena | Gate / fraza | Posebna zaštita |
|---|---|---|---|
| Drum Kit / Percussion | per-key groove i pocket | one-shot ostaje netaknut | Kit+Key profil |
| Percussive | transient pocket, repeated-hit grupa | prirodni rep ostaje | transient guard |
| Bass | veza s najbližim drum anchorom | artikulacija do sljedećeg onseta | mono-line i same-pitch guard |
| Guitar | koherentan strum ili riff | strum release | RX/DNC i special-pitch guard |
| Piano | zajednički akord ili linija | pedal-aware release | CC64 i oblik akorda |
| Accordion | bellows fraza i akordi | legato bellows | CC1/CC2/Pitch Bend |
| Harmonica | breath fraza | breath legato | CC1/CC2/Pitch Bend |
| Strings / Ensemble | vrlo blagi zajednički onset | sustain/voice-leading tail | dugi repovi i fraza |
| Choir / Voice | onset se čuva | breath/tail samo iz profila | expression controller |
| Brass | stab, akord ili breath fraza | stab naspram sustaina | CC1/PB/Aftertouch |
| Reed / Pipe | solo breath/air fraza i ukrasi | legato/breath gap | CC1/CC2/Pitch Bend |
| Organ | vrlo blagi legato ili stab | stanje legata | drawbar/controller state |
| Synth Pad | onset se čuva | vrlo blag long-tail profil | sustain layer/state |
| Synth Lead | solo, triler, mordent i grace kontekst | legato ornament | CC1/PB/Aftertouch |
| Chromatic Perc / Mallet | pitched transient/hit pattern | prirodni decay ostaje | exact-profile only |
| Pluck | linija ili arpeggio | prirodni decay ostaje | exact-profile only |
| Ethnic | samo tačan dokaz | kulturna artikulacija se čuva | special pitch/controller |
| Other / SFX / Unknown | nema generičke korekcije | potpuno očuvanje | raw-event preserve |

Velocity u svim redovima i dalje dolazi isključivo iz tačno razriješenog
Factory/Gold velocity profila. Family detalji samo određuju zaštitu/grupisanje
i audit razlog; ne proizvode novi velocity target.

```bash
python tools/build_neural_instrument_profiles.py
python tools/run_instrument_profile_certification.py
```

## Neural Dataset V2

Lossless event contract čuva raw event redoslijed, note occurrence,
track/channel, Bank/Program, metar, simultanu grupu, instrument/intent kontekst
i protected zavisnosti. Dataset Forge zatim pravi auditirane clean/corrupt i
hard-negative primjere bez dodjele mutation authorityja.

```bash
python tools/run_neural_dataset_certification.py
python tools/forge_neural_dataset.py MIDI_FOLDER --output DATASET \
  --license LICENSE_ID --provenance SOURCE_DESCRIPTION
python tools/audit_neural_dataset.py DATASET/DATASET_MANIFEST.json
```

Lokalni rezultat: 14/14 byte-identičnih roundtripova, 60 clean/corrupt
slučajeva, 26 hard negatives i šest ritam/gate defect klasa. Velocity je
isključivo profilni podatak. Source-group leakage,
protected-event promjene i izmjene originalnih MIDI-ja su nula. Ovo je
trening infrastruktura; model još nije treniran.

## Self-Supervised Music Encoder V1

Masked-event encoder više ne vidi samo tri tona. Novi kandidat koristi
hijerarhijski prikaz **cijele fraze do osam taktova**: 33 velocity-free
ulaza za lokalni notni kontekst i dodatnih 18 ulaza za položaj u frazi,
trajanje, gustoću, raspon, konturu, ponavljanje, ukrase, višeglasje, takt,
look-back/look-ahead intervale, element i CV. Sve note fraze zato dijele
informaciju o njenom punom obliku, dok globalna transpozicija ne mijenja
ritmički/performance prikaz. Postojeći prihvaćeni 33-ulazni modeli ostaju
potpuno podržani i ne moraju se ponovo trenirati; samo budući kandidati uče
novi 51-ulazni phrase-aware ugovor. Velocity ni tada nije neuralni ulaz niti
izlaz, nego ostaje isključivo pod Factory/profilnim autoritetom.

```bash
python tools/run_neural_encoder_certification.py
python tools/train_neural_encoder.py MIDI_FOLDER \
  --output models/candidates/encoder_YYYYMMDD_HHMMSS_UTC.json \
  --log-dir training_logs
```

U GUI tabu `Trening` klikni `IZABERI FOLDER`, pa `ANALIZIRAJ FOLDER`. Detaljni
GUI log prikazuje svaki prihvaćeni i odbijeni MIDI/KAR, razlog odbijanja,
SHA-256 audit identitet te train/validation/test raspored bez source-group
leakage-a. Tek kada audit prođe, pokreni `POKRENI TRENING`.
Nakon treninga nastaje samo kandidat. `AKTIVIRAJ KANDIDATA` je jedina GUI
radnja koja, nakon potvrde, mijenja aktivni model. `PREGLED MODELA` prikazuje
validation/test improvement, confidence i dozvoljene izlaze. Dugme za primjenu
ostaje zaključano dok aktivni model nema validan acceptance zapis; prihvaćen
model smije predlagati samo timing i gate, dok velocity, pitch, Voice,
Sound/Kit, articulation i FX ostaju zabranjeni.

Nezavisni neural forensic regression pokreće se sa
`python tools/run_neural_forensic_regression.py`. Za svaki certificirani MIDI
ponovo provjerava note identitet, pitch, velocity, Voice/CC/meta događaje,
akordske simultane grupe, redoslijed fraze, track-end i maksimalni timing/gate
pomak. Rezultat se zapisuje u `NEURAL_FORENSIC_REGRESSION_RESULT.json`.

Za fizičku završnicu pokreni `CREATE_HARDWARE_CAMPAIGN.bat`. Paket sadrži 383
blind A/B reda: 210 Voice, 150 FX i 23 DNC adrese. Nakon mjerenja pokreni
`EVALUATE_HARDWARE_CAMPAIGN.bat`. `FINAL_RELEASE_GATE.json` jasno razlikuje
`SOFTWARE_CERTIFIED_HARDWARE_PENDING` od `HARDWARE_CERTIFIED`; bez stvarnog
Pa800 rezultata nikada se ne dodjeljuje hardware AUTO authority.
Isti tok je dostupan direktno u GUI tabu `Hardware A/B`: kreiranje paketa,
otvaranje `RESULTS.csv`, evaluacija i prikaz završnog release statusa.

Runtime je read-only prema svim kanonskim `profiles/data/*.json` fajlovima i
aktivnom `models/encoder.json`. Optimizacija provjerava invariant prije commita
i poslije završetka; svaka neočekivana promjena se atomically vraća na tačan
početni sadržaj i obrada se prekida. Trening zapisuje samo verzionirani model-kandidat u
`models/candidates`; aktivni model se mijenja isključivo posebnim GUI dugmetom
`AKTIVIRAJ KANDIDATA` uz eksplicitnu potvrdu.
Source/epoch/evaluation napredak prikazuje se direktno u GUI-ju, a kompletan
zapis čuva se i u `training_logs`. Za eksplicitnu primjenu prvo označi MIDI
fajlove u tabu `Optimizer`, zatim klikni `PRIMIJENI NA ODABRANE MIDI` u tabu
`Trening`. Ovaj poseban prolaz mijenja bounded ritam/timing, razmak trilera i
trajanje/gate nota. Neuralne velocity i pitch predikcije se ne primjenjuju.
Factory ostaje jedini autoritet za velocity, Sound/Kit, bank/program, RX/DNC i
voice-specifične artikulacije.

Grouped holdout ima 9 train, 2 validation i 2 test source grupe. Validation
masked MSE poboljšava mean baseline 20,64%, test 33,93%, a transposition cosine
je 1,0. Model je treniran samo kao lokalni sintetički proxy:
`production_ready=false` i `authority_granted=false`.

## Potpuna biblioteka profila

`factory_profile_completeness_v1.json` sadrži 542 pune Factory kartice i 23
manual-only DNC kartice. Svaka kartica ima originalnu Factory numeriku kada
postoji, službenu Pa800 semantiku, community kandidate bez mutation autoriteta
i eksplicitna UNKNOWN polja. Pregledni izvoz je
`PROFILE_COMPLETENESS_CATALOG.csv`, a sažetak `PROFILE_COMPLETENESS_AUDIT.md`.

## Kompletni stress certifikat

`PUBLIC_API_STRESS_MANIFEST.json` trenutno inventariše 341 javnu funkciju u 108
modula. `COMPLETE_STRESS_RESULT.json` se obnavlja naredbom ispod u instaliranom
validation okruženju i release gate priznaje samo rezultat koji pokriva svih
341/341 funkcija, nema nepokrivenih funkcija i čiji pytest prolaz završi bez
greške. Neizvršene granice su eksplicitno odvojene kao CLI, GUI, release/build,
real-Mido/PC ili fizički hardware ugovori; neuspjeli ili nepotpun rezultat
ostaje jasno označen kao blokiran, nikada kao lažni PASS.

```bash
python tools/public_api_stress.py
python tools/run_complete_stress.py
```

## Instrument Intent V3

Analyzer sada povezuje identitet, track ulogu, frazu, note namjeru, sekciju i
ansamblski odnos kroz deterministički `intent_id`. Svaki rezultat sadrži
confidence, evidence, alternative, UNKNOWN razloge, protected dependencies i
dopuštene akcije. V3 ne dodjeljuje sebi mutacijski autoritet.

Kanonski paket sadrži 55 scenarija i 110 pozitivnih/negativnih MIDI fixturea:

```bash
python tools/instrument_intent_stress_midis.py
python tools/evaluate_instrument_intent_stress.py
```

Rezultat je u `INSTRUMENT_INTENT_STRESS_RESULT.json`: 110/110 PASS, svih 55
parova semantički razdvojeno, 100% note attribution i nula primijenjenih akcija.

## Specialized Family Intent V1

Drum/Percussion, Bass, Guitar i Piano/EP sada imaju note-level muzičke modele.
Oni razlikuju groove anchor/ghost/fill, foundation/passing/approach bass,
simultani ili usmjereni guitar strum te piano chord glasove, arpeggio i damper
zavisnost. Rezultat se ugrađuje u Intent V3, ali ostaje analyzer-only.

```bash
python tools/evaluate_family_intent_stress.py
```

`FAMILY_INTENT_STRESS_RESULT.json` potvrđuje 38/38 real-SMF slučajeva i 19/19
adversarial parova, sa stabilnim digestom, nula mutacija i nula AUTO autoriteta.

## Section & Narrative V3

Style Element/CV i poznati Song markeri ostaju eksplicitni dokaz. Za inferred
Song/KAR granicu traže se višestruke promjene slojeva, ritma, harmonije,
gustoće ili harmonijskog ritma. Sama promjena velocityja ne stvara novu
sekciju. Narrative opisuje BUILD, RELEASE, CONTRAST i RETURN, a note koje
prelaze boundary ostaju u preserve overlap ledgeru.

```bash
python tools/section_narrative_stress_midis.py
python tools/evaluate_section_narrative_stress.py
```

Rezultat je 24/24 real-SMF PASS i 12/12 razdvojenih adversarial parova, bez
mutacija i bez section AUTO autoriteta.

## Ground-truth kalibracija

```bash
python tools/create_instrument_intent_ground_truth.py MIDI_FOLDER --output INSTRUMENT_INTENT_GROUND_TRUTH.csv
python tools/evaluate_instrument_intent_ground_truth.py INSTRUMENT_INTENT_GROUND_TRUTH.csv
```

Evaluator računa fine-role i superclass macro-F1, UNKNOWN precision, expected
calibration error i grouped split leakage. Trenutni status je
`EXTERNAL_REQUIRED` jer projekt nema ručno označenih 100 Song + 100 Style + 30
KAR fajlova. Kalibracija nikada sama ne daje mutation authority.

## Pipeline

`MIDI -> parse -> Sound/role/context -> musical intent -> profile match -> velocity/timing/gate -> RX/DNC guard -> verifier -> output`

## Brzi start

```bat
install.bat
run.bat input.mid output.mid --mode live
```

ili:

```bash
python -m pa800_optimizer.cli input.mid output.mid --mode live --report output.report.json
```

Muzičko objašnjenje bez stvaranja izlaznog MIDI-ja:

```bash
pa800-understand song.mid --report song.music.json --markdown song.music.md
```

Ovaj analysis-only tok opisuje funkcije instrumenata, fraze, melodijski
kontur i ponovljene intervalske motive, simultane ili blisko arpeđirane
akordske oblike, bounded voice-leading, Drum/Bass odnos, call--response
kandidate, orkestracijsku gustoću, razvoj napetosti, masking rizike i granice
dokaza. Ne dodjeljuje sebi autoritet za kreativnu mutaciju.

Muzički preset umjesto tehničkih parametara:

```bash
python -m pa800_optimizer.cli song.mid out.mid --musical-preset groove_first
python -m pa800_optimizer.cli backing.mid out.mid --musical-preset vocal_backing
python -m pa800_optimizer.cli set.mid out.mid --musical-preset live_stage
python -m pa800_optimizer.cli idea.mid out.mid --musical-preset creative_preview
```

Dostupni presetovi su `original_preserve`, `natural_band`, `groove_first`,
`vocal_backing`, `live_stage` i `creative_preview`. Creative Lab proizvodi samo
audition prijedloge; ne dobija pitch/note mutation autoritet.

Sigurni SMART MAX primjeri:

```bash
# Factory preporuke bez Sound/FX mutacije (default)
python -m pa800_optimizer.cli song.mid out.mid --content-type song --smart suggest

# Eksplicitni opt-in za evidence-gated Sound/FX promjene
python -m pa800_optimizer.cli style.mid out.mid --content-type style --smart apply --mode max
```

`auto` razlikuje Style od Song sadržaja preko Element/CV/ACC oznaka.
`--smart apply` je eksplicitni opt-in; u `preserve` i `--velocity-only`
režimu primjena Sound/FX promjena je blokirana.

## Modovi

- `preserve`: byte-identičan izlaz; analiza je dozvoljena, mutacija nije
- `gentle`: nekadašnji low-strength velocity/timing/gate profilni prolaz
- `natural`: blaga korekcija prema Factory distribuciji
- `live`: srednja korekcija + kontrolisana deterministička varijacija
- `strong`: jača korekcija
- `max`: maksimalna dozvoljena profilna korekcija, ali i dalje uz zaštite

SMART politika je odvojena: `off`, `suggest` (sigurni default) ili `apply`.

## Sigurnost

- pitch se ne mijenja
- note count se ne mijenja
- tempo/time signature/markers se ne mijenjaju; program/bank se mogu mijenjati samo uz eksplicitni `--smart apply` i verifier allowlist
- RX special-pitch kandidati su zaštićeni
- vrlo niske RX velocity vrijednosti (<=20) su zaštićene po defaultu
- CC1/CC2/CC64/PB/Aftertouch se ne čiste niti generički mijenjaju
- identity conflict adrese ne dobijaju exact profile transformaciju
- output se snima u privremeni fajl, ponovo učitava i verificira, pa se MIDI i report zajedno instaliraju rollback-zaštićenim commitom
- output lock sprečava dva procesa da istovremeno obrađuju isti izlaz

## Full Note / Velocity MAX Detector

Analysis-only detector (does not modify MIDI):

```bat
detect_velocity_max.bat input.mid
```

or:

```bash
python -m pa800_optimizer.note_velocity_cli input.mid --report velocity_max.json --csv velocity_max.csv
```

For every Note-On it reports exact Sound/role/Element/CV, note name/number, metric position, musical intent, Factory profile source/support, velocity zone, estimated Factory percentile, ideal/working/contextual/raw maximum, remaining headroom, local velocity context, chord/repetition context, MIDI-127 hits, over-max flags, and RX/DNC protection state. Drum/Perc tracks use exact Kit+Key profiles when available.

## Factory ATOMIC MAX Lab

Projekt sada sadrži puni empirijski arranger research sloj iz 252 Factory Style MIDI fajla.
GUI kartica **Factory MAX Lab** prikazuje:

- Element anatomiju (Variation/Intro/Fill/Break/Ending),
- V1 -> V4 razvoj po ulozi,
- Factory technique kandidate (ghost/accent/staccato/legato/dead-mute/strum/trill/tremolo/grace),
- controller/Pitch Bend forenziku.

Runtime baza sadrži `factory_atomic_max_summary.json` i `factory_control_forensics_max.json`.
Puni research warehouse je u `research_max/`, uključujući kompresovani segment-level NDJSON, SQLite, CV kontraste, cross-role timing, pattern fingerprints i izvještaj.

### Glavno empirijsko pravilo

Factory V1->V4 se prvenstveno razvija kroz **dodavanje uloga/slojeva i veću gustinu**, ne kroz globalno povećanje velocityja. CV1/CV2 u velikom broju slučajeva čuvaju isti ritmički skeleton i Sound, pa se CV tretira kao chord/harmony kontekst iste arranger ideje, ne kao nevezan pattern.

### Granica dokaza

ATOMIC MAX pokriva sve što je objektivno vidljivo iz Factory SMF-a. Interni OSC izbor, neizvezeni NTT/Trigger/Tension parametri i tačan naziv nedokumentovane RX/DNC artikulacije ostaju `NOT_OBSERVABLE`/`PROTECTED` dok ih manual/Sound Edit/hardware ne potvrdi.

## Dependency profiles

The deterministic optimizer remains the authority and can run with only `mido`.
Optional libraries are separated so research/forensic capabilities cannot silently become required for safe MIDI processing.

- `install.bat core` — minimal deterministic runtime.
- `install.bat full` — recommended; adds NumPy/SciPy, scikit-learn, statsmodels, NetworkX, Pydantic/JSON Schema, orjson, joblib and Numba for forensic/research analysis.
- `install.bat neural` — FULL plus optional PyTorch guarded proposal layer (Python 3.10+). Neural output is not an authority and remains behind deterministic guards/verifier.
- `install.bat dev` — FULL plus pytest, Hypothesis and memory-profiler.
- plain `install.bat` defaults to `core`.
- `check_dependencies.bat` prints installed optional capabilities.

The core optimizer must never fail merely because an optional dependency is unavailable.

## GUI folder workflow

GUI now uses persistent working folders instead of manual file/output naming:

- Choose **INPUT folder** once. MIDI/KAR files are scanned automatically.
- Choose **OUTPUT folder** once. It is remembered between launches.
- Select one or multiple files and click **OPTIMIZE SELECTED**, or use **OPTIMIZE ALL**.
- Double-click a MIDI in the list to optimize the selected item(s).
- Output names are automatic: `<source>_OPTIMIZED.mid` by default.
- Existing output files are skipped unless **Dozvoli overwrite** is enabled.
- Input folder, Output folder, mode, suffix and overwrite preference are saved per Windows user.
- Processing runs in a worker thread so the GUI remains responsive during batch work.

## SMART Sound / Drum Kit / FX Intelligence

GUI SMART izbor `off/suggest/apply` upravlja konzervativnim Factory-informed slojem prije velocity/timing/gate obrade. `suggest` je default.

- Sound/Kit ranking uses exact Factory profiles, musical family, role, observed pitch/register, profile support and score margin.
- Drum Kit ranking additionally measures coverage of the actual MIDI drum keys against Factory per-key profiles.
- A Sound/Kit rewrite is allowed only for a strong same-family candidate with a sufficient margin, an unconflicted single-program track, and already-existing CC0 + CC32 + Program Change events. Missing bank/program events are never invented.
- AUTO additionally requires STRONG/GOOD support, at least five Factory Styles, STABLE/MODERATE split stability and a non-conflicting target address.
- `ACCORDION` (harmonika), `HARMONICA` (usna harmonika) and generic `REED` are separate runtime classes.
- FX intelligence covers Drum Kit/Percussion, Bass, Guitar, Piano, Organ, Accordion, Harmonica, Reed/Pipe, Strings/Ensemble, Brass, Synth Lead/Pad, Chromatic Percussion, Ethnic and SFX/Unknown.
- Existing MIDI CC91/CC93 sends can be adjusted with a bounded blend. The engine never invents undocumented Pa800 SysEx or claims a guessed insert/master routing as hardware fact.
- The JSON report records current Sound, proposed Sound/Kit, score, margin, confidence, action, apply status, FX send changes, FX chain recommendation, delay hint and Pa800 routing hint for every track/channel.

This layer remains subordinate to RX/DNC protection and the semantic verifier.

## Real PC validation 0.3

Pokreni `VALIDATE_ON_PC.bat`. Skripta instalira mali `validation` profil i
generiše `validation_results/SEND_ME_PA800_VALIDATION_*.zip`. Provjerava stvarni
Mido, svih 48 testova, wheel/package-data, Tkinter, deterministički output,
Style/Song evidence, rollback, output lock i 2.400-note stress slučaj.

Folder sa svojim MIDI/KAR fajlovima možeš prevući na BAT. Originali se ne
mijenjaju, a MIDI sadržaj se ne stavlja u ZIP za slanje. Fizički Pa800 se testira
prema `HARDWARE_PA800_AB_TEST.md` i CSV obrascu.

## Verifier i release integritet 0.3

Verifier kontroliše note-on/off pairing, pozitivna trajanja, note/pitch count,
track end, nepromjenjive meta/controller/SysEx događaje, Bank/Program strukturu
i eksplicitni Sound/FX allowlist. Factory velocity-semantics v2 se koristi u
runtimeu i učitava lazy.

`python tools/release_audit.py --write-manifest` provjerava obavezne Factory
artefakte i zapisuje SHA-256 hash manifest. `CreateBaza.bat` regeneriše bazne
profile i ATOMIC MAX runtime/research sloj.

Windows release sadrži `PA800_FACTORY_DATA_BUNDLE.zip` sa zasebnim hash
manifestom. `ENSURE_FACTORY_DATA.bat` prije GUI/CLI rada provjerava Factory
podatke i po potrebi ih atomically obnavlja iz tog ugrađenog bundle-a; ručno
kopiranje izvornog ZIP-a nije dio normalnog korisničkog workflowa.

## AI Resource Brain (BAJA MAX add-on)

The optimizer now includes `pa800_optimizer/ai_brain.py`, a central compute governor that detects CPU/RAM, scores each MIDI workload, caps scientific/neural threads, and can defer optional neural timing/gate inference under memory pressure while keeping deterministic Factory/Gold processing active. See `AI_BRAIN_RESOURCE_MANAGER.md`.
