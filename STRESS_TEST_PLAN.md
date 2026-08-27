# PA800 Profile Optimizer: Stress Test Plan

Ovaj plan vrijedi za sadržaj direktorija `PA800_Profile_Optimizer_SMART_MAX` iz
arhive `PA800_Profile_Optimizer_BAJA_MAX_AUTONOMOUS_PREMIUM_R13_CHECKPOINT (1).zip`.
Cilj nije samo da testovi završe bez iznimke, nego da svaki modul ima dokazanu
ulaznu granicu, izlazni ugovor, ponašanje pod opterećenjem i siguran kvar.

## 1. Testni nivoi

| Nivo | Što dokazuje | Kriterij prolaza |
| --- | --- | --- |
| Unit | Svaka javna funkcija i granični slučajevi | 100% testova prolazi; nema neočekivanih iznimki |
| Property/fuzz | Invarijante za MIDI, profile, konfiguraciju i transakcije | 10.000 generiranih slučajeva po kritičnom ugovoru; reproducibilan seed |
| Integration | Cijeli proces: import -> analiza -> prijedlog -> gate -> export | Deterministički rezultat, očuvani nepoznati eventi, validan MIDI |
| Stress/soak | Opterećenje CPU-a, memorije, diskova i ponavljanja | 24 h bez curenja memorije, deadlocka ili degradacije; 0 izgubljenih transakcija |
| Negative/resilience | Oštećeni MIDI, profili, modeli, prekid I/O-a i nedostupne opcionalne ovisnosti | Siguran `FAIL/CANNOT_CERTIFY`, bez djelomičnog upisa i bez korupcije |
| Release gate | Instalacija, CLI, GUI, hardware/PC i manifesti | Jedan agregirani gate prolazi tek kad svi obavezni moduli prođu |

## 2. Pokrivenost po modulu

Postojeće testove grupirati i izvršavati kao sljedeće obavezne kampanje:

- **Core MIDI i sigurnost:** `midi_io`, `smf_preflight`, tolerant parser, `midi_doctor`, `preserve_unknown`, `runtime_safety`, RX/DNC guardovi.
- **Optimizer i glazbeni engine:** `optimizer`, timing, velocity, velocity conductor, performance director, phrase doctor, chord/pattern generator, rhythm/trill correction.
- **Intent i kontekst:** context, musical context/understanding, intent, family/instrument intent, ground truth, section narrative i style import contract.
- **Instrumenti i profili:** registry, fingerprints, policies, guards, exact neural profiles, profile completeness, factory atomic/data bundle/usage.
- **Neural pipeline:** corpus router, dataset forge, encoder feature/event/runtime contract, self-supervised encoder, model acceptance, training audit i trained application.
- **Mix/articulation/workflow:** mix FX director, sound FX, articulation director/audition, audition queue, repair previews, musician workflow i workstation.
- **Release i vanjski sustavi:** compatibility matrix, hardware evidence/campaign, PC validation, process certification, release integrity, final release gate, GUI state/training.

Za svaki modul mora postojati barem jedan test koji poziva javni API direktno,
jedan test procesa kroz susjedni modul i jedan negativni test. Inventar modula i
funkcija mora se usporediti s `PUBLIC_API_STRESS_MANIFEST.json`; svaki
`unaccounted` ili `unclassified` zapis ruši gate.

## 3. Kritične invarijante

1. Ulazni MIDI koji je već validan ostaje semantički validan nakon svakog procesa.
2. Nepoznati MIDI eventi, meta podaci, channel state i redoslijed događaja ostaju očuvani prema ugovoru.
3. Profil, model i konfiguracija su nepromjenjivi tijekom runtime-a; pokušaj mutacije završava odbijanjem.
4. Svaka transakcija je atomarna: ili se commitaju svi artefakti i manifest, ili nema izlazne promjene.
5. Svaki prijedlog ima dokaz, izvor, confidence i policy odluku; nedostatak dokaza znači odbijanje.
6. Isti ulaz, seed i verzija daju isti hash rezultata na najmanje tri uzastopna pokretanja.
7. Odbijeni, oštećeni ili nepotpuni ulazi ne proizvode “uspješan” artefakt.

