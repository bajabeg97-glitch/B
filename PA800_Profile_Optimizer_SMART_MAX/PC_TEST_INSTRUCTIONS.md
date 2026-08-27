# Test na računaru

## Najjednostavnije

1. Raspakuj ZIP u običan folder, npr. `C:\PA800_SMART_MAX`.
2. Dvoklikni `VALIDATE_ON_PC.bat`.
3. Sačekaj završetak. Prvi put instalira mali VALIDATION profil: Mido, pytest i build.
4. U folderu `validation_results` pronađi
   `SEND_ME_PA800_VALIDATION_YYYYMMDD_HHMMSS.zip` i pošalji ga.

Ako su veliki Factory JSON fajlovi prazni ili oštećeni, koristi
`REPAIR_AND_VALIDATE.bat`. Repair paket ih vraća prije ponovnog testa.

## Test sa tvojim MIDI fajlovima

Prevuci folder sa MIDI/KAR fajlovima na `VALIDATE_ON_PC.bat`, ili pokreni:

```bat
VALIDATE_ON_PC.bat "D:\Moji MIDI fajlovi"
```

Validator obrađuje najviše 30 fajlova u privremenom folderu. Ne mijenja
originale i ne stavlja tvoje MIDI fajlove u ZIP za slanje; šalje samo rezultate,
nazive fajlova, verifier status i greške.

## Šta se provjerava

- stvarni Python i Mido,
- svih 48 testova nakon proširenja,
- deterministički output,
- Style/Song klasifikacija,
- 2.400-note stress test i memorija,
- stale/live output lock,
- MIDI+JSON rollback transakcija,
- wheel build i prisutnost Factory podataka,
- Tkinter prozor,
- Factory SHA-256 manifest,
- opcionalno tvoji stvarni MIDI/KAR fajlovi u preserve/suggest režimu.

Za fizički Pa800 koristi `HARDWARE_PA800_AB_TEST.md` i popuni CSV obrazac.