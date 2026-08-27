# Safe Voice Upgrade Director 0.8.0

Sistem automatski mijenja instrument samo kada može dokazati da ostaje u istoj GM programskoj klasi. Cilj je dobiti kvalitetniju Pa800 varijantu bez promjene muzičke funkcije trake.

## Automatski koridor

Svi uslovi moraju biti ispunjeni:

1. izvor je exact GM Sound u banci `121.0`;
2. cilj ima isti Program broj i istu Factory porodicu;
3. cilj je GOOD ili STRONG, prisutan u najmanje pet stilova i STABLE/MODERATE;
4. adresa nije konfliktna i ni izvor ni cilj nisu RX/DNC;
5. Factory/context score napreduje najmanje 10 bodova;
6. margin je najmanje 7, confidence najmanje 0,95;
7. traka ima postojeće CC0, CC32 i tačno jedan Program Change.

Ponovljeni Bank Select događaji su dozvoljeni jer ih stvarni Pa800/StyleWorks Song export koristi kao redundantni setup. Svi se mijenjaju u isti autorizovani cilj, a event-level verifier potvrđuje svaki događaj. Dva ili više Program Change događaja znače više mogućih instrumenata i automatska promjena se odbija.

## Šta ostaje suggestion-only

- prelazak na drugi Program broj;
- Drum Kit promjena;
- RX/DNC ili konfliktna adresa;
- slab, nestabilan ili kontekstualno nejasan Factory profil;
- kandidat koji mijenja karakter instrumenta iako statistički score izgleda bolje.

## Hardware potvrda

Pokreni `CREATE_VOICE_UPGRADE_AUDITION.bat`. Svaki generisani MIDI svira A: GM izvor, zatim B: Pa800 cilj istog Program broja. Popuni `VOICE_UPGRADE_SCORE.csv`. Rezultat služi za budući hardware-confirmed whitelist; Factory statistika sama ne može dokazati subjektivno bolji timbar.