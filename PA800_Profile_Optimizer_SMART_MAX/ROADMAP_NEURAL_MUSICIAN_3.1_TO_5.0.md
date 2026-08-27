# Roadmap 3.1–5.0 — Neural Musician za popravku i muzikalnu izvedbu MIDI-ja

## Vizija

Konačni proizvod nije generator koji zamijeni pjesmu svojom verzijom. To je
**neuronski muzičar, aranžer i MIDI restaurator** koji:

1. razumije šta je autor svirao i šta je pokušao postići;
2. nalazi stvarni kvar, robotizaciju ili konflikt;
3. predlaže najmanju muzikalno opravdanu promjenu;
4. pokazuje šta bi promijenio i zašto;
5. dopušta A/B slušanje i prihvatanje po noti, frazi, tracku ili sekciji;
6. nikada ne dobija direktan pristup izlaznom MIDI-ju mimo postojećeg
   authority ledgera, event-level verifiera i Pa800 zaštita.

Osnovna arhitektura zato ostaje hibridna:

```text
Original MIDI
    ↓
Deterministički parser + Doctor + identitet + protected-state ledger
    ↓
Neural Understanding Plane
    ├── note/phrase/section/track embeddings
    ├── corruption probability
    ├── musical intent and uncertainty
    └── ensemble relationship graph
    ↓
Neural Proposal Plane — proizvodi k kandidata, nikada finalni fajl
    ├── repair delta
    ├── expressive performance delta
    ├── orchestration/mix suggestion
    └── creative inpainting preview
    ↓
Deterministički Constraint Projector
    ├── pitch/note-count/controller/RX/DNC/Style ugovori
    ├── groove, chord, phrase, sustain i ensemble fingerprints
    └── evidence + confidence + user authority
    ↓
Event-level verifier + save/reload + hardware gate
    ↓
Prihvaćeni MIDI + potpuni before/after izvještaj
```

## Odgovor na pitanje „je li sadašnji sistem maksimum?”

Nije. Verzija 2.5.3 je maksimum determinističkog lokalnog analyzera bez
stvarnog označenog korpusa i bez fizičkih Pa800 rezultata. Ona zna zaštititi,
izmjeriti i objasniti mnogo toga, ali još ne može pouzdano naučiti:

- zašto dva tačno odsvirana takta ipak zvuče različito muzikalno;
- koliko ista fraza treba kasniti ili žuriti u konkretnom grooveu;
- kako se velocity luk ponaša kroz cijelu rečenicu, ne samo po Sound profilu;
- kada je kratka nota namjerna artikulacija, a kada greška;
- kako se bass, kick, piano, guitar i vocal prostor međusobno pregovaraju;
- lični touch konkretnog svirača;
- koji od više tehnički ispravnih rezultata muzičar stvarno preferira.

Neuronska mreža može naučiti te odnose, ali samo ako se uvede kao **proposal
model sa kalibriranom nesigurnošću**, a ne kao novi skriveni autoritet.

## Muzičarski zahtjevi koji upravljaju cijelim dizajnom

### 1. Ne diraj ono što već svira dobro

- očuvati ritmički potpis i stabilni laid-back/ahead osjećaj;
- očuvati relativni velocity unutar akorda i struma;
- očuvati sustain, overlap, legato i phrase tail;
- očuvati PB, Aftertouch i sve postojeće CC konture;
- RX/DNC, special-pitch, noise, cycle, random i SFX tretirati kao zaključane;
- svaka neuronska promjena mora imati lokalni razlog, ne samo „model score”.

### 2. Popravi izvedbu, ne kompoziciju

Prva produkcijska neuronska verzija smije mijenjati samo:

- velocity delta;
- onset delta unutar tvrdog, instrument-specifičnog prozora;
- note-off/gate delta uz sustain i legato state;
- postojeći CC91/93 bounded offset ako deterministički FX gate to dopušta;
- dokumentovane, korisnički potvrđene artikulacije.

