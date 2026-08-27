# P0 Real Windows / Pa800 validation

## Pokretanje

1. Napravi folder sa 10–30 kopija stvarnih MIDI/KAR fajlova. Uključi Song, Style, GM, Pa800 exact, RX, tih i preglasan primjer.
2. Prevuci taj folder na `P0_REAL_VALIDATION.bat` ili pokreni BAT i zalijepi punu putanju.
3. Sačekaj dependency, test, wheel, MIDI Doctor, Voice/FX i Velocity provjere.
4. Otvori generisani `validation_results/SEND_ME_PA800_VALIDATION_*.zip`.

## A/B paket

ZIP sadrži:

- `PA800_AB_PACK/01_ORIGINAL` — nepromijenjene kopije ulaza;
- `PA800_AB_PACK/02_OPTIMIZED` — AUTO PILOT rezultati;
- `PA800_AB_PACK/03_REPORTS` — puni JSON audit;
- `PA800_AB_SCORE_SHEET.csv` — tabela za Pa800 ocjene;
- `PA800_AB_MANIFEST.json` — SHA-256, mode/policy, repair, velocity, Sound i FX sažetak.

Originalni folder se nikad ne mijenja. Svaki fajl se optimizuje samo jednom; isti rezultat se koristi za report i hardware A/B paket.

## Kritični FAIL

Stuck note, pogrešna Bank/Program adresa, nestala RX/DNC artikulacija, promijenjena forma/tempo/marker, clipping ili verifier FAIL. Po završetku pošalji cijeli SEND_ME ZIP sa popunjenim score sheetom.