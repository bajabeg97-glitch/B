# PA800 SMART MAX — FULL roadmap 2.2 → 3.0

## Definicija FULL

`FULL` ne znači da svaka Factory statistika mora proizvesti MIDI promjenu. FULL znači da je svaki raspoloživi dokaz:

1. indeksiran i izmjeren;
2. spojen sa odgovarajućim runtime modulom ili eksplicitno označen kao research-only;
3. ograničen E0–E3 autoritetom;
4. verifikovan na softveru;
5. fizički potvrđen kada odluka zavisi od zvuka Pa800.

Detaljni plan za prepoznavanje namjere instrumenata, section-aware automatiku
i kanonske adversarial MIDI testove nalazi se u
`ROADMAP_INSTRUMENT_INTENT_AUTOMATION_2.5_TO_3.0.md`.

## Trenutna tačka — 3.4.0-alpha1 Exact Per-Instrument Neural Profiles

- 252/252 Factory Style fajlova analizirano.
- 1.430.602 validna Note-On atoma.
- 542 Sound, 2.004 Kit+Key i 7.414 contextual velocity profila.
- 315/315 lokalnih regression testova preko ugrađenog standard-SMF subset
  backenda; stvarni Mido/Windows prolaz ostaje obavezan.
- 315 javnih funkcija u 99 modula su inventarisane; 254 su stvarno izvršene
  kroz puni release trag, svih 315 ima dokazivu coverage odluku i nula ostaje
  nepokriveno.
- Instrument Intent V3 povezuje track, frazu, notu, sekciju i ansamblsku vezu;
  55 scenarija daju 110 stvarnih MIDI fixturea i 110/110 analyzer PASS.
- Family Intent V1 klasificira Drum/Bass/Guitar/Piano note; 38/38 real-SMF
  slučajeva i 19/19 adversarial parova prolazi bez mutation authorityja.
- Section & Narrative V3 prolazi 24/24 real-SMF slučaja i 12/12 parova;
  velocity-only lažna granica se odbija, a boundary overlap ostaje preserve.
- Neural Dataset V2 prolazi 14/14 byte-identičnih roundtripova i daje 60
  clean/corrupt slučajeva plus 26 hard-negative `PRESERVE` primjera kroz šest
  ritam/gate defect klasa. Velocity ostaje samo u Factory profilima, bez
  protected promjene ili source-group leakagea.
- Self-Supervised Encoder koristi 9/2/2 grouped split, poboljšava validation i
  test masked reconstruction baseline i ostaje analysis-only bez MIDI mutacije.
- Svih 565 Factory/manual-only instrumenata ima vlastiti exact Sound+role
  profil kroz 18 porodica; 85 profila je protected, 480 suggestion-only, pet
  grouped-proxy, a produkcijski AUTO ostaje 0.
- 52 deterministička MIDI/KAR fixturea pokrivaju svih 26 A–Z faza pozitivnim i
  negativnim scenarijem. To je coverage matrica, ne hardware certifikacija.
- Event-level verifier, authority ledger i final quality gate.
- AUTO Voice profilni gate: 17/542 profila, odnosno 3,1365% profila i 9,6418% Factory note mase.
- Posljednja stvarna Windows validacija odnosi se na stariju 1.2 granu i 30 Song fajlova; 2.1.1 mora dobiti novi finalni vanjski report.
- 2.2.7 obnavlja hashirane runtime profile, uvodi byte-identični strict-preserve,
  odvaja `gentle`, pooštrava note authority i uklanja PKL0 testne fixturee.
- Factory Usage Meter svaku notu svrstava u jednu coverage klasu i mjeri
  `available`, `resolved`, `used`, `mutated` i `blocked` po familiji/kontekstu.
- `instruments/policies.py` je spojen na velocity/timing/gate runtime routing;
  UNKNOWN, SFX i SYNTH_FX nemaju generičku note mutaciju.