Pitch, nova nota, brisanje note, harmonijska zamjena, novi controller i
Sound/FX rewrite ostaju zaključani dok posebna kasnija faza ne dokaže svaki
takav koridor.

### 3. Muzičar mora imati zadnju riječ

- `Repair only` — samo dokazivi kvarovi;
- `Natural performance` — fraziranje i dinamika bez promjene karaktera;
- `Groove lock` — čuva namjerni Drum/Bass osjećaj;
- `Vocal space` — smanjuje konflikt sa vokalom bez „ubijanja” benda;
- `Live stage` — konzervativan, stabilan i predvidiv izlaz;
- `Creative alternatives` — tri preview kandidata, nikad automatski commit;
- `Learn my touch` — privatni adapter iz korisnikovih prihvaćenih odluka.

## Pet razdvojenih neuronskih zadataka

Jedan veliki model ne smije istovremeno glumiti detektor, aranžera i verifier.
Sistem se dijeli na pet modela sa odvojenim metrikama i autoritetom.

### A. Neural Music Understanding Encoder

Ulaz: dvije sinhronizovane reprezentacije istog MIDI-ja.

1. **Strukturni pogled:** takt, beat, pozicija, pitch, trajanje, instrument,
   uloga, sekcija, akordni oblik i track veza.
2. **Performance residual pogled:** velocity, mikro-timing, gate, pedal,
   controllere i odstupanje od lokalnog patterna.

Izlaz:

- embedding po noti, frazi, sekciji, tracku i cijeloj pjesmi;
- fine-role i family-intent distribucija;
- section i narrative distribucija;
- OOD/UNKNOWN procjena;
- alternativna interpretacija i kalibrirana vjerovatnoća.

Predložena osnova je hijerarhijski Transformer sa bar/section summary tokenima
i relativnom metričkom pozicijom. Simultane note, sustain i voice-leading veze
dodatno ulaze kroz mali graph encoder. Time linearni MIDI tokeni ne moraju sami
otkrivati da akordne note postoje istovremeno.

### B. Corruption & Repair Network

Ovo je prvi model koji smije doći blizu AUTO režima. Uči razliku između
namjerne izvedbe i oštećenja:

- missing/stuck note-off;
- note-on velocity 0 i neusklađeni parovi;
- duplikat ili slučajni very-short hit;
- nenamjerni ekstrem velocityja;
- robotizovana flat-velocity dionica;
- timing spike u inače stabilnom patternu;
- gate spike koji prekida legato ili pad tail;
- controller state bleed;
- pogrešno postavljen Program/Bank događaj;
- lokalni groove outlier, ali ne stabilni laid-back offset.

Model vraća `corruption_type`, `probability`, `counterfactual_without_repair`,
`candidate_delta` i `uncertainty`. Deterministički Doctor i dalje odlučuje je
li promjena legalna.

### C. Expressive Performance Renderer

Ne generira note. Za postojeće, otključane note predviđa distribuciju:

```text
Δvelocity, Δonset, Δgate, phrase_arc, articulation_class
```

Predikcija je hijerarhijska:

- note head vidi lokalni attack i susjedne note;
- chord/strum head daje jedan zajednički group delta;
- phrase head daje luk i disanje;
- section head daje build/release kontekst;
- ensemble head ograničava rezultat prema drugim instrumentima.

Model mora vratiti više kandidata. Medijan nije uvijek najmuzikalniji rezultat,
pa korisnik dobija `Tight`, `Natural` i `Expressive` A/B varijantu unutar istog
sigurnog koridora.

### D. Ensemble Intent Graph Network

Čvorovi su note-grupe, fraze, trackovi i sekcije. Veze uključuju:

- Drum↔Bass lock i stabilni offset;
- chord simultanost i voice-leading;
- Guitar/Piano rhythmic support;
- doubling i unison;
- call-response i foreground handoff;
- pedal/tail zavisnost;
- register/density masking;
- shared accent i ensemble hit;
- controller-state zavisnost.

