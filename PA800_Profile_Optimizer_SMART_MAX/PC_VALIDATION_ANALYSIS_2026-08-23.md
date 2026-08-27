# Analiza primljenog Windows validation paketa

Paket: `SEND_ME_PA800_VALIDATION_20260823_213446_299769.zip`

## Šta je stvarno potvrđeno

- Windows 10 build 19045, Python 3.14.7 i Mido 1.3.3 rade.
- Obavezni i forenzički dependencyji su dostupni; Torch je opcionalno odsutan.
- Factory release audit prolazi bez greške.
- Tkinter prozor radi.
- Wheel 2.2.4 se gradi i sadrži obavezne Factory profile.
- Tadašnji release skup završava sa 143/143 PASS.
- Real-Mido stress od 2.400 nota prolazi sa približno 17,77 MiB peak memorije.

## Crveni rezultati

Paket je napravljen iz verzije 2.2.4, pa nije validacija trenutnog builda.
Od 30 stvarnih Song MIDI fajlova devet je završilo, a 21 je sigurno blokiran
prije commita:

- 18 fajlova prijavilo je skraćeni sustain tail; stvarni uzrok je uglavnom bio
  pomak cijele note za 1--3 ticka, dok je trajanje ostalo isto;
- sedam fajlova prijavilo je Organ velocity izvan limita; conductor profile
  rail je mogao nadjačati family delta cap;
- jedan fajl prijavio je izgubljen Organ legato jer naredna nota nije bila dio
  istog timing guarda;
- dva fajla pala su na canonical note diffu jer je legalna zero-duration Drum
  nota pri timing pomaku produžena sa 0 na 1 tick.

Jedini `real_mido` fixture FAIL nije dokaz kvara DNC enginea. Test je koristio
Preserve preset, zatim očekivao automatski CC80 apply. Preserve ga po centralnoj
politici mora blokirati, pa je sam validation test bio kontradiktoran.

## Korekcije poslije paketa

- sustain audit sada poredi trajanje, a ne apsolutni Note-Off tick;
- overlap/retrigger same-pitch tokovi imaju occurrence-order guard;
- gate ne može preći naredni onset iste note;
- obje note Organ legato veze ulaze u timing guard;
- Organ profile rail više ne može nadjačati family cap;
- zero-duration Drum nota zadržava trajanje nula pri timing pomaku;
- verifier vraća mali strukturirani razlog umjesto ogromnog mutation ledgera;
- PC report zapisuje tačnu verziju/build ID i odvojeno testira DNC apply i
  Preserve blokadu.

Konačan Windows status ostaje otvoren dok se novi build ponovo ne pokrene na
istih 30 fajlova sa stvarnim Mido paketom.