- Batch JSON/CSV agregator postoji u `tools/aggregate_factory_usage.py`.
- Doctor repair se ponavlja iz netaknutog ulaza i mora dati isti canonical
  digest; multi-program kanal nema note shaping; Style preset zahtijeva
  minimalno importabilan Pa800 ugovor; direktni FX dry guard ima authority zapis.
- Windows/Mido paket za 2.2.4 potvrdio je instalaciju, ali je otkrio sustain,
  Organ i zero-duration occurrence rubne slučajeve; 2.2.7 ih zatvara i traži
  ponavljanje istog batcha prije zatvaranja compatibility faze.

---

## Faza 2.2 — Factory Usage Meter

**Lokalni status 2.2.0:** core meter, report schema, final quality gate,
instrument policy routing i batch JSON/CSV agregacija su završeni. Vizuelni GUI
dashboard je lokalno završen; stvarna Windows/Mido provjera ostaje obavezna.

### Cilj

Za svaki obrađeni MIDI prikazati koliko je Factory baze stvarno korišteno, a ne samo koliko je dostupno.

### Implementacija

- exact Sound note coverage;
- Sound+Role+Element+CV coverage;
- Kit+Key hit coverage;
- family fallback coverage;
- protected/unknown/conflict note fraction;
- Factory-derived naspram heuristic/hardware odluka;
- per-module broj promijenjenih i sačuvanih događaja;
- batch dashboard i CSV/JSON agregacija.

### Gate

- svaka nota dobija tačno jednu coverage klasifikaciju;
- zbir klasifikacija je 100%;
- report razlikuje `available`, `resolved`, `used`, `mutated` i `blocked`.

---

## Faza 2.3 — Ground-truth Musical Context

**Analyzer V2 status:** dodani su strogi annotation schema, privatni template,
evaluator i `PA800_MUSICAL_UNDERSTANDING_V2`. Runtime sada daje muzičke
funkcije, frazne lukove, melodijski kontur i motive, simultane i blisko
arpeđirane chord-shape oznake, bounded voice-leading, Drum/Bass odnose,
foreground razmjenu/prostor, orkestracijsku gustoću, tension trajectory,
masking upozorenja, objašnjenja i UNKNOWN granice.
Nijedan accuracy/F1 rezultat se ne tvrdi dok ne postoji propisani ručno
označeni korpus; analyzer nema kreativni AUTO autoritet.

**Musician Workflow V1:** centralni dashboard objedinjuje Groove Preserver,
role, sekcije, Vocal Friendly, Pa800 Drum Intelligence, harmonijski kontekst,
Live Stage i Creative Preview. Musical presetovi biraju dokazno ograničene
politike; Vocal Friendly štiti foreground note od shaping enginea, dok
Creative Preview ne mijenja pitch, note ni aranžman.

### Cilj

Pretvoriti Song section/function heuristiku u izmjeren model.

### Implementacija

- ručno označiti najmanje 100 Song, 100 Style i 30 KAR fajlova;
- track funkcije: foundation, lead, counter, comp, pad, riff, ornament;
- Song sekcije: intro, verse, pre-chorus, chorus, solo, break, ending;
- confusion matrix po funkciji i sekciji;
- confidence calibration i UNKNOWN prag;
- žanr/meter/tempo stratifikacija.

### Gate

- track-function prihvatljivost ≥90%;
- section boundary F1 ≥0,85;
- nejasni slučajevi ostaju UNKNOWN;
- nijedna E1 Song sekcija ne dobija skriven E2 autoritet.

---

## Faza 2.4 — Dublje korištenje ATOMIC baze

**Lokalni status 2.4.4 / 2.4D:** svih 542 Factory profila i 23 službena
manual-only DNC profila imaju samostalnu evidence-complete karticu. Kartica
sadrži originalnu Factory numeriku kada postoji, official-manual semantiku,
community kandidate bez autoriteta i eksplicitne UNKNOWN granice. Ukupno je
565/565 kompletnih shema; nijedna forumska tvrdnja nema AUTO autoritet.