Graph model ne predlaže edit pojedinačno. Vraća grupni constraint i označava
koje bi druge događaje izolirana promjena oštetila.

### E. Controlled Inpainting & Creative Model

Najkasnija i najrestriktivnija faza. Koristi masked infilling ili diffusion za:

- nedostajući dio accompanimenta;
- alternativni fill;
- varijaciju postojeće fraze;
- smireniju vocal-backing verziju;
- novu orkestracijsku ideju sa zaključanom melodijom i harmonijom.

Sve je preview-only. Model radi nad kopijom i mora poštovati eksplicitnu masku:
šta je zaključano, šta smije mijenjati i koliko daleko smije odstupiti.

## Reprezentacija — PA800 Neural Event Contract

Neuronski token ne smije izgubiti nijedan važan MIDI ili Pa800 identitet.

### Strukturni token

```text
BAR, POSITION, TRACK, CHANNEL, BANK_MSB, BANK_LSB, PROGRAM,
FAMILY, SERIALIZED_ROLE, SECTION, PHRASE, PITCH, DURATION,
CHORD_GROUP, VOICE_INDEX, INTENT, PROTECTED_STATE
```

### Performance token

```text
VELOCITY, ONSET_RESIDUAL, GATE_RESIDUAL, PEDAL_STATE,
CC1, CC2, CC64, CC80, CC81, PITCH_BEND, AFTERTOUCH,
RX_DNC_FLAG, SPECIAL_PITCH_FLAG
```

### Obavezna pravila tokenizacije

- bar/beat/position je eksplicitan, ne zaključuje se samo iz redoslijeda;
- track i channel ostaju odvojeni;
- svaka Program promjena otvara novi program-state segment;
- simultane note dobijaju group ID i voice index;
- note-on/off se čuvaju u raw event ledgeru za tačan roundtrip;
- nepoznati događaj dobija `UNKNOWN_RAW_PRESERVE`, ne odbacuje se;
- trening može koristiti transpoziciju samo ako Sound range, special pitch i
  harmonska oznaka ostanu legalni;
- performance residual se uči odvojeno od kompozicijskog sadržaja.

## Podaci i dokazni slojevi

### D0 — postojeći deterministički dokaz

- 252 Factory Style MIDI fajla;
- 1.430.602 validna Note-On atoma;
- 542 Sound profila, 2.004 Kit+Key profila i 565 evidence kartica;
- postojeći Intent, Family, Section, fingerprint i authority izvještaji.

Ovo je dovoljno za self-supervised pretraining i sintetičke corruption testove,
ali nije dovoljno za tvrdnju da je naučena ljudska preferencija.

### D1 — Synthetic Repair Curriculum

Iz čistog MIDI-ja deterministički se stvaraju poznata oštećenja:

- timing outlier;
- velocity spike/flattening;
- gate truncation/overlap;
- controller bleed;
- dropped ili duplicated event;
- Program-state konflikt;
- quantization robotization;
- uništen strum smjer;
- uništen chord balance;
- pomjeren fill ili pickup.

Za svaki primjer postoji tačan clean target i corruption maska. Split mora biti
po izvornom Style/Song fingerprintu, nikada po izvedenim segmentima.

### D2 — Licensed/Public Symbolic Pretraining

Cilj je najmanje:

- 10.000 jedinstvenih multitrack kompozicija za prvi ozbiljan encoder;
- 1.000.000 taktova nakon deduplikacije;
- odvojeni piano-performance i band/arranger korpusi;
- jasna licenca i provenance za svaki fajl;
- fingerprint deduplikacija transponovanih i preimenovanih kopija.

Javni korpus služi učenju opće muzičke strukture. Ne daje Pa800 Sound/DNC
autoritet.

### D3 — Pa800 Performance Pairs

Najvrijedniji budući podatak nije još jedan slučajni MIDI, nego par:

