#!/usr/bin/env python3
"""
FORENSIC PROJECT AUDITOR
------------------------
Ovaj alat skenira cijeli projekt i pronalazi:
1. Lažne implementacije (funkcije koje samo vraćaju True/None bez logike)
2. Mrtvi kod (moduli koji se nikad ne importaju)
3. Dokumentaciju koja laže (README/MD fajlovi koji obećavaju nedostajuće funkcije)
4. Prazne klase i metode
5. Hardkodirane putanje koje neće raditi
6. Thread-unsafe operacije u GUI kontekstu
7. Nedostajuće poveznice između GUI i Engine-a
"""

import os
import re
import ast
import sys
from pathlib import Path
from collections import defaultdict

class ForensicAuditor:
    def __init__(self, root_path):
        self.root = Path(root_path)
        self.issues = []
        self.import_graph = defaultdict(set)
        self.defined_symbols = {}
        self.used_symbols = set()
        
    def scan_all(self):
        print("🔍 POČINJEM FORENZIČKU ANALIZU PROJEKTA...\n")
        
        # 1. Identificiraj sve Python fajlove
        py_files = list(self.root.rglob("*.py"))
        print(f"Pronađeno {len(py_files)} Python fajlova.")
        
        # 2. Analiziraj import strukturu
        self.analyze_imports(py_files)
        
        # 3. Detektuj mrtvi kod
        self.find_dead_code(py_files)
        
        # 4. Detektuj lažne implementacije
        self.find_fake_implementations(py_files)
        
        # 5. Detektuj opasne pattern-e
        self.find_dangerous_patterns(py_files)
        
        # 6. Provjeri dokumentaciju vs kod
        self.verify_documentation()
        
        # 7. Generiši izvještaj
        self.generate_report()

    def analyze_imports(self, files):
        """Gradi graf importova da vidi šta se stvarno koristi."""
        for file in files:
            try:
                with open(file, 'r', encoding='utf-8') as f:
                    tree = ast.parse(f.read())
                
                module_name = file.stem
                self.defined_symbols[module_name] = []
                
                for node in ast.walk(tree):
                    if isinstance(node, ast.Import):
                        for alias in node.names:
                            self.import_graph[module_name].add(alias.name.split('.')[0])
                    elif isinstance(node, ast.ImportFrom):
                        if node.module:
                            self.import_graph[module_name].add(node.module.split('.')[0])
                    
                    # Sakupi definisane klase i funkcije
                    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        self.defined_symbols[module_name].append(node.name)
                    elif isinstance(node, ast.ClassDef):
                        self.defined_symbols[module_name].append(node.name)
                        
            except Exception as e:
                self.issues.append(f"⚠️ Greška pri parsiranju {file}: {e}")

    def find_dead_code(self, files):
        """Pronalazi module koji se nikad ne importuju."""
        all_modules = {f.stem for f in files if f.parent != self.root} # Ignoriši root skripte
        imported_modules = set()
        for imports in self.import_graph.values():
            imported_modules.update(imports)
        
        # Root skripte su uvijek "žive"
        root_scripts = {'run', 'setup_env', 'main'} 
        live_modules = imported_modules.union(root_scripts)
        
        dead_modules = all_modules - live_modules
        
        # Filtriraj poznate sigurne module (npr. __init__, setup)
        safe_prefixes = {'__', 'setup', 'test', 'audit'}
        real_dead = [m for m in dead_modules if not any(m.startswith(p) for p in safe_prefixes)]
        
        if real_dead:
            self.issues.append(f"\n💀 PRONAĐEN MRTVI KOD ({len(real_dead)} fajlova):")
            for m in sorted(real_dead):
                self.issues.append(f"   - {m}.py (Nikad nije importovan ni pozvan)")

    def find_fake_implementations(self, files):
        """Traži funkcije koje tvrde da rade nešto a nemaju logiku."""
        suspicious_keywords = ['TODO', 'FIXME', 'pass', 'return True', 'return None', 'return {}', 'return []']
        
        for file in files:
            if 'audit' in str(file) or 'test' in str(file):
                continue
                
            try:
                with open(file, 'r', encoding='utf-8') as f:
                    content = f.read()
                    lines = content.split('\n')
                
                # Provjeri za velike fajlove koji imaju sumnjivo malo logike
                if len(lines) > 50 and content.count('pass') > 10:
                    self.issues.append(f"\n🤡 SUMNJIVA IMPLEMENTACIJA: {file}")
                    self.issues.append(f"   Previše 'pass' izjava ({content.count('pass')}) za veliki fajl.")

                # Traži specifične lažne povratne vrijednosti u kritičnim funkcijama
                critical_funcs = ['optimize', 'rebuild', 'analyze', 'generate', 'process', 'fix', 'repair']
                tree = ast.parse(content)
                
                for node in ast.walk(tree):
                    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        if any(kw in node.name.lower() for kw in critical_funcs):
                            # Provjeri tijelo funkcije
                            func_body = ast.get_source_segment(content, node)
                            if func_body:
                                if 'return True' in func_body and 'if' not in func_body:
                                    self.issues.append(f"\n🚨 LAŽNA FUNKCIJA: {file}:{node.name}")
                                    self.issues.append(f"   Vraća 'True' bez ikakve logike ili provjere!")
                                
                                if len(node.body) == 1 and isinstance(node.body[0], ast.Pass):
                                    self.issues.append(f"\n🚨 PRAZNA KRITIČNA FUNKCIJA: {file}:{node.name}")
                                    self.issues.append(f"   Sadrži samo 'pass'!")

            except Exception as e:
                pass # Ignoriši greške parsiranja za ovu specifičnu provjeru

    def find_dangerous_patterns(self, files):
        """Traži opasne pattern-e poput hardkodiranih putanja, thread unsafe koda."""
        for file in files:
            try:
                with open(file, 'r', encoding='utf-8') as f:
                    content = f.read()
                    lines = content.split('\n')
                
                # Hardkodirane putanje
                if '/home/' in content or 'C:\\Users\\' in content:
                    self.issues.append(f"\n⚠️ HARDKODIRANA PUTANJA: {file}")
                    self.issues.append("   Koristi apsolutnu putanju koja neće raditi na drugim računarima.")

                # Thread unsafe GUI update (približna detekcija)
                if 'QApplication' in content or 'QWidget' in content:
                    if 'time.sleep' in content:
                        self.issues.append(f"\n⚠️ THREAD BLOCKING: {file}")
                        self.issues.append("   Koristi time.sleep() u GUI kontekstu! Zamrznut će aplikaciju.")
                    
                    # Detekcija direktnog pristupa widgetu iz threada (teško bez AST, ali probajmo regex)
                    if re.search(r'self\.\w+\.setText|self\.\w+\.update|self\.\w+\.repaint', content):
                        # Ovo je previše lažnih pozitivnih, preskočimo osim ako je unutar QThread
                        pass 

            except Exception:
                pass

    def verify_documentation(self):
        """Provjerava da li README/MD fajlovi obećavaju stvari koje ne postoje."""
        md_files = list(self.root.rglob("*.md"))
        if not md_files:
            return

        # Sakupi sve javne klase i funkcije iz koda
        implemented_features = set()
        for mod, symbols in self.defined_symbols.items():
            implemented_features.update(symbols)
        
        # Ključne riječi koje dokumentacija često laže
        hype_words = ['AI', 'Neural', 'Smart', 'Auto', 'Premium', 'Ultimate', 'Intelligent']
        
        for md in md_files:
            with open(md, 'r', encoding='utf-8') as f:
                content = f.read().lower()
            
            # Ako dokumentacija spominje "Neural Network" a nemamo torch/numpy usage u glavnim modulima
            if 'neural' in content or 'ai engine' in content:
                # Provjeri postoji li stvarni AI kod
                has_ai = False
                for file in self.root.rglob("*.py"):
                    if 'neural' in str(file) or 'ai' in str(file):
                        with open(file, 'r') as f:
                            if 'torch' in f.read() or 'tensorflow' in f.read() or 'sklearn' in f.read():
                                has_ai = True
                                break
                if not has_ai:
                    self.issues.append(f"\n📄 DOKUMENTACIJA LAŽE: {md}")
                    self.issues.append("   Spominje 'Neural/AI' motore, ali nema pronađenih biblioteka ili implementacije!")

    def generate_report(self):
        print("\n" + "="*60)
        print("📊 REZULTATI FORENZIČKE ANALIZE")
        print("="*60)
        
        if not self.issues:
            print("\n✅ NISU PRONAĐENI KRITNIČNI PROBLEMI!")
            print("Projekt izgleda čisto (po površnoj analizi).")
        else:
            print(f"\n❌ PRONAĐENO {len(self.issues)} POTENCIJALNIH PROBLEMA:\n")
            for issue in self.issues:
                print(issue)
        
        print("\n" + "="*60)
        print("Preporuka: Pokreni ovaj script prije svakog 'Release'.")
        print("="*60)

if __name__ == "__main__":
    from pathlib import Path
    root = Path(__file__).resolve().parent
    auditor = ForensicAuditor(str(root))
    auditor.scan_all()