**Lokalni status 2.4.5 / 2.4E, ponovo certifikovan u 2.5.0:** kompletni stress
manifest pokriva svih 261 javnih funkcija u 80 modula. Dinamički trag pogađa
212 funkcija, dok su ostale
eksplicitno vezane za CLI, GUI, release/build, real-Mido/PC ili hardware ugovor.
Edge matrica pokriva MIDI ekstreme, gusti 16-kanalni determinizam i korelirane
muzičke regresije.

**Lokalni status 2.5.0:** `PA800_INSTRUMENT_INTENT_V3` je integriran u
optimizer i analysis-only CLI. Svaka od 110 pozitivnih/negativnih stress MIDI
varijanti prolazi dvostruku analizu sa stabilnim digestom, 100% atribucijom
nota, nula mutacija i nula AUTO autoriteta. Ground-truth accuracy i dalje je
otvoren gate; V3 je dokaz strukture i fail-closed ponašanja, ne tvrdnja da je
svaka umjetnička namjera statistički potvrđena.

**Lokalni status 2.5.1:** generator pravi SHA-256 vezan annotation sheet, a
evaluator računa fine/superclass macro-F1, UNKNOWN precision, ECE i grouped
split leakage. Savršen kompletan sintetički korpus prolazi; samouvjereno
pogrešan model i source leakage padaju. Stvarni status ostaje
`EXTERNAL_REQUIRED` sa 0/100 Song, 0/100 Style i 0/30 KAR. Kalibracija nema
mutation authority.

**Lokalni status 2.5.2:** specijalizirani analyzer pokriva Drum/Percussion,
Bass, Guitar i Piano/EP namjere na nivou note. Postojeći RX/DNC, low-velocity
special kandidati, damper i ekspresivni kontroleri ostaju protected. Svih 38
kanonskih MIDI slučajeva i 19 pozitivno-negativnih parova prolazi dvostruki
digest test; sloj ima nula mutacija i nula AUTO autoriteta. Family ground truth
i Pa800 A/B ostaju vanjskim dokaznim gateom.

**Lokalni status 2.5.3:** Style Element/CV i prepoznati marker su E2, dok
Song/KAR inferred boundary zahtijeva višestruke promjene koje ne uključuju
velocity kao boundary autoritet. Analyzer razlikuje build, release, contrast i
return, evidentira pickup/break/overlap slučajeve i nikada ne cijepa sustain
notu na granici. Svih 24 MIDI slučaja i 12 adversarial parova prolazi; stvarni
section-boundary F1, label macro-F1 i false-chorus gate ostaju otvoreni do
ručno označenog korpusa.

**Lokalni status 2.4.1 / 2.4A proxy:** before/after fingerprint audit
za Bass, Guitar i Piano. Bass timing koristi najbliži Drum anchor umjesto
nezavisnog random pomaka. Grouped holdout dopušta pozitivan runtime model samo
za Finger Bass 3 i Grand Piano. Guitar strum grupe ostaju preserve jer nijedan
Guitar profil nije prošao stability+error gate; Piano chord onset grupe smiju
se pomjeriti samo zajedničkim delta pomakom, bez desinhronizacije ili
flatteninga unutrašnjeg velocity balansa.
Piano gate se ne mijenja dok je CC64 damper aktivan. Final quality gate blokira
svaku detektovanu regresiju. Širi positive-model support ostaje zatvoren dok
novi profil ne prođe isti grouped stability+error gate.

**Lokalni status 2.4.1 / 2.4B proxy:** Strings, Ensemble, Pad i Choir čuvaju
simultane chord onsete i duge sustain tailove. Organ koristi mali velocity cap i
ne smije izgubiti postojeći legato. Brass, Reed, Pipe, Harmonica, Accordion i
Synth Lead sa PB/CC1/CC2/CC64/CC80/CC81/Aftertouch dokazom ostaju bez timing i
gate rewrita. Njihov controller contour je event-level invariant, osim zasebno
autorizovanih CC91/93 FX sendova. Grouped holdout daje tačno ograničene
pozitivne modele za Analog Strings 2, i3 Strings i Jazz Clarinet. Ensemble
akord/fraza se pomjera koherentno; Jazz Clarinet velocity ostaje potpuno
sačuvan kada već postoji ekspresivni controller. Organ, Brass, Pad i
Accordion/Reed ostaju guard-only jer nijedan njihov profil nije prošao gate.