```text
izvorna/kvantizovana dionica → muzičarova popravljena izvedba
```

Za svaki par čuvati:

- original i target;
- identitet muzičara bez javnog otkrivanja;
- žanr, tempo, metar, instrument i ulogu;
- reason codes po promjeni;
- prihvaćene i odbijene neuralne prijedloge;
- Pa800 OS, Musical Resources, SET i audio-chain identitet;
- dozvolu za trening, samo evaluaciju ili lokalnu privatnu upotrebu.

### D4 — Human Preference & Hardware Evidence

- blind A/B/C između originala, determinističkog i neuralnog prijedloga;
- najmanje tri ocjenjivača za release-kritične koridore;
- fizički Pa800 render i loudness-matched audio;
- preference, non-inferiority, groove, naturalness, vocal space i artifact score;
- svih 23 DNC Soundova ostaju zaseban E3 program.

## Trening ciljevi

Ukupan loss nije jedna vrijednost. Svaki head ima zaseban izvještaj:

```text
L = L_masked_event
  + L_bar_and_section
  + L_intent_calibration
  + L_corruption_detection
  + L_delta_likelihood
  + L_graph_relations
  + L_invariance
  + L_rule_violation
  + L_preference
```

### Obavezni invariance lossovi

- promjena track imena ne mijenja strukturu ako note dokazi ostanu isti;
- permutacija trackova ne mijenja rezultat;
- drugačiji running status ili delta encoding ne mijenja rezultat;
- globalna velocity promjena ne mijenja section boundary;
- legalna transpozicija čuva ritmičku ulogu;
- dodavanje praznog tracka ne mijenja aktivne namjere;
- uklanjanje dokaza mora smanjiti confidence;
- protected događaj uvijek dobija nulti mutacijski delta.

## Faze implementacije

### 3.1 — Neural Data Contract & Dataset Forge

Isporučiti:

- verzionirani token schema i raw-event roundtrip;
- dataset manifest sa SHA-256, licencom i source-group ID-em;
- synthetic corruption generator;
- deduplikaciju i leakage audit;
- train/validation/test split po cijelom izvornom fajlu;
- dataset card i privacy policy.

**PASS:** 100% raw-event attribution, byte-identičan decode kada nema edita,
nula split leakagea i reproducibilan dataset digest.

**Lokalni status 3.1:** lossless contract i byte-identični roundtrip su
implementirani; svaki neuronski izlaz ostaje bez mutation authorityja.

### 3.2 — Neural Dataset V2

Proširiti synthetic curriculum na muzički smislene i auditirane primjere:

- velocity spike i flatten;
- onset spike i progresivni groove drift;
- gate truncation i gate overlap;
- duplicate hit;
- chord desync;
- protected događaj kao hard-negative `PRESERVE`, ne kao target;
- obavezni license/provenance za TRAINING skup;
- byte dedup i transposition-invariant source-group split.

**Lokalni status 3.2:** 14/14 byte-identičnih roundtripova, 60 clean/corrupt
slučajeva, 26 hard negatives, šest ritam/gate defect klasa, bez neuronskog
velocity ulaza ili izlaza, nula group leakagea i nula
promjena originala. Ovo je kanonski stress curriculum; realni licencirani
korpus i dalje je `EXTERNAL_REQUIRED`.

### 3.3 — Self-Supervised Music Understanding Encoder

Pretraining zadaci:

- maskirane note, trajanje, instrument i bar pozicija;
- maskirani cijeli takt i track segment;
- predikcija sljedećeg section embeddinga;
- contrastive matching transponovane/legalno ekvivalentne verzije;
- note↔phrase↔section↔song hijerarhijska rekonstrukcija;
- graph edge prediction za simultanost, sustain i voice-leading.

**PASS:** poboljšanje nad postojećim determinističkim feature baselineom na
intent/section/relationship zadacima, ECE ≤0,05 i UNKNOWN precision ≥0,95.

