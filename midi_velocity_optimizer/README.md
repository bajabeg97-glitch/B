# MIDI Velocity Optimizer & Auto Audio Engineer

🎵 Napredna Python aplikacija za automatsku optimizaciju MIDI fajlova sa inteligentnim audio engineerska obradom.

## 🎛 Karakteristike

### ⚙️ Auto Engines
- **Bass Engine**: Optimizacija bas zvuka sa velocity kontrolom i key range mapiranjem
- **Guitar Engine**: Chak Chak Strummer sa strumming pattern simulacijom
- **Drum Kit Engine**: Individualni velocity opsezi za svaki tip bubnja
- **MIDI Enhancer**: RX enhancement, DNC (Dynamic Noise Control), RX Delay

### 🔍 Analiza
- Detekcija 16 trakova sa detaljnom analizom
- Auto-detekcija tipova instrumenata (bass, gitara, bubnjevi, vokali)
- Program Change detekcija na početku trakta
- Analiza solo sekcija i delay trakova
- Detekcija terći (harmony trakova)

### 🎚️ Optimizacije
- Smanjenje pozadine na 35% (bez narušavanja strukture)
- RX Delay za smooth solo sekcije
- Redukcija miksa tokom vokala
- Batch obrada foldera sa auto postavkama
- Spremi u .mid format

## 📋 Zahtjevi

- **Python** 3.8+
- **Windows**, **macOS** ili **Linux**

## 🚀 Instalacija

### Windows (Najjednostavnije)

1. Preuzmi ili kloniraj repositorij
2. Dvoklik na `install.bat` (prvo)
3. Čekaj dok se sve instalira
4. Dvoklik na `gui.bat` za pokretanje

### Manual Instalacija

```bash
# Kloniraj repositorij
git clone <repo-url>
cd midi-velocity-optimizer

# Kreiraj virtual environment (preporučeno)
python -m venv venv
source venv/bin/activate  # Na Windowsu: venv\\Scripts\\activate

# Instaluraj zavisnosti
pip install -r requirements.txt

# Pokreni aplikaciju
python main.py
```

## 💻 Korišćenje

### GUI Aplikacija

1. **Učitaj MIDI**: Klikni "Učitaj MIDI" i odaberi .mid fajl
2. **Pregled**: Vidi sve 16 trakova sa detaljnom analizom
3. **Auto Optimize**: Klikni zelenu "Auto Optimize" tipku
4. **Spremi**: Klikni "Spremi MIDI" za ispis

### Batch Obrada

1. Klikni "Batch Folder"
2. Odaberi folder sa MIDI fajlovima
3. Sve .mid fajlove će biti obrada i sprema u `/optimized` folder

### Konfiguracija

Tab **"Engines"** omogućava fino podešavanje:
- **Bass**: Min/Max velocity, Key range, Artikulacije
- **Guitar**: Strumming intensity, velocity opseg
- **Drums**: Individualni opsezi za Kick, Snare, HiHat, Crash

Tab **"Batch Postavke"** za globalne opcije pri batch obradi:
- Primjena svakog enginea
- Background reduction % (default 35%)
- RX enhancement i DNC

## 📊 Analizirani Podaci

Svaki trak prikazuje:
- **Tip**: Detektovani instrument tip
- **Velocity Range**: Min i max brzina
- **Opseg**: Min i max nota
- **Ukupno nota**: Broj nota u tracku
- **Solo?**: Da li je solo sekcija
- **Terća?**: Da li je harmony/terća trak
- **Delay?**: Da li ima delay

## 🔧 Engines Detaljno

### Bass Engine
```
Min Velocity: 50
Max Velocity: 110
Key Range: C1 (24) - B3 (59)
Artikulations: sustain, accent, muted, slap
RX Enhancement: ON
DNC: ON
```

### Guitar Engine
```
Min Velocity: 40
Max Velocity: 110
Key Range: E2 (40) - B4 (83)
Artikulations: pick, muted, palm_mute, harmonic, bend
Strumming Pattern: ON
RX Enhancement: ON
```

### Drum Kit Engine
```
Kick (C1): 50-110
Snare (D1): 60-110
Closed HiHat (F#1): 40-90
Open HiHat (A#1): 50-100
Crash (C#2): 70-110
Ride (D#2): 50-100
```

## 📝 Primjeri

### Primjer 1: Standardna obrada
```bash
python main.py
# 1. File → Load MIDI
# 2. Click Auto Optimize
# 3. File → Save MIDI
```

### Primjer 2: Batch obrada
```bash
python main.py
# 1. Click Batch Folder
# 2. Select folder with .mid files
# 3. Wait for processing
# 4. Check /optimized folder
```

## 🐛 Troubleshooting

### "Python nije pronađen"
- Preuzmi Python sa https://www.python.org/downloads/
- **Važno**: Označi "Add Python to PATH" pri instalaciji
- Restartuj računar

### "Greška pri instalaciji"
```bash
# Isprobaj manual instalaciju:
python -m pip install --upgrade pip
pip install mido PyQt6 numpy
```

### MIDI fajl se ne učitava
- Provjerite da li je .mid fajl ispravan
- Pokušajte sa drugim MIDI editorom da otvorite fajl
- Provjerite da li ima dovoljno memorije

## 📚 Korisna Literatura

- [mido dokumentacija](https://mido.readthedocs.io/)
- [PyQt6 dokumentacija](https://www.riverbankcomputing.com/software/pyqt/)
- [MIDI Specification](https://www.midi.org/specifications)

## 🤝 Doprinos

Suggestions i bug reports su dobrođošli! Kreiraj issue ili pull request.

## 📄 Licenca

MIT License - Slobodno koristi, prilagođavaj i dijeli!

## 👨‍💻 Autori

Kreirano za audio engineers i MIDI entuzijaste.

---

**Verzija**: 1.0.0
**Posljednja Ažuriranja**: 2026
**Status**: ✅ Aktivno Održavano