**Lokalni status 2.4.2 / 2.4C CLOSED PRESERVE:** rijetke familije koriste exact-only
koridor. Synth Lead, Chromatic Percussion/Mallet, Pluck, Ethnic i heterogene
Other porodice ne koriste family fallback za mutaciju; potreban je exact
GOOD/STRONG profil sa STABLE/MODERATE klasom. Slab exact profil ostaje vidljiv
u usage reportu kao `available`, ali je `blocked` i nije `used`. SFX, Synth FX,
Cycle, Random i wave-sequence identiteti su note-level preserve.
Strojni evidence report nalazi nula profila koji su istovremeno GOOD/STRONG i
STABLE/MODERATE; zato nema pozitivnog rijetkog AUTO modela. Novi kandidat samo
ponovo otvara review i ne dobija autoritet iz samog evaluator rezultata.

### Cilj

Spojiti trenutno analyzer/report-only dimenzije tamo gdje dokaz dozvoljava.

### Implementacija

- Variation progression → section energy targets;
- cross-role timing → Drum/Bass/Perc interaction suggestions;
- phrase/bar contour → instrument-aware dynamics;
- exact controller trajectory → preserve/smoothing rules;
- technique candidates → audition queue, nikad slijepi insertion;
- special-pitch relation → preciznija RX protection zona;
- multimodal velocity profil → mode-aware correction;
- style/element/CV stability → dinamički strength limiter.

### Gate

- svaki novi mutator ima holdout i negativni test;
- groove fingerprint retention ≥95%;
- velocity IQR retention ≥0,75;
- 100% verifier PASS;
- bez povećanja RX/DNC regresija.

---

## Faza 2.5 — Hardware Evidence Campaign

**Infrastrukturni status 2.2.4:** generator kreira 210 Voice A/B redova
(30 za svaku od sedam glavnih familija), 150 FX redova (30 za svaku glavnu
ulogu) i svih 23 manualnih DNC adresa. Evaluator zahtijeva stvarni Pa800 OS,
Musical Resources, SET i audio-chain identitet; UNKNOWN nije PASS, a stuck
note, wrong program, lost articulation ili playback error blokira kampanju.
Fizički rezultati još nisu uneseni, pa E3 autoritet nije dodijeljen.

### Cilj

Popuniti E3 registry stvarnim Pa800 A/B dokazom.

### Test skup

- najmanje 30 A/B primjera po glavnoj Voice porodici;
- najmanje 30 FX A/B primjera za glavne mix uloge;
- svih 23 manualnih DNC Soundova kroz audition set;
- više OS/SET konfiguracija gdje je moguće;
- original i optimized pod identičnim mixer/master uslovima.

### Metrike

- Voice top-1 i top-3 accuracy;
- false-positive rate;
- preference original/optimized/same;
- timbre character, clarity i mix fit;
- RX/DNC preservation;
- FX depth, mud i foundation dryness.

### Gate

- AUTO Voice samo za porodicu sa top-1 ≥85% i false-positive <2%;
- najmanje 90% hardware A/B rezultata bolje ili jednako;
- nijedan stuck note, pogrešan program, izgubljena artikulacija ili ozbiljan playback kvar.

---

## Faza 2.6 — RX/DNC Hardware Maps

### Cilj

Zamijeniti `SPECIAL_CANDIDATE` oznake potvrđenim mapama samo gdje hardware dokaz postoji.

### Implementacija