**Lokalni proxy status 3.3:** masked-event encoder sa 24 hidden dimenzije i
450 epoha prolazi deterministički trening. Source-group split je 9/2/2;
validation/test masked reconstruction poboljšanje nad mean baselineom je
20,64%/33,93%, a transposition cosine 1,0. Intent/section F1, ECE i UNKNOWN
precision ostaju otvoreni do velikog licenciranog i označenog korpusa.

### 3.4 — Exact Per-Instrument Neural Profiles

Svaki poznati Factory ili manual-only Sound dobija vlastitu Sound+role karticu,
ne samo zajednički family preset. Kartica spaja 12-dimenzionalni empirijski
vektor, family head/policy, support, stabilnost, protected controllere,
manualne DNC granice i dozvoljene prijedloge.

**Lokalni status 3.4:** 565/565 profila se exact razrješava kroz 18 porodica.
Osamdeset pet profila je protected, 480 suggestion-only, pet ima postojeći
grouped-proxy dokaz, a produkcijski AUTO ostaje 0. Stvarni per-instrument
embedding zahtijeva licencirane izvedbene parove i fizički Pa800 A/B.

**PASS:** jedinstven profile ID i resolver za svaku karticu, nula izmišljenih
embeddinga, nula family fallback AUTO odluka i nula promijenjenih protected
događaja.

### 3.5 — Neural Corruption Detector

Prvo se trenira samo klasifikacija i lokalizacija kvara, bez editovanja.

**PASS:** recall ≥0,98 za sintetičke kritične kvarove, precision ≥0,995 za
AUTO-eligible klasu i nula označenih RX/DNC/protected događaja kao repair.

### 3.6 — Repair Delta Model

Predviđa bounded delta samo na događajima koje je detector označio. Izlaz je
distribucija, ne jedna prisilna vrijednost.

**PASS:** ≥99% vraćenih sintetičkih targeta unutar propisane tolerancije,
0 note-count/pitch/controller regresija i deterministički projector PASS.

### 3.7 — Family Expressive Renderers

Redoslijed:

1. Drum/Bass groove;
2. Piano/EP chord, melody i pedal;
3. Guitar strum, arpeggio i riff;
4. Strings/Pad/Choir phrase arc;
5. Brass/Reed/Pipe/Accordion breath phrase;
6. Organ;
7. rare family suggestion-only.

Svaka porodica dobija zaseban head, loss, holdout i model card.

**PASS:** ≥97% groove/chord/phrase fingerprint retention, nula protected
regresija i blind A/B non-inferiority prije bilo kakvog AUTO statusa.

### 3.8 — Neural Ensemble Graph

Uči odnose među trackovima i označava grupu koju edit mora sačuvati.

**PASS:** edge macro-F1 ≥0,85, Drum/Bass lock i chord simultanost retention
≥0,97, call-response gap retention ≥0,95 i controller bleed 0.

### 3.9 — Section-Conditioned Performance

Renderer dobija section/narrative embedding, ali section model još nema
mutacijski autoritet. Razlikuje isti pattern u verseu, buildu i chorusu bez
globalnog velocity pumpanja.

**PASS:** section boundary F1 ≥0,85, label macro-F1 ≥0,80, false chorus ≤5%
i nula section promjene kada je jedini signal globalni velocity.

### 3.10 — Neural Proposal API V1

Standardni izlaz:

```json
{
  "proposal_id": "...",
  "model_id": "...",
  "event_key": [0, 1, 1536, 60, 0],
  "task": "velocity_delta",
  "distribution": {"p10": -2, "p50": 1, "p90": 4},
  "confidence": 0.91,
  "uncertainty": 0.09,
  "evidence": ["phrase_arc", "family_head", "section_context"],
  "protected_dependencies": [],
  "requested_action": "SUGGEST",
  "authority_granted": false
}
```

**PASS:** schema/ledger roundtrip, nula skrivenih primijenjenih promjena i svaki
proposal se može reproducirati iz model/dataset/config digesta.