## 4. Stress kampanje

### A. MIDI corpus stress

- 1, 10, 100 i 1.000 pjesama; 1 do 64 trackova; svi MIDI kanali.
- Note density: 0, 1, 10.000 i 1.000.000 događaja.
- Varijante: tempo/promjena takta, running status, sysex, nepoznati eventi,
  prazni trackovi, ekstremni delta-time, truncation i random byte corruption.
- Metrike: vrijeme po fajlu, peak RSS, output hash, broj očuvanih događaja,
  broj sigurnih odbijanja i broj djelomično zapisanih fajlova.

### B. Profile/neural stress

- Svaka obitelj instrumenta, rijetke obitelji, nedostajući profil, duplikat,
  pogrešan schema version, NaN/Inf, ekstremne vrijednosti i neusklađen model.
- 100 paralelnih read-only evaluacija i 10.000 serijskih evaluacija po profilu.
- Trening/holdout split mora biti bez curenja identiteta; prihvat modela mora
  pasti na lošem holdoutu, ne samo na lošem inputu.

### C. Transaction and workflow soak

- 24 sata ponavljati import -> analyze -> propose -> preview -> accept/reject ->
  export, uz nasumične prekide između svaka dva koraka.
- 32 paralelna procesa nad istim read-only datasetom i odvojenim output folderima.
- Simulirati pun disk, read-only direktorij, prekinut write, zaključan fajl,
  timeout i ponovno pokretanje nakon prekida.
- Nakon svakog prekida provjeriti da nema polu-commitanog artefakta i da je
  recovery idempotentan.

### D. CLI/GUI/hardware contract

- Pokrenuti sve javne CLI entry pointe s ispravnim, praznim, prevelikim,
  nepostojećim i zlonamjerno oblikovanim argumentima.
- GUI state/training testirati kroz 10.000 promjena stanja i ponovno učitavanje.
- Hardware/PC kampanje izvršiti u mock modu bez uređaja i u stvarnom okruženju;
  nedostupan uređaj mora biti jasan `NOT_CERTIFIED`, nikad lažni PASS.

## 5. Property i metamorfni testovi

- `optimize(optimize(midi)) == optimize(midi)` za idempotentne opcije.
- Promjena samo irelevantnog meta eventa ne mijenja glazbeni rezultat.
- Permutacija nezavisnih trackova ne mijenja rezultat po tracku.
- Export pa re-import čuva ugovorene evente i canonical hash.
- Isti seed daje isti rezultat; različit seed ne smije mijenjati safety odluke.
- Prekid transakcije u bilo kojoj točki ostavlja stanje jednako stanju prije početka.

## 6. Pokretanje i release gate

```bash
cd PA800_Profile_Optimizer_SMART_MAX
python -m pip install -e '.[dev,validation,forensics,neural]'
python -m pytest -q --maxfail=1
python tools/run_complete_stress.py
python tools/public_api_stress.py
python tools/final_release_gate.py
```

Gate je **PASS** samo ako je `pytest` return code `0`, svi testovi i kampanje
prođu, `dynamic_hit_ratio` nije nula, `unaccounted_functions == 0`,
`unclassified == 0`, nema nevalidnih outputa i svi negativni scenariji završe
sigurnim odbijanjem. Izvještaj mora spremiti verziju, commit, Python/dependency
verzije, OS, seed, corpus hash, trajanje, peak RSS i artefakte za reprodukciju.

Trenutni `COMPLETE_STRESS_RESULT.json` ne smije se označiti kao dokaz prolaza:
zadnji zabilježeni run pada jer `pytest` nije instaliran, a funkcije nisu potpuno
obračunate. Prvo treba izvršiti instalaciju i zatim cijeli gate u čistom okruženju.