- per-Sound CC80/CC81/JS/AT/Damper prag;
- legato/staccato interval i gap koridori;
- key-on/key-off/noise ponašanje;
- Cycle/Random označiti kao interni nedeterministički rezultat;
- OS/SET/version vezivanje svakog zapisa;
- rollback i audition MIDI uz svaki E3 zapis.

### Gate

- nijedna semantika bez izvora i fizičkog testa;
- exact address + OS/SET match;
- fallback je preserve, nikad guess.

---

## Faza 2.7 — Pa800 FX Serialization Lab

### Cilj

Utvrditi može li se sigurno zapisivati Insert/Master FX.

### Implementacija

- sourced format/schema dokumentacija;
- byte-level before/after capture sa Pa800;
- algoritam, parametar i routing identitet;
- roundtrip kroz Pa800 save/load;
- verifier allowlist za svaki serializovani field.

### Gate

- ako schema nije dokazana: ostaje trajno recommendation-only;
- ako jeste: 100% byte/event roundtrip na hardware test skupu;
- nijedan guessed SysEx ili nesourced field.

---

## Faza 2.8 — Real-world Compatibility Matrix

**Lokalni status 2.4.3:** validator i evidence agregator su završeni. Samo
report tačnog build ID-a, sa PASS release/build/wheel/real-Mido gateovima i
jedinstvenim korisničkim SHA-256 ulazima ulazi u kvotu. Stari buildovi,
`TEST_*`/fixture/synthetic sadržaj, duplikati i sistemi izvan propisane matrice
su eksplicitno odbijeni. Vanjska kvota ostaje otvorena: trenutni build ima
0/100 Song, 0/100 Style, 0/30 KAR, 0/5 Python minor verzija i 0/2 Windows
generacije.

### Cilj

Potvrditi cijeli sistem izvan sintetičkih testova.

### Matrica

- Python 3.10–3.14;
- Windows 10 i 11;
- Mido podržane verzije;
- 100+ Song, 100+ Style i 30+ KAR;
- GM, Pa800 exact, RX/DNC, User, multi-program i legacy exporter;
- Unicode/duge putanje, antivirus lock, disk-full i interrupted batch;
- session undo/redo, crash recovery i audio reference.

### Gate

- 100% final verifier PASS;
- 0 corrupt outputa;
- 0 neautorizovanih Bank/Program/FX/articulation promjena;
- deterministic hash za isti input/config;
- dokumentovan performance i peak RAM.

---

## Faza 2.9 — Release Engineering

### Implementacija

- zaključani dependency constraints;
- CI matrica;
- wheel i clean-machine smoke test;
- jedan Windows installer/launcher;
- upgrade/migration test za session i registry schema;
- code signing gdje je dostupno;
- objedinjeni korisnički priručnik;
- privacy i recovery dokumentacija;
- jedan `FINAL_VALIDATE_3_0.bat` i jedan završni SEND_ME paket.

### Gate

- clean Windows instalacija bez ručne Python intervencije;
- svi packaged Factory SHA-256 hashovi potvrđeni;
- nema cachea, temp podataka ni privatnih MIDI fajlova u releaseu.

---

## Verzija 3.0 — Hardware-Proven FULL

3.0 se može proglasiti tek kada su istovremeno zatvoreni:

- Software gate: 100% verifier PASS na punoj real-world matrici;
- Musical gate: ≥90% A/B bolje ili jednako;
- Voice gate: po-porodici top-1 ≥85% i false-positive <2%;
- RX/DNC gate: bez izgubljene potvrđene artikulacije;
- FX gate: bez mutnog Bass/Drum temelja;
- Release gate: clean install i deterministic output;
- Evidence gate: svaka AUTO odluka ima E2 ili E3 trag.

## Šta nije obavezno za FULL optimizer

- neuralno generisanje novih pjesama;
- automatski harmony rewrite;
- izmišljanje RX/DNC semantike;
- Insert/Master FX ako serialization nikad nije dokaziva.

Ove funkcije ne smiju blokirati stabilan FULL optimizer niti se predstavljati kao završene bez posebnog istraživačkog projekta.