### 3.11 — Musician A/B Lab

GUI mora nuditi:

- original + tri kandidata;
- solo/mute i loop po frazi;
- heatmap promjena;
- razlog i confidence;
- `accept`, `reject`, `less`, `more`, `keep my groove`;
- lock po tracku, sekciji, controlleru i note grupi;
- instant rollback;
- preference zapis bez privatnog MIDI sadržaja po defaultu.

**PASS:** korisnik može završiti cijeli proces bez gledanja tehničkih tickova,
a audit i dalje može rekonstruisati svaku odluku.

### 3.12 — Preference Model & Personal Touch Adapter

Globalni model nikada ne uči direktno iz jednog korisnika. Lični ukus ide u
mali lokalni adapter:

- preferirani groove offset;
- velocity range i phrase arc;
- strum spread;
- pedal i legato navike;
- live-stage konzervativnost;
- prihvaćeni/odbijeni prijedlozi.

Adapter mora biti izbrisiv, prenosiv i po defaultu lokalni.

**PASS:** poboljšanje preference rezultata na holdoutu istog korisnika bez
pogoršanja safety metrika i bez miješanja podataka drugih korisnika.

### 4.0 — Neural Copilot Release

Dozvoljeno:

- analiza;
- repair suggestion;
- tri expressive previewa;
- user-confirmed bounded velocity/timing/gate;
- potpuni audit.

Nije dozvoljeno:

- pitch/note generation u glavnom fajlu;
- Sound/FX/DNC AUTO;
- edit bez prikazanog confidencea;
- cloud upload bez eksplicitne dozvole;
- model update koji nema regression i A/B rezultat.

### 4.1 — Selective Safe AUTO

AUTO se otvara samo za kalibrirane klase gdje model može odbiti odluku.

Minimalni uslov po klasi:

- precision ≥0,995;
- selective coverage se objavljuje, ne skriva;
- ECE ≤0,03;
- nula kritičnih regression kvarova;
- deterministic projector i verifier 100% PASS;
- blind A/B non-inferiority;
- tačan model, dataset i build ID.

### 4.2 — Pa800 Neural Hardware Adapter

Uči razliku između simboličkog prijedloga i onoga što se čuje na fizičkom
Pa800, ali ne pokušava rekonstruisati nedokumentovani oscillator state.

- timbral preference ostaje ranking, ne direktni MIDI rewrite;
- DNC triggeri samo iz dokumentovanog + hardware-confirmed registra;
- Sound/FX prijedlozi imaju audio A/B dokaz;
- Insert/Master ostaje recommendation-only dok serialization nije dokazana.

### 4.3 — Live Neural Assistant

Poseban mali model, ne puni offline renderer:

- radi unaprijed ili sa strogo ograničenom latencijom;
- ne mijenja već emitovan događaj;
- failover na original stream;
- bez generativnog pitcha;
- CPU-safe model i memorijski limit;
- watchdog, timeout i bypass tipka.

**PASS:** p99 latencija unutar unaprijed zadanog live budžeta, nula stuck nota,
nula event loss i trenutni bypass na original.

### 4.4 — Controlled Creative Inpainting

Tek nakon stabilnog Copilota:

- korisnik crta tačnu masku;
- melodija, bass, akordi, ritam ili instrument mogu se zasebno zaključati;
- model vraća 3–8 kandidata;
- similarity/copy-risk audit;
- rezultat nikada ne zamjenjuje original bez potvrde.

### 5.0 — Hardware-Proven Neural Musician

FULL status zahtijeva istovremeno:

- dataset provenance i leakage PASS;
- razumijevanje, repair, family, section i ensemble ground truth PASS;
- neural uncertainty i selective-risk PASS;
- svaki AUTO koridor zasebno kalibriran;
- Windows 10/11 i Python 3.10–3.14 matrix;
- pravi Mido wheel i clean-machine installer;
- 100+ Song, 100+ Style i 30+ KAR compatibility;
- fizički Pa800 A/B za sve hardware-zavisne odluke;
- model card, data card, build ID i reproducibilan inference;
- potpuna mogućnost rada bez neuralnog paketa u determinističkom preserve modu.

## Stress test program

### Neural corruption matrica

Za svaku porodicu i svaku corruption klasu generisati najmanje:

- 100 pozitivnih slučajeva;
- 100 teških negativnih slučajeva koji izgledaju slično, ali su namjerni;
- minimalni i maksimalni tempo;
- 2/4, 3/4, 4/4, 6/8 i promjenu metra;
- note 0/127 i velocity 1/127;
- svih 16 kanala;
- Type-0 i Type-1;
- više Program stanja;
- controller, PB, Aftertouch i sustain kombinacije;
- RX/DNC/SFX/protected varijantu;
- transpoziciju, track permutaciju i serialization ekvivalent.

### Muzički negativni testovi

Model mora odbiti „popravku” kada je u pitanju:

- stabilan laid-back bass;
- flam ili drag;
- namjeran grace note;
- ghost note;
- rubato;
- syncopation;
- strum spread;
- breath pickup;
- pad tail;
- pedal overlap;
- phrase-end ritardando;
- nagli accent ili subito dinamika;
- one-bar break;
- polymeter/polyrhythm kandidat;
- special-pitch artikulacija.

### Metamorphic testovi

- isti MIDI nakon save/reload mora dati isti proposal digest;
- seed mora biti eksplicitan;
- batch redoslijed ne mijenja rezultat;
- CPU/GPU numerička tolerancija je verzionirana;
- model ne smije zavisiti od imena fajla;
- prazni meta događaji ne mijenjaju aktivne note;
- uklanjanje dokaza spušta confidence;
- zaključana nota uvijek dobija delta 0;
- preserve bez neuralnog paketa ostaje byte-identičan.

### Adversarial testovi

- pogrešan track naziv;
- GM instrument sa Pa800-like nazivom;
- kanal 10 koji nije Drum i Drum koji nije kanal 10;
- zlonamjerni ili slučajni marker;
- ekstremno gust MIDI;
- dugi SysEx/meta blok;
- duplikat trening fajla u drugoj transpoziciji;
- OOD žanr i nepoznat instrument;
- model sa previsokim confidenceom;
- corrupted checkpoint ili pogrešan model ID.

## Metrike koje muzičar stvarno osjeti

Tehnički accuracy nije dovoljan. Release dashboard mora prikazati:

| Dimenzija | Mjera |
|---|---|
| Integritet | note/event/controller count, stuck notes, roundtrip |
| Groove | onset fingerprint retention, stable offset retention |
| Akord/strum | simultanost, smjer, spread i relative velocity retention |
| Fraza | phrase-arc correlation, breath/pickup/release retention |
| Sustain | pedal-aware overlap i tail retention |
| Ansambl | lock/support/call-response/masking edge retention |
| Kalibracija | ECE, selective risk, UNKNOWN precision |
| Repair | precision, recall, false repair rate po corruption klasi |
| Preferencija | blind A/B preference i non-inferiority |
| Hardware | Pa800 artifact, mud, timbre i playback failure rate |
| Latencija | p50/p95/p99 inference i peak memory |

Macro prosjek je obavezan. Grand Piano, dominantan žanr ili jedan veliki
korpus ne smiju sakriti loš rezultat rijetke porodice.

## Model i compute profili

### Lite

- mali encoder/detector;
- CPU inference;
- analiza i repair detection;
- bez generativnog modela;
- cilj za standardni Windows laptop.

### Studio

- hijerarhijski encoder + family rendereri + ensemble graph;
- GPU opcionalan, CPU fallback;
- tri bounded performance prijedloga;
- lokalni preference adapter.

### Research

- masked infilling/diffusion;
- trening, ablation i large-corpus evaluacija;
- nikada obavezan za core optimizer.

Core `preserve` i deterministički safety moraju ostati funkcionalni samo sa
Mido paketom. Neural dependency ne smije postati uslov za otvaranje ili sigurno
čuvanje MIDI fajla.

## Sigurnost, privatnost i autorski rizik

- svaki dataset fajl ima licencu i provenance;
- privatni korisnički MIDI je opt-in i odvojen od javnog modela;
- telemetry po defaultu ne sadrži MIDI note;
- preference adapter je lokalno šifriran ili ga korisnik može potpuno izbrisati;
- model release sadrži training-data statement;
- nearest-neighbor/copy-risk audit za kreativne izlaze;
- nema automatskog uploada originala, outputa ili audio A/B fajla;
- checkpoint se učitava samo uz potpis/hash i kompatibilan schema/build ID.

## Failure policy

Neuralni sloj pada u `PRESERVE` ako:

- model ili tokenizer verzija nije tačna;
- ulaz je OOD;
- confidence nije kalibriran;
- alternative su preblizu;
- protected state nije potpuno poznat;
- event map nije 100%;
- projector ili verifier pada;
- model i deterministic intent se kritično ne slažu;
- hardware-zavisna odluka nema E3 dokaz;
- korisnik nije dozvolio traženu klasu promjene.

## Istraživačka osnova arhitekture

- Music Transformer — relative attention i dugoročna struktura, arXiv:1809.04281.
- Pop Music Transformer / REMI — eksplicitni beat/bar događaji,
  arXiv:2002.00212.
- MusicBERT — OctupleMIDI i bar-level masking, arXiv:2106.05630.
- Museformer — fine/coarse attention za duge strukture, arXiv:2210.10349.
- Multitrack Music Transformer — sažet multitrack zapis i brži inference,
  arXiv:2207.06983.
- Graph Neural Network for Music Score Data — simultane i trajne note kao graf,
  ICML/PMLR 97, 2019.
- MAESTRO — precizno usklađen expressive MIDI/audio korpus,
  arXiv:1810.12247.
- DExter — diffusion expressive performance rendering,
  arXiv:2406.14850.
- Symbolic Music Generation with Non-Differentiable Rule Guided Diffusion —
  neuralni prijedlog vođen simboličkim pravilima, arXiv:2402.14285.
- MMM — track/bar-level multitrack infilling, arXiv:2008.06048.

Ovi radovi su arhitektonska inspiracija, ne dokaz da je konkretan Pa800 model
završen. Svaka tvrdnja o ovom proizvodu mora dolaziti iz njegovog vlastitog
dataset, stress, ground-truth, Windows i hardware audita.

## Praktični redoslijed od sljedećeg commita

1. zaključati `PA800_NEURAL_EVENT_CONTRACT_V1`;
2. napisati synthetic corruption generator i clean/corrupt pair manifest;
3. napraviti leakage/dedup auditor;
4. trenirati mali understanding encoder bez ikakvog edit authorityja;
5. dodati corruption detector i samo report;
6. tek nakon precision gatea dodati bounded repair proposal;
7. uvesti Musician A/B Lab;
8. skupljati prihvaćene/odbijene odluke uz opt-in;
9. trenirati family expressive heads;
10. dodati ensemble graph;
11. otvoriti user-confirmed neural shaping;
12. otvoriti uski selective AUTO samo za zasebno dokazane repair klase;
13. kreativni inpainting ostaviti posljednji i trajno preview-first.

## Završna produktna definicija

Najbolja verzija ovog alata ne govori:

> „Optimizovao sam 12.438 događaja.”

Ona govori:

> „Našao sam dvije vjerovatne greške i tri mjesta gdje izvedba zvuči
> mehanički. Groove, akordi, pedal, artikulacije i tvoj timing potpis ostali su
> zaključani. Evo tri muzikalne varijante; poslušaj ih i izaberi.”

To je cilj Neural Musiciana: **manje promjena, bolji razlog, više muzike i
potpuna kontrola muzičara.**
