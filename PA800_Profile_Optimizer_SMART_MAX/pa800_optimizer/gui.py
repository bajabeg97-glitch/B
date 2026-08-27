import json
import os
import queue
import subprocess
import sys
import threading
import traceback
import tkinter as tk
from dataclasses import asdict
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from .analysis.factory_atomic import FactoryAtomicKnowledge
from .analysis.factory_usage import render_factory_usage_dashboard
from .config import OptimizeConfig
from .gui_state import _activate_model_candidate, _effective_output_suffix, _hardware_create_command, _hardware_evaluate_commands, build_training_audit_command, build_training_command, list_midi_files, load_settings, output_path_for, save_settings
from .optimizer import Optimizer
from .repair_audition import _create_repair_variant,_describe_repair_variant
from .workstation import WorkstationSession,apply_export_preset,build_mixer_snapshot
from .musician_workflow import MUSICAL_PRESETS,configure_musical_preset,render_dashboard
from .neural.self_supervised_encoder import load_encoder_model
from .neural.corpus_router import build_corpus_manifest, route_authority, validate_corpus_manifest
from .neural.pattern_advisor import generate_chord_pattern,parse_chord_progression

ELEMENTS = ['Variation 1','Variation 2','Variation 3','Variation 4','Intro 1','Intro 2','Intro 3','Fill 1','Fill 2','Break','Ending 1','Ending 2','Ending 3']
ROLES = ['DRUM','PERC','BASS','ACC1','ACC2','ACC3','ACC4','ACC5']

class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title('PA800 Profile Optimizer — Factory + Gold Neural Workstation')
        self.geometry('1180x760')
        self.minsize(940, 620)
        self.atomic = FactoryAtomicKnowledge()
        self.settings = load_settings()
        self.worker_queue = queue.Queue()
        self.cancel_event = threading.Event()
        self.is_running = False
        self._midi_paths = {}
        self._latest_repair_context = None

        nb = ttk.Notebook(self)
        nb.pack(fill='both', expand=True)
        self.opt_tab = ttk.Frame(nb)
        self.corpus_tab = ttk.Frame(nb)
        self.training_tab = ttk.Frame(nb)
        self.hardware_campaign_tab=ttk.Frame(nb)
        self.factory_tab = ttk.Frame(nb)
        self.audit_tab = ttk.Frame(nb)
        self.context_tab = ttk.Frame(nb)
        self.pattern_tab = ttk.Frame(nb)
        self.audition_tab = ttk.Frame(nb)
        self.mix_fx_tab = ttk.Frame(nb)
        self.compatibility_tab = ttk.Frame(nb)
        self.mixer_tab = ttk.Frame(nb)
        self.session_tab = ttk.Frame(nb)
        self.quality_tab = ttk.Frame(nb)
        self.musician_tab = ttk.Frame(nb)
        self.factory_usage_tab=ttk.Frame(nb)
        nb.add(self.opt_tab, text='Optimizer')
        nb.add(self.corpus_tab, text='Factory + Gold')
        nb.add(self.training_tab, text='Trening')
        nb.add(self.hardware_campaign_tab,text='Hardware A/B')
        nb.add(self.factory_tab, text='Factory MAX Lab')
        nb.add(self.audit_tab, text='Last Audit')
        nb.add(self.context_tab, text='Musical Context')
        nb.add(self.pattern_tab, text='Pattern Brain')
        nb.add(self.audition_tab, text='Audition Queue')
        nb.add(self.mix_fx_tab, text='Mix & FX')
        nb.add(self.compatibility_tab, text='Compatibility')
        nb.add(self.mixer_tab, text='Mixer')
        nb.add(self.session_tab, text='Session')
        nb.add(self.quality_tab, text='Quality Gate')
        nb.add(self.musician_tab, text='Musician Dashboard')
        nb.add(self.factory_usage_tab,text='Factory Usage')
        self._build_optimizer()
        self._build_corpus()
        self._build_training()
        self._build_hardware_campaign_view()
        self._build_factory()
        self._build_audit()
        self._build_context_view()
        self._build_pattern_view()
        self._build_audition_view()
        self._build_mix_fx_view()
        self._build_compatibility_view()
        self._build_mixer_view()
        self._build_session_view()
        self._build_quality_view()
        self._build_musician_view()
        self._build_factory_usage_view()
        self.protocol('WM_DELETE_WINDOW', self._on_close)
        self.after(120, self._poll_worker)

    def _build_corpus(self):
        root=Path(__file__).resolve().parents[1];corpus=root/'corpus'
        self.factory_archive=tk.StringVar(value=str(corpus/'Factory Styles.zip'))
        self.gold_archive=tk.StringVar(value=str(corpus/'Gold DNA.zip'))
        self.corpus_status=tk.StringVar(value='Klikni PROVJERI KORPUSE')
        top=ttk.LabelFrame(self.corpus_tab,text='Ugrađeni izvori znanja');top.pack(fill='x',padx=10,pady=10)
        for row,(label,var,command) in enumerate((('Factory Styles',self.factory_archive,lambda:self._pick_corpus_archive(self.factory_archive)),('Gold DNA',self.gold_archive,lambda:self._pick_corpus_archive(self.gold_archive)))):
            ttk.Label(top,text=label).grid(row=row,column=0,sticky='w',padx=8,pady=7);ttk.Entry(top,textvariable=var,state='readonly').grid(row=row,column=1,sticky='ew',padx=8,pady=7);ttk.Button(top,text='IZABERI ZIP',command=command).grid(row=row,column=2,padx=8,pady=7)
        top.columnconfigure(1,weight=1)
        actions=ttk.Frame(self.corpus_tab);actions.pack(fill='x',padx=10,pady=(0,8))
        ttk.Button(actions,text='PROVJERI KORPUSE',command=self._verify_corpora).pack(side='left')
        ttk.Button(actions,text='PRIPREMI ZA TRENING',command=self._prepare_corpora).pack(side='left',padx=8)
        ttk.Button(actions,text='KORISTI COMBINED FOLDER',command=self._use_combined_training).pack(side='left')
        ttk.Label(actions,textvariable=self.corpus_status).pack(side='left',padx=12)
        box=ttk.LabelFrame(self.corpus_tab,text='Autoriteti i provjera');box.pack(fill='both',expand=True,padx=10,pady=(0,10))
        self.corpus_log=tk.Text(box,wrap='word',state='disabled');self.corpus_log.pack(fill='both',expand=True,padx=7,pady=7)
        self._verify_corpora(silent=True)

    def _pick_corpus_archive(self,var):
        selected=filedialog.askopenfilename(title='Izaberi ZIP korpus',filetypes=[('ZIP','*.zip'),('All files','*.*')])
        if selected:var.set(selected);self._verify_corpora()

    def _corpus_write(self,text):
        self.corpus_log.configure(state='normal');self.corpus_log.delete('1.0','end');self.corpus_log.insert('1.0',text);self.corpus_log.configure(state='disabled')

    def _verify_corpora(self,silent=False):
        try:
            manifest=build_corpus_manifest(self.factory_archive.get(),self.gold_archive.get());audit=validate_corpus_manifest(manifest)
            counts=audit['counts'];lines=['FACTORY + GOLD CORPUS GATE: '+('PASS' if audit['pass'] else 'FAIL'),'Factory: %s / 252'%counts.get('FACTORY'),'Gold: %s / 182'%counts.get('GOLD'),'Velocity neural input: ZABRANJEN','Velocity neural output: ZABRANJEN','Neural mutation authority: NEMA','']
            for feature in ('FILL_STRUCTURE','GUITAR_MODE','GUITAR_STRUM','POWERCHORD_VOICING','BRASS_PATTERN','STRINGS_PAD_PATTERN','DRUM_PATTERN','BASS_PATTERN','SOLO_PHRASE','EXPRESSION_CC11','ORNAMENT','VELOCITY'):
                row=route_authority(feature);lines.append('%-24s Factory=%s Gold=%s mode=%s'%(feature,row.get('factory'),row.get('gold'),row.get('mode')))
            if audit['errors']:lines.append('\nGreške: '+', '.join(audit['errors']))
            self._corpus_write('\n'.join(lines));self.corpus_status.set('PASS — Factory 252, Gold 182' if audit['pass'] else 'FAIL — vidi greške')
            if not silent and audit['pass']:messagebox.showinfo('Factory + Gold','Korpusi su kompletni i velocity izolacija je aktivna.')
            return audit['pass']
        except Exception as exc:
            self.corpus_status.set('FAIL — korpus nije dostupan');self._corpus_write('Greška: '+repr(exc))
            if not silent:messagebox.showerror('Factory + Gold',repr(exc))
            return False

    def _prepare_corpora(self):
        if not self._verify_corpora(silent=True):return messagebox.showerror('Factory + Gold','Prvo ispravi corpus gate.')
        root=Path(__file__).resolve().parents[1];target=root/'training_corpora'
        command=[sys.executable,str(root/'tools'/'prepare_factory_gold_training.py'),'--factory',self.factory_archive.get(),'--gold',self.gold_archive.get(),'--output',str(target)]
        result=subprocess.run(command,cwd=root,text=True,capture_output=True,encoding='utf-8',errors='replace')
        self._corpus_write(result.stdout+result.stderr)
        if result.returncode:return messagebox.showerror('Priprema korpusa','Priprema nije uspjela. Vidi log.')
        self.training_dir.set(str(target/'combined'));self.corpus_status.set('Spremno za trening: '+str(target/'combined'));messagebox.showinfo('Priprema korpusa','Factory i Gold su pripremljeni i Combined folder je odabran u tabu Trening.')

    def _use_combined_training(self):
        target=Path(__file__).resolve().parents[1]/'training_corpora'/'combined'
        if not target.is_dir():return messagebox.showwarning('Combined folder','Prvo klikni PRIPREMI ZA TRENING.')
        self.training_dir.set(str(target));self.corpus_status.set('Combined folder je odabran za trening')

    def _build_training(self):
        self.training_dir=tk.StringVar(value=self.settings.get('training_dir',''))
        self.training_status=tk.StringVar(value='Spreman — odaberi MIDI/KAR folder')
        self.training_power=tk.StringVar(value='MAX')
        self.is_training=False
        frame=ttk.LabelFrame(self.training_tab,text='Neural analyzer trening')
        frame.pack(fill='x',padx=10,pady=10)
        ttk.Label(frame,text='Folder sa MIDI/KAR fajlovima').grid(row=0,column=0,sticky='w',padx=8,pady=8)
        ttk.Entry(frame,textvariable=self.training_dir,state='readonly').grid(row=0,column=1,sticky='ew',padx=8,pady=8)
        ttk.Button(frame,text='IZABERI FOLDER',command=self._pick_training_folder).grid(row=0,column=2,padx=8,pady=8)
        self.btn_train=ttk.Button(frame,text='POKRENI MAX TRENING',command=self._start_training)
        self.btn_train.grid(row=1,column=2,padx=8,pady=(0,8))
        ttk.Combobox(frame,textvariable=self.training_power,values=('MAX','BALANCED'),state='readonly',width=12).grid(row=3,column=1,sticky='e',padx=8,pady=(0,8))
        self.btn_audit_training=ttk.Button(frame,text='ANALIZIRAJ FOLDER',command=self._start_training_audit)
        self.btn_audit_training.grid(row=1,column=1,sticky='e',padx=8,pady=(0,8))
        self.btn_apply_training=ttk.Button(frame,text='PRIMIJENI NA ODABRANE MIDI',command=self._apply_trained_model,state='normal' if self._trained_model_accepted() else 'disabled')
        self.btn_apply_training.grid(row=2,column=2,padx=8,pady=(0,8))
        ttk.Button(frame,text='PREGLED MODELA',command=self._preview_trained_model).grid(row=2,column=1,sticky='e',padx=8,pady=(0,8))
        self.btn_activate_candidate=ttk.Button(frame,text='AKTIVIRAJ KANDIDATA',command=self._activate_latest_candidate,state='normal' if self._latest_candidate_model() else 'disabled');self.btn_activate_candidate.grid(row=3,column=2,padx=8,pady=(0,8))
        ttk.Label(frame,text='Primjena: bounded ritam/timing, razmak trilera i trajanje nota. Factory zadržava velocity i Voice postavke.',foreground='#666').grid(row=1,column=0,rowspan=2,columnspan=2,sticky='w',padx=8,pady=(0,8))
        frame.columnconfigure(1,weight=1)
        progress_frame=ttk.Frame(self.training_tab);progress_frame.pack(fill='x',padx=10,pady=(0,6))
        self.training_progress=ttk.Progressbar(progress_frame,mode='indeterminate');self.training_progress.pack(fill='x')
        ttk.Label(progress_frame,textvariable=self.training_status).pack(anchor='w',pady=(4,0))
        log_frame=ttk.LabelFrame(self.training_tab,text='Detaljni training log');log_frame.pack(fill='both',expand=True,padx=10,pady=(0,10))
        self.training_log=tk.Text(log_frame,wrap='word',state='disabled');ys=ttk.Scrollbar(log_frame,orient='vertical',command=self.training_log.yview);self.training_log.configure(yscrollcommand=ys.set);self.training_log.pack(side='left',fill='both',expand=True,padx=(7,0),pady=7);ys.pack(side='right',fill='y',padx=(0,7),pady=7)
        self.training_dir.trace_add('write',lambda *_:self._remember_settings())

    def _pick_training_folder(self):
        initial=self.training_dir.get() or self.input_dir.get() or str(Path.home())
        selected=filedialog.askdirectory(title='Izaberi MIDI/KAR folder za trening',initialdir=initial)
        if selected:self.training_dir.set(selected);self.training_status.set('Odabran folder: '+selected)

    def _append_training_log(self,text):
        self.training_log.configure(state='normal');self.training_log.insert('end',text);self.training_log.see('end');self.training_log.configure(state='disabled')

    def _start_training(self):
        if self.is_training:return
        folder=Path(self.training_dir.get())
        if not folder.is_dir():return messagebox.showerror('Training folder','Izaberi ispravan folder sa MIDI/KAR fajlovima.')
        self.is_training=True;self.btn_train.configure(state='disabled');self.btn_audit_training.configure(state='disabled');self.training_progress.start(12);self.training_status.set('Trening u toku...')
        self.training_log.configure(state='normal');self.training_log.delete('1.0','end');self.training_log.configure(state='disabled')
        self._append_training_log('=== START GUI TRAINING ===\nProfil: %s\nFolder: %s\nMAX = 1200 epoha, hidden 48, mask 40%%, detaljni checkpoint svakih 5%%.\nVelocity input/output: ZABRANJEN.\n'%(self.training_power.get(),folder))
        threading.Thread(target=self._training_worker,args=(folder,),daemon=True).start()

    def _start_training_audit(self):
        if self.is_training:return
        folder=Path(self.training_dir.get())
        if not folder.is_dir():return messagebox.showerror('Training folder','Izaberi ispravan folder sa MIDI/KAR fajlovima.')
        self.is_training=True;self.btn_train.configure(state='disabled');self.btn_audit_training.configure(state='disabled');self.training_progress.start(12);self.training_status.set('Analiza training foldera u toku...')
        self.training_log.configure(state='normal');self.training_log.delete('1.0','end');self.training_log.configure(state='disabled')
        threading.Thread(target=self._training_worker,args=(folder,True),daemon=True).start()

    def _trained_model_path(self):
        return Path(__file__).resolve().parents[1]/'models'/'encoder.json'

    def _latest_candidate_model(self):
        folder=Path(__file__).resolve().parents[1]/'models'/'candidates';paths=sorted(folder.glob('encoder_*.json'),key=lambda path:path.stat().st_mtime_ns,reverse=True) if folder.is_dir() else []
        return paths[0] if paths else None

    def _trained_model_accepted(self):
        try:load_encoder_model(self._trained_model_path(),require_accepted=True,migrate_legacy=True);return True
        except Exception:return False

    def _apply_trained_model(self):
        paths=self._selected_paths()
        if not paths:return messagebox.showwarning('Nije odabrano','U tabu Optimizer odaberi MIDI fajlove na koje želiš primijeniti trenirani ritam/trilere.')
        if not self._trained_model_accepted():return messagebox.showerror('Trenirani model','Model ne postoji ili nije prošao acceptance/confidence gate. Otvori PREGLED MODELA.')
        accepted=messagebox.askyesno('Primijeni trenirani muzički model','Kreira nove izlazne kopije sa bounded ritam/timing, trill i note-duration korekcijama.\n\nFactory ostaje jedini autoritet za velocity i Voice postavke. Pitch/harmonija se čuvaju. Nastaviti?')
        if accepted:self._start_batch(paths,trained_rhythm_apply=True)

    def _preview_trained_model(self):
        path=self._trained_model_path()
        if not path.is_file():return messagebox.showwarning('Pregled modela','Trenirani model još ne postoji.')
        try:
            data=json.loads(path.read_text(encoding='utf-8'));acceptance=data.get('acceptance') or {};evaluation=data.get('evaluation') or {};metrics=evaluation.get('metrics') or {}
            lines=['=== PREGLED TRENIRANOG MODELA ===','Model: '+str(path),'Digest: '+str(data.get('model_digest','N/A')),'Acceptance: '+('PASS' if acceptance.get('pass') else 'FAIL'),'Confidence: '+str(acceptance.get('confidence','N/A')),'Dozvoljeno: timing, gate','Zabranjeno: velocity, pitch, Voice, Sound/Kit, articulation, FX']
            for split in ('train','validation','test'):
                row=metrics.get(split) or {};lines.append('%s: notes=%s improvement=%s'%(split,row.get('notes','N/A'),row.get('improvement','N/A')))
            if acceptance.get('reasons'):lines.append('Razlozi: '+', '.join(acceptance['reasons']))
            self._append_training_log('\n'.join(lines)+'\n');self.training_status.set('Model acceptance: '+('PASS' if acceptance.get('pass') else 'FAIL'))
        except Exception as exc:messagebox.showerror('Pregled modela','Model se ne može provjeriti: '+repr(exc))

    def _activate_latest_candidate(self):
        candidate=self._latest_candidate_model()
        if not candidate:return messagebox.showwarning('Neural kandidat','Nema kandidata za aktivaciju.')
        try:load_encoder_model(candidate,require_accepted=True)
        except Exception as exc:return messagebox.showerror('Neural kandidat','Kandidat nije validan/prihvaćen: '+repr(exc))
        if not messagebox.askyesno('Aktiviraj neuralni model','Ovo je jedina radnja koja mijenja aktivni neuralni model.\n\nKandidat: %s\nNastaviti?'%candidate):return
        active=_activate_model_candidate(candidate,self._trained_model_path());self.btn_apply_training.configure(state='normal');self.training_status.set('Eksplicitno aktiviran model: '+candidate.name);self._append_training_log('=== MODEL EXPLICITLY ACTIVATED ===\nCandidate: %s\nActive: %s\n'%(candidate,active))

    def _training_worker(self,folder,audit_only=False):
        root=Path(__file__).resolve().parents[1];command=build_training_audit_command(root,folder) if audit_only else build_training_command(root,folder,profile=self.training_power.get());candidate=Path(command[command.index('--output')+1])
        self.worker_queue.put(('training_log','$ '+subprocess.list2cmdline(command)+'\n'))
        try:
            environment=os.environ.copy();environment['PYTHONUTF8']='1';environment['PYTHONIOENCODING']='utf-8'
            process=subprocess.Popen(command,cwd=root,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,encoding='utf-8',errors='replace',bufsize=1,env=environment)
            if process.stdout:
                for line in process.stdout:self.worker_queue.put(('training_log',line))
            code=process.wait();self.worker_queue.put(('training_audit_done' if audit_only else 'training_done',code,candidate,root/'training_logs'))
        except Exception as exc:self.worker_queue.put(('training_failed',repr(exc)))

    def _build_hardware_campaign_view(self):
        self.hardware_campaign_dir=tk.StringVar(value=self.settings.get('hardware_campaign_dir',''))
        self.hardware_campaign_status=tk.StringVar(value='SOFTWARE CERTIFIED — fizički Pa800 A/B još nije unesen')
        frame=ttk.LabelFrame(self.hardware_campaign_tab,text='Pa800 fizička A/B certifikacija');frame.pack(fill='x',padx=10,pady=10)
        ttk.Label(frame,text='Campaign folder').grid(row=0,column=0,sticky='w',padx=8,pady=8);ttk.Entry(frame,textvariable=self.hardware_campaign_dir,state='readonly').grid(row=0,column=1,sticky='ew',padx=8,pady=8)
        ttk.Button(frame,text='IZABERI',command=self._pick_hardware_campaign).grid(row=0,column=2,padx=5,pady=8)
        ttk.Button(frame,text='KREIRAJ 383 A/B TESTA',command=self._create_hardware_campaign).grid(row=1,column=0,padx=8,pady=(0,8),sticky='w')
        ttk.Button(frame,text='OTVORI RESULTS.CSV',command=self._open_hardware_results).grid(row=1,column=1,padx=8,pady=(0,8),sticky='w')
        ttk.Button(frame,text='EVALUIRAJ + FINAL GATE',command=self._evaluate_hardware_campaign).grid(row=1,column=2,padx=5,pady=(0,8))
        frame.columnconfigure(1,weight=1);ttk.Label(self.hardware_campaign_tab,textvariable=self.hardware_campaign_status).pack(anchor='w',padx=12,pady=(0,6))
        box=ttk.LabelFrame(self.hardware_campaign_tab,text='Hardware campaign log');box.pack(fill='both',expand=True,padx=10,pady=(0,10));self.hardware_campaign_log=tk.Text(box,wrap='word',state='disabled');self.hardware_campaign_log.pack(fill='both',expand=True,padx=7,pady=7)
        self.hardware_campaign_dir.trace_add('write',lambda *_:self._remember_settings())

    def _hardware_log(self,text):
        self.hardware_campaign_log.configure(state='normal');self.hardware_campaign_log.insert('end',text);self.hardware_campaign_log.see('end');self.hardware_campaign_log.configure(state='disabled')

    def _pick_hardware_campaign(self):
        selected=filedialog.askdirectory(title='Izaberi PA800 hardware campaign folder',initialdir=self.hardware_campaign_dir.get() or str(Path.home()))
        if selected:self.hardware_campaign_dir.set(selected);self.hardware_campaign_status.set('Odabrana kampanja — popuni RESULTS.csv pa evaluiraj')

    def _create_hardware_campaign(self):
        parent=filedialog.askdirectory(title='Gdje kreirati PA800_HARDWARE_CAMPAIGN?',initialdir=self.hardware_campaign_dir.get() or str(Path.home()))
        if not parent:return
        root=Path(__file__).resolve().parents[1];target=Path(parent)/'PA800_HARDWARE_CAMPAIGN';result=subprocess.run(_hardware_create_command(root,target),cwd=root,text=True,capture_output=True)
        self._hardware_log('$ '+' '.join(_hardware_create_command(root,target))+'\n'+result.stdout+result.stderr)
        if result.returncode:return messagebox.showerror('Hardware A/B','Kreiranje nije uspjelo. Vidi log.')
        self.hardware_campaign_dir.set(str(target));self.hardware_campaign_status.set('Kreirano 383 A/B testa — popuni device podatke i RESULTS.csv');messagebox.showinfo('Hardware A/B','Kampanja je kreirana:\n'+str(target))

    def _open_hardware_results(self):
        path=Path(self.hardware_campaign_dir.get())/'RESULTS.csv'
        if not path.is_file():return messagebox.showerror('Hardware A/B','RESULTS.csv nije pronađen.')
        try:
            if os.name=='nt':os.startfile(path)
            elif sys.platform=='darwin':subprocess.Popen(['open',str(path)])
            else:subprocess.Popen(['xdg-open',str(path)])
        except Exception as exc:messagebox.showerror('Hardware A/B','Ne mogu otvoriti CSV: '+repr(exc))

    def _evaluate_hardware_campaign(self):
        folder=Path(self.hardware_campaign_dir.get());root=Path(__file__).resolve().parents[1]
        if not (folder/'CAMPAIGN.json').is_file() or not (folder/'RESULTS.csv').is_file():return messagebox.showerror('Hardware A/B','Izaberi ispravan campaign folder.')
        evaluate,gate,evaluation_path,gate_path=_hardware_evaluate_commands(root,folder);first=subprocess.run(evaluate,cwd=root,text=True,capture_output=True);self._hardware_log('$ '+' '.join(evaluate)+'\n'+first.stdout+first.stderr)
        second=subprocess.run(gate,cwd=root,text=True,capture_output=True);self._hardware_log('$ '+' '.join(gate)+'\n'+second.stdout+second.stderr)
        data=json.loads(gate_path.read_text(encoding='utf-8')) if gate_path.is_file() else {};status=data.get('release_class','EVALUATION_FAILED');self.hardware_campaign_status.set(status)
        if status=='HARDWARE_CERTIFIED':messagebox.showinfo('Hardware A/B','HARDWARE_CERTIFIED — svi fizički gateovi su prošli.')
        else:messagebox.showwarning('Hardware A/B','Status: %s\nNepopunjeni/FAIL redovi ostaju blokirani. Detalji: %s'%(status,evaluation_path))

    # ---------------- Optimizer GUI ----------------
    def _build_optimizer(self):
        f = self.opt_tab
        self.input_dir = tk.StringVar(value=self.settings.get('input_dir', ''))
        self.output_dir = tk.StringVar(value=self.settings.get('output_dir', ''))
        self.mode = tk.StringVar(value=self.settings.get('mode', 'auto'))
        self.suffix = tk.StringVar(value=self.settings.get('suffix', '_OPTIMIZED'))
        self.overwrite = tk.BooleanVar(value=bool(self.settings.get('overwrite', False)))
        self.smart_mode = tk.StringVar(value=self.settings.get('smart_mode', 'auto'))
        self.content_type = tk.StringVar(value=self.settings.get('content_type', 'auto'))
        self.midi_doctor = tk.BooleanVar(value=bool(self.settings.get('midi_doctor',True)))
        self.velocity_conductor = tk.BooleanVar(value=bool(self.settings.get('velocity_conductor',True)))
        self.articulation_mode = tk.StringVar(value=self.settings.get('articulation_mode','suggest'))
        self.safe_voice_upgrades = tk.BooleanVar(value=bool(self.settings.get('safe_voice_upgrades',True)))
        self.performance_mode = tk.StringVar(value=self.settings.get('performance_mode','shadow'))
        self.voice_aesthetic = tk.StringVar(value=self.settings.get('voice_aesthetic','original'))
        self.hardware_evidence_path = tk.StringVar(value=self.settings.get('hardware_evidence_path',''))
        self.mix_fx_mode = tk.StringVar(value=self.settings.get('mix_fx_mode','auto'))
        self.export_preset = tk.StringVar(value=self.settings.get('export_preset','auto'))
        self.variant_label = tk.StringVar(value=self.settings.get('variant_label','optimized'))
        self.musical_preset=tk.StringVar(value=self.settings.get('musical_preset','custom'))
        self.vocal_friendly=tk.BooleanVar(value=bool(self.settings.get('vocal_friendly',False)))
        self.live_performance=tk.BooleanVar(value=bool(self.settings.get('live_performance',False)))
        self.filter_text = tk.StringVar()
        self.status = tk.StringVar(value='Spreman')

        dirs = ttk.LabelFrame(f, text='Radne mape')
        dirs.pack(fill='x', padx=10, pady=(10, 6))
        self._folder_row(dirs, 'INPUT folder', self.input_dir, 0, self._pick_input_folder)
        self._folder_row(dirs, 'OUTPUT folder', self.output_dir, 1, self._pick_output_folder)
        ttk.Label(dirs,text='Hardware evidence JSON').grid(row=2,column=0,sticky='w',padx=8,pady=7);ttk.Entry(dirs,textvariable=self.hardware_evidence_path,state='readonly').grid(row=2,column=1,sticky='ew',padx=8,pady=7);ttk.Button(dirs,text='Izaberi JSON',command=self._pick_hardware_evidence).grid(row=2,column=2,padx=8,pady=7)
        ttk.Label(dirs, text='Input i Output se pamte automatski između pokretanja.', foreground='#666').grid(
            row=3, column=1, sticky='w', padx=8, pady=(0, 7)
        )
        dirs.columnconfigure(1, weight=1)

        controls = ttk.Frame(f)
        controls.pack(fill='x', padx=10, pady=4)
        ttk.Label(controls, text='Mode').pack(side='left')
        mode_box = ttk.Combobox(controls, textvariable=self.mode, values=['auto','preserve','gentle','natural','live','strong','max'], state='readonly', width=12)
        mode_box.pack(side='left', padx=(6, 16))
        mode_box.bind('<<ComboboxSelected>>', lambda _e: self._remember_settings())
        ttk.Label(controls, text='Output suffix').pack(side='left')
        suffix_entry = ttk.Entry(controls, textvariable=self.suffix, width=18)
        suffix_entry.pack(side='left', padx=(6, 16))
        suffix_entry.bind('<FocusOut>', lambda _e: self._remember_settings())
        ttk.Checkbutton(controls, text='Dozvoli overwrite', variable=self.overwrite, command=self._remember_settings).pack(side='left')
        ttk.Label(controls,text='Content').pack(side='left',padx=(16,0))
        content_box=ttk.Combobox(controls,textvariable=self.content_type,values=['auto','style','song'],state='readonly',width=8); content_box.pack(side='left',padx=5)
        content_box.bind('<<ComboboxSelected>>',lambda _e:self._remember_settings())
        ttk.Label(controls,text='SMART').pack(side='left',padx=(12,0))
        smart_box=ttk.Combobox(controls,textvariable=self.smart_mode,values=['auto','off','suggest','apply'],state='readonly',width=9); smart_box.pack(side='left',padx=5)
        smart_box.bind('<<ComboboxSelected>>',lambda _e:self._remember_settings())
        ttk.Checkbutton(controls,text='MIDI Doctor',variable=self.midi_doctor,command=self._remember_settings).pack(side='left',padx=(10,0))
        ttk.Checkbutton(controls,text='Normal Velocity',variable=self.velocity_conductor,command=self._remember_settings).pack(side='left',padx=(8,0))
        ttk.Label(controls,text='Artic.').pack(side='left',padx=(8,0))
        articulation_box=ttk.Combobox(controls,textvariable=self.articulation_mode,values=['off','suggest','apply'],state='readonly',width=8);articulation_box.pack(side='left',padx=4)
        articulation_box.bind('<<ComboboxSelected>>',lambda _e:self._remember_settings())
        ttk.Checkbutton(controls,text='Safe Voice+',variable=self.safe_voice_upgrades,command=self._remember_settings).pack(side='left',padx=(8,0))
        ttk.Label(controls,text='Perf.').pack(side='left',padx=(8,0));performance_box=ttk.Combobox(controls,textvariable=self.performance_mode,values=['off','shadow','apply'],state='readonly',width=8);performance_box.pack(side='left',padx=4);performance_box.bind('<<ComboboxSelected>>',lambda _e:self._remember_settings())
        ttk.Label(controls,text='Voice').pack(side='left',padx=(8,0));aesthetic_box=ttk.Combobox(controls,textvariable=self.voice_aesthetic,values=['original','natural','modern'],state='readonly',width=9);aesthetic_box.pack(side='left',padx=4);aesthetic_box.bind('<<ComboboxSelected>>',lambda _e:self._remember_settings())

        musician_controls=ttk.Frame(f);musician_controls.pack(fill='x',padx=10,pady=(0,4));ttk.Label(musician_controls,text='Musical preset').pack(side='left');musical_box=ttk.Combobox(musician_controls,textvariable=self.musical_preset,values=list(MUSICAL_PRESETS),state='readonly',width=20);musical_box.pack(side='left',padx=6);musical_box.bind('<<ComboboxSelected>>',lambda _e:self._remember_settings());ttk.Checkbutton(musician_controls,text='Vocal Friendly',variable=self.vocal_friendly,command=self._remember_settings).pack(side='left',padx=8);ttk.Checkbutton(musician_controls,text='Live Performance',variable=self.live_performance,command=self._remember_settings).pack(side='left',padx=8);ttk.Label(musician_controls,text='Creative Lab je preview-only.',foreground='#666').pack(side='left',padx=8)

        mix_controls=ttk.Frame(f);mix_controls.pack(fill='x',padx=10,pady=(0,4));ttk.Label(mix_controls,text='Mix & FX Director').pack(side='left');mix_box=ttk.Combobox(mix_controls,textvariable=self.mix_fx_mode,values=['auto','off','shadow','apply'],state='readonly',width=9);mix_box.pack(side='left',padx=6);mix_box.bind('<<ComboboxSelected>>',lambda _e:self._remember_settings());ttk.Label(mix_controls,text='Export preset').pack(side='left',padx=(14,0));preset_box=ttk.Combobox(mix_controls,textvariable=self.export_preset,values=['auto','song','style','preserve'],state='readonly',width=9);preset_box.pack(side='left',padx=6);preset_box.bind('<<ComboboxSelected>>',lambda _e:self._remember_settings());ttk.Label(mix_controls,text='Variant').pack(side='left',padx=(14,0));variant_entry=ttk.Entry(mix_controls,textvariable=self.variant_label,width=14);variant_entry.pack(side='left',padx=6);variant_entry.bind('<FocusOut>',lambda _e:self._remember_settings());ttk.Label(mix_controls,text='CC91/93 only; session čuva A/B istoriju.',foreground='#666').pack(side='left',padx=8)

        body = ttk.Panedwindow(f, orient='horizontal')
        body.pack(fill='both', expand=True, padx=10, pady=6)

        left = ttk.LabelFrame(body, text='MIDI fajlovi u INPUT folderu')
        right = ttk.LabelFrame(body, text='Proces / log')
        body.add(left, weight=3)
        body.add(right, weight=2)

        search = ttk.Frame(left)
        search.pack(fill='x', padx=7, pady=7)
        ttk.Label(search, text='Filter').pack(side='left')
        ent = ttk.Entry(search, textvariable=self.filter_text)
        ent.pack(side='left', fill='x', expand=True, padx=6)
        self.filter_text.trace_add('write', lambda *_: self._refresh_file_list())
        ttk.Button(search, text='Osvježi', command=self._refresh_file_list).pack(side='left')

        list_frame = ttk.Frame(left)
        list_frame.pack(fill='both', expand=True, padx=7, pady=(0, 7))
        self.file_list = tk.Listbox(list_frame, selectmode='extended', exportselection=False, activestyle='dotbox')
        sb = ttk.Scrollbar(list_frame, orient='vertical', command=self.file_list.yview)
        self.file_list.configure(yscrollcommand=sb.set)
        self.file_list.pack(side='left', fill='both', expand=True)
        sb.pack(side='right', fill='y')
        self.file_list.bind('<Double-Button-1>', lambda _e: self.optimize_selected())
        self.file_list.bind('<<ListboxSelect>>', lambda _e: self._update_selection_status())

        actions = ttk.Frame(left)
        actions.pack(fill='x', padx=7, pady=(0, 8))
        self.btn_selected = ttk.Button(actions, text='OPTIMIZE SELECTED', command=self.optimize_selected)
        self.btn_selected.pack(side='left')
        self.btn_all = ttk.Button(actions, text='OPTIMIZE ALL', command=self.optimize_all)
        self.btn_all.pack(side='left', padx=7)
        self.btn_full_test=ttk.Button(actions,text='BAJA MAX — FACTORY + GOLD',command=self.test_full_optimization_selected)
        self.btn_full_test.pack(side='left',padx=7)
        ttk.Button(actions, text='Select all', command=self._select_all).pack(side='left')
        self.btn_cancel=ttk.Button(actions,text='CANCEL AFTER CURRENT',command=self._cancel_batch,state='disabled');self.btn_cancel.pack(side='right')

        self.log = tk.Text(right, wrap='word', state='disabled')
        self.log.pack(fill='both', expand=True, padx=7, pady=7)
        statusbar = ttk.Frame(right)
        statusbar.pack(fill='x', padx=7, pady=(0, 7))
        self.progress = ttk.Progressbar(statusbar, mode='determinate')
        self.progress.pack(fill='x')
        ttk.Label(statusbar, textvariable=self.status).pack(anchor='w', pady=(4, 0))

        self.input_dir.trace_add('write', lambda *_: self._remember_settings())
        self.output_dir.trace_add('write', lambda *_: self._remember_settings())
        self._refresh_file_list()

    def _folder_row(self, parent, label, var, row, command):
        ttk.Label(parent, text=label).grid(row=row, column=0, sticky='w', padx=8, pady=7)
        entry = ttk.Entry(parent, textvariable=var, state='readonly')
        entry.grid(row=row, column=1, sticky='ew', padx=8, pady=7)
        ttk.Button(parent, text='Izaberi mapu', command=command).grid(row=row, column=2, padx=8, pady=7)

    def _pick_input_folder(self):
        initial = self.input_dir.get() or str(Path.home())
        p = filedialog.askdirectory(title='Izaberi INPUT folder', initialdir=initial)
        if p:
            self.input_dir.set(p)
            if not self.output_dir.get():
                self.output_dir.set(str(Path(p) / 'Optimized'))
            self._refresh_file_list()

    def _pick_output_folder(self):
        initial = self.output_dir.get() or self.input_dir.get() or str(Path.home())
        p = filedialog.askdirectory(title='Izaberi OUTPUT folder', initialdir=initial)
        if p:
            self.output_dir.set(p)

    def _pick_hardware_evidence(self):
        p=filedialog.askopenfilename(title='Izaberi hardware evidence JSON',filetypes=[('JSON','*.json'),('All files','*.*')])
        if p:self.hardware_evidence_path.set(p);self._remember_settings()

    def _remember_settings(self):
        try:
            save_settings({
                'input_dir': self.input_dir.get(),
                'output_dir': self.output_dir.get(),
                'mode': self.mode.get(),
                'suffix': self.suffix.get(),
                'overwrite': self.overwrite.get(),
                'smart_mode': self.smart_mode.get(),
                'content_type': self.content_type.get(),
                'midi_doctor': self.midi_doctor.get(),
                'velocity_conductor': self.velocity_conductor.get(),
                'articulation_mode': self.articulation_mode.get(),
                'safe_voice_upgrades': self.safe_voice_upgrades.get(),
                'performance_mode': self.performance_mode.get(),
                'voice_aesthetic': self.voice_aesthetic.get(),
                'hardware_evidence_path': self.hardware_evidence_path.get(),
                'mix_fx_mode': self.mix_fx_mode.get(),
                'export_preset': self.export_preset.get(),
                'variant_label': self.variant_label.get(),
                'musical_preset':self.musical_preset.get(),
                'vocal_friendly':self.vocal_friendly.get(),
                'live_performance':self.live_performance.get(),
                'training_dir':self.training_dir.get() if hasattr(self,'training_dir') else '',
                'hardware_campaign_dir':self.hardware_campaign_dir.get() if hasattr(self,'hardware_campaign_dir') else '',
                'pattern_chords':self.pattern_chords.get() if hasattr(self,'pattern_chords') else 'C | Am | F | G7',
                'pattern_include_solo':self.pattern_include_solo.get() if hasattr(self,'pattern_include_solo') else True,
            })
        except Exception:
            # GUI settings must never block MIDI work.
            pass

    def _refresh_file_list(self):
        selected_names = {self.file_list.get(i) for i in self.file_list.curselection()} if hasattr(self, 'file_list') else set()
        if not hasattr(self, 'file_list'):
            return
        self.file_list.delete(0, 'end')
        self._midi_paths = {}
        filt = self.filter_text.get().strip().lower()
        files = list_midi_files(self.input_dir.get())
        for path in files:
            if filt and filt not in path.name.lower():
                continue
            self._midi_paths[path.name] = path
            self.file_list.insert('end', path.name)
            if path.name in selected_names:
                self.file_list.selection_set('end')
        self.status.set(f'{len(self._midi_paths)} MIDI fajlova')

    def _select_all(self):
        if self.file_list.size():
            self.file_list.selection_set(0, 'end')
            self._update_selection_status()

    def _update_selection_status(self):
        count = len(self.file_list.curselection())
        total = self.file_list.size()
        self.status.set(f'Odabrano {count} / {total}')

    def _selected_paths(self):
        return [self._midi_paths[self.file_list.get(i)] for i in self.file_list.curselection()]

    def optimize_selected(self):
        paths = self._selected_paths()
        if not paths:
            messagebox.showwarning('Nije odabrano', 'Odaberi jedan ili više MIDI fajlova iz liste.')
            return
        self._start_batch(paths)

    def optimize_all(self):
        paths = [self._midi_paths[self.file_list.get(i)] for i in range(self.file_list.size())]
        if not paths:
            messagebox.showwarning('Nema MIDI fajlova', 'INPUT folder nema MIDI/KAR fajlova.')
            return
        self._start_batch(paths)

    def test_full_optimization_selected(self):
        paths=self._selected_paths()
        if not paths:
            messagebox.showwarning('Nije odabrano','Odaberi MIDI fajl za FACTORY + GOLD MAX.')
            return
        accepted=messagebox.askyesno('BAJA MAX — FACTORY + GOLD','Jedan prolaz automatski forsira bolji izvor po zadatku:\n\nFactory — PA800 struktura, Guitar Mode/PowerChord voicing, Brass, Strings/Pad i sigurnosne granice.\nGold — groove, drum/bass, strumming, fill sadržaj, solo, Expression i ukrasi.\n\nTvoji stage defaulti: DRUM 120.000.004, BASS DNC 121.016.033, RHYTHM GTR DNC 121.035.025; PERC/Conga kanal se završno spušta na 40%. Neuralni model se NE trenira ponovo. Nastaviti?')
        if accepted:self._start_batch(paths,full_optimization_test=True)

    def _start_batch(self, paths,full_optimization_test=False,trained_rhythm_apply=False):
        if self.is_running:
            return
        unique=[]; seen=set()
        for p in paths:
            key=str(Path(p).resolve()).lower()
            if key not in seen:seen.add(key);unique.append(Path(p))
        paths=unique
        out_dir = Path(self.output_dir.get()) if self.output_dir.get() else None
        if not self.input_dir.get() or not Path(self.input_dir.get()).is_dir():
            messagebox.showerror('Input folder', 'Izaberi ispravan INPUT folder.')
            return
        if out_dir is None:
            messagebox.showerror('Output folder', 'Izaberi OUTPUT folder.')
            return
        try:
            out_dir.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            messagebox.showerror('Output folder', f'Ne mogu kreirati OUTPUT folder:\n{e}')
            return
        run_suffix=_effective_output_suffix(self.suffix.get(),full_optimization_test)+('_TRAINED_RHYTHM' if trained_rhythm_apply else '');outputs={}
        for inp in paths:
            out=output_path_for(inp,out_dir,run_suffix)
            key=str(out.resolve()).lower(); outputs.setdefault(key,[]).append(inp.name)
        collisions=[names for names in outputs.values() if len(names)>1]
        if collisions:
            messagebox.showerror('Output collision','Više ulaza bi pisalo isti output:\n'+'\n'.join(', '.join(x) for x in collisions)); return

        self._remember_settings()
        self.is_running = True
        self.cancel_event.clear()
        self.btn_selected.configure(state='disabled')
        self.btn_all.configure(state='disabled')
        self.btn_full_test.configure(state='disabled')
        self.btn_apply_training.configure(state='disabled')
        self.btn_cancel.configure(state='normal')
        self.progress.configure(maximum=max(1, len(paths)), value=0)
        run_mode='TRAINED_RHYTHM_ONLY' if trained_rhythm_apply else ('FULL_TEST' if full_optimization_test else self.mode.get())
        self._append_log(f'\n=== START: {len(paths)} fajl(a) | mode={run_mode} ===\n')
        cfg_mode = self.mode.get()
        suffix = run_suffix
        overwrite = self.overwrite.get()
        smart_mode = self.smart_mode.get(); content_type=self.content_type.get();midi_doctor=self.midi_doctor.get();velocity_conductor=self.velocity_conductor.get();articulation_mode=self.articulation_mode.get();safe_voice_upgrades=self.safe_voice_upgrades.get();performance_mode=self.performance_mode.get();voice_aesthetic=self.voice_aesthetic.get();hardware_evidence_path=self.hardware_evidence_path.get();mix_fx_mode=self.mix_fx_mode.get();export_preset=self.export_preset.get();variant_label=self.variant_label.get().strip() or 'optimized';musical_preset=self.musical_preset.get();vocal_friendly=self.vocal_friendly.get();live_performance=self.live_performance.get()
        thread = threading.Thread(
            target=self._batch_worker,
            args=(list(paths), out_dir, cfg_mode, suffix, overwrite, smart_mode, content_type, midi_doctor, velocity_conductor, articulation_mode, safe_voice_upgrades, performance_mode, voice_aesthetic, hardware_evidence_path, mix_fx_mode, export_preset, variant_label,musical_preset,vocal_friendly,live_performance,full_optimization_test,trained_rhythm_apply),
            daemon=True,
        )
        thread.start()

    def _batch_worker(self, paths, out_dir, mode, suffix, overwrite, smart_mode, content_type, midi_doctor, velocity_conductor, articulation_mode, safe_voice_upgrades, performance_mode, voice_aesthetic, hardware_evidence_path, mix_fx_mode, export_preset, variant_label,musical_preset,vocal_friendly,live_performance,full_optimization_test=False,trained_rhythm_apply=False):
        cfg=OptimizeConfig.for_musical_preset(musical_preset) if musical_preset!='custom' else OptimizeConfig.for_mode(mode)
        if vocal_friendly:configure_musical_preset(cfg,'vocal_backing')
        if live_performance:configure_musical_preset(cfg,'live_stage')
        cfg.content_type=content_type
        cfg.enable_midi_repair=bool(midi_doctor)
        cfg.enable_velocity_conductor=bool(velocity_conductor)
        cfg.enable_articulation_director=articulation_mode!='off';cfg.apply_articulation_triggers=articulation_mode=='apply'
        cfg.auto_apply_safe_voice_upgrades=safe_voice_upgrades
        cfg.enable_performance_director=performance_mode!='off';cfg.apply_performance_director=performance_mode=='apply'
        cfg.voice_aesthetic=voice_aesthetic;cfg.hardware_evidence_path=hardware_evidence_path or None
        effective_mix='shadow' if mix_fx_mode=='apply' and mode=='preserve' else mix_fx_mode;cfg.mix_fx_policy=effective_mix;cfg.enable_mix_fx_director=effective_mix!='off';cfg.apply_mix_fx_director=effective_mix=='apply'
        if smart_mode!='auto':
            cfg.smart_policy_override=smart_mode
            cfg.enable_sound_kit_selector = smart_mode!='off'
            cfg.enable_fx_intelligence = smart_mode!='off'
            apply_smart=smart_mode=='apply' and mode!='preserve'
            cfg.apply_high_confidence_sound_changes = apply_smart
            cfg.apply_existing_fx_sends = apply_smart
            cfg.preserve_controllers = not apply_smart
        apply_export_preset(cfg,export_preset)
        if full_optimization_test:
            cfg.enable_autonomous_baja_max()
            self.worker_queue.put(('log','[AUTHORITY] FACTORY + GOLD MAX AUTONOMOUS: dominantni izvor se bira po zadatku; velocity=PROFILE_ONLY.\n'))
            model_path=self._trained_model_path()
            try:
                model=load_encoder_model(model_path,require_accepted=True,migrate_legacy=True)
            except Exception as exc:
                self.worker_queue.put(('log','[NEURAL] FULL_TEST nastavlja bez neuralnih timing/gate korekcija: aktivni model nije prihvaćen (%s).\n'%exc))
            else:
                cfg.apply_trained_rhythm_model=True;cfg.trained_rhythm_model_path=str(model_path);cfg.trained_rhythm_only=False;cfg.velocity_factory_data_only=True
                migration=model.get('migration') or {};self.worker_queue.put(('log','[NEURAL] FULL_TEST koristi prihvaćeni aktivni model samo za timing/gate; velocity i Voice ostaju pod Factory autoritetom.%s\n'%(' Legacy 36-D model je automatski migriran na 33-D bez ponovnog treninga.' if migration else '')))
        if trained_rhythm_apply:
            cfg.mode='natural';cfg.export_preset='auto';cfg.autopilot=False;cfg.enable_velocity=False;cfg.velocity_strength=0.0;cfg.enable_velocity_conductor=False;cfg.velocity_conductor_strength=0.0;cfg.enable_gate=False;cfg.gate_strength=0.0
            cfg.enable_sound_kit_selector=False;cfg.apply_high_confidence_sound_changes=False;cfg.enable_fx_intelligence=False;cfg.apply_existing_fx_sends=False;cfg.enable_articulation_director=False;cfg.apply_articulation_triggers=False;cfg.auto_apply_safe_voice_upgrades=False
            cfg.enable_performance_director=True;cfg.apply_performance_director=False;cfg.enable_mix_fx_director=False;cfg.apply_mix_fx_director=False;cfg.mix_fx_policy='off';cfg.enable_timing=True;cfg.timing_strength=1.0;cfg.apply_trained_rhythm_model=True;cfg.trained_rhythm_model_path=str(self._trained_model_path());cfg.trained_rhythm_only=True;cfg.velocity_factory_data_only=True;variant_label='trained_rhythm'
        session=WorkstationSession(Path(out_dir)/'PA800_WORKSTATION_SESSION.json');session.begin_batch(paths,{**asdict(cfg),'suffix':suffix,'output_dir':str(out_dir),'variant_label':variant_label})
        current={'input':None}
        def phase_callback(phase,details):
            if current['input'] is not None:
                session.record_phase(current['input'],phase,details)
                self.worker_queue.put(('log','[PHASE] %s | %s | %s\n'%(current['input'].name,phase,json.dumps(details,ensure_ascii=False,sort_keys=True,default=str))))
        optimizer = Optimizer(cfg,phase_callback=phase_callback)
        ok = 0
        skipped = 0
        failed = 0
        cancelled=False;manifest_rows=[]
        for idx, inp in enumerate(paths, 1):
            if self.cancel_event.is_set():cancelled=True;break
            current['input']=inp
            self.worker_queue.put(('log','\n[FILE_START] %d/%d | %s | bytes=%d | mode=%s | export=%s | neural=%s\n'%(idx,len(paths),inp.name,inp.stat().st_size,mode,export_preset,bool(cfg.apply_trained_rhythm_model))))
            out = output_path_for(inp, out_dir, suffix)
            report = out.with_suffix(out.suffix + '.report.json')
            if out.exists() and not overwrite:
                skipped += 1
                self.worker_queue.put(('log', f'[SKIP] {inp.name} -> postoji: {out.name}\n'))
                manifest_rows.append({'input':str(inp),'output':str(out),'status':'SKIP_EXISTS'})
                try:session.finish_file(inp,'SKIP_EXISTS',out,None)
                except Exception as exc:self.worker_queue.put(('log',f'[WARN] Session SKIP zapis nije snimljen: {exc}\n'))
                self.worker_queue.put(('progress', idx, len(paths), inp.name))
                continue
            try:
                rep = optimizer.optimize(str(inp), str(out), str(report))
                ok += 1
                mixer=build_mixer_snapshot(rep);variant=None
                try:variant=session.record_variant(inp,out,report,asdict(cfg),variant_label,mixer);session.finish_file(inp,'PASS',out,report)
                except Exception as exc:self.worker_queue.put(('log',f'[WARN] MIDI je commitovan, ali session zapis nije uspio: {exc}\n'))
                intel = rep.intelligence or []
                auto = sum(1 for x in intel if str(x.get('sound_apply_status','')).startswith('applied'))
                fxn = sum(int(x.get('fx_send_changes') or 0) for x in intel)
                sug = sum(1 for x in intel if x.get('action') == 'SUGGEST_ONLY')
                conf=(rep.content_detection or {}).get('confidence')
                pilot=rep.automation_decision or {};pilot_mode=pilot.get('mode',mode);pilot_smart=pilot.get('effective_smart_policy',smart_mode)
                repairs=(rep.midi_repair or {}).get('repair_count',0)
                vnorm=(rep.velocity_conductor or {}).get('global_normalized_median_after')
                arts=(rep.articulations or {}).get('applied_triggers',0)
                change_kinds=(rep.change_summary or {}).get('by_kind') or {}
                neural=(rep.workstation or {}).get('trained_rhythm_application') or {}
                instrument_application=(rep.workstation or {}).get('instrument_application') or {};instrument_rows=instrument_application.get('contexts') or [];instrument_families=sorted({str(row.get('policy_family')) for row in instrument_rows if row.get('policy_family')})
                solo=(rep.performance_director or {});solo_tracks=solo.get('solo_track_count',0);trills=solo.get('trill_count',0);ornaments=solo.get('ornament_count',0);expression=solo.get('expression_changes',0)
                music_summary=(rep.musical_understanding or {}).get('musician_summary','')
                brain=(rep.workstation or {}).get('ai_resource_brain') or {}
                self.worker_queue.put(('log','[AI BRAIN] tier=%s threads=%s workers=%s neural=%s->%s RAM=%s/%sMB cost=%s\n' % (brain.get('tier'),brain.get('max_cpu_threads'),brain.get('max_batch_workers'),brain.get('neural_requested'),brain.get('neural_effective'),(brain.get('snapshot') or {}).get('available_memory_mb'),(brain.get('snapshot') or {}).get('total_memory_mb'),brain.get('estimated_cost'))))
                self.worker_queue.put(('log', f'[PASS] {inp.name} -> {out.name} | content={rep.content_type}/{conf} auto={pilot_mode}/{pilot_smart} repair={repairs} changes={len(rep.changes)} timing={change_kinds.get("timing",0)} gate={change_kinds.get("gate",0)} velocity={sum(value for kind,value in change_kinds.items() if str(kind).startswith("velocity"))} neural_proposed={neural.get("timing_proposed_notes",0)}/{neural.get("duration_proposed_notes",0)} solo_tracks={solo_tracks} trills={trills} ornaments={ornaments} expression_cc11={expression} vnorm={vnorm} artic={arts} sound={auto} fx={fxn} quality={rep.quality_gate.get("score_percent")} suggest={sug} warnings={len(rep.warnings)}\n[AUTHORITY] {json.dumps(neural.get("authority_selection",{}),ensure_ascii=False,sort_keys=True)}\n[INSTRUMENT] contexts={len(instrument_rows)} families={','.join(instrument_families)} velocity_authority={instrument_application.get("velocity_authority")} neural_authority={instrument_application.get("neural_authority")}\n[MUSIC] {music_summary}\n'))
                manifest_rows.append({'input':str(inp),'output':str(out),'report':str(report),'status':'PASS','verifier':bool(rep.verifier.get('pass'))})
                self.worker_queue.put(('audit',json.dumps({'file':inp.name,'output':out.name,'workstation':rep.workstation,'authority_ledger':rep.authority_ledger,'quality_gate':rep.quality_gate,'content':rep.content_detection,'compatibility':rep.compatibility,'musical_context':rep.musical_context,'pattern_advisor':rep.pattern_advisor,'performance_director':rep.performance_director,'mix_fx_director':rep.mix_fx_director,'automation':rep.automation_decision,'doctor':rep.midi_repair,'velocity':rep.velocity_conductor,'hardware_evidence':rep.hardware_evidence,'voice_fx':rep.intelligence,'articulations':rep.articulations,'audition_queue':rep.audition_queue,'change_summary':rep.change_summary,'verifier':rep.verifier},indent=2,ensure_ascii=False)))
                self.worker_queue.put(('context',json.dumps(rep.musical_context,indent=2,ensure_ascii=False)))
                self.worker_queue.put(('pattern_advisor',json.dumps(rep.pattern_advisor,indent=2,ensure_ascii=False)))
                self.worker_queue.put(('audition',json.dumps(rep.audition_queue,indent=2,ensure_ascii=False)))
                self.worker_queue.put(('repair_context',str(inp),str(out),str(report)))
                self.worker_queue.put(('mix_fx',json.dumps(rep.mix_fx_director,indent=2,ensure_ascii=False)))
                self.worker_queue.put(('compatibility',json.dumps(rep.compatibility,indent=2,ensure_ascii=False)))
                self.worker_queue.put(('mixer',mixer))
                self.worker_queue.put(('session',json.dumps({'active_variant':variant,'session':session.data},indent=2,ensure_ascii=False)))
                self.worker_queue.put(('quality',json.dumps({'quality_gate':rep.quality_gate,'authority_ledger':rep.authority_ledger},indent=2,ensure_ascii=False)))
                self.worker_queue.put(('musician',render_dashboard(rep.musician_workflow)))
                self.worker_queue.put(('factory_usage',render_factory_usage_dashboard(rep.factory_usage_meter)))
            except Exception as e:
                failed += 1
                try:session.finish_file(inp,'FAIL',out,report,e)
                except Exception:pass
                manifest_rows.append({'input':str(inp),'output':str(out),'status':'FAIL','error':repr(e)})
                self.worker_queue.put(('log', '[FAIL] %s: %s\n[TRACEBACK]\n%s\n'%(inp.name,e,traceback.format_exc())))
            self.worker_queue.put(('progress', idx, len(paths), inp.name))
        try:session.finish_batch(cancelled)
        except Exception as exc:self.worker_queue.put(('log',f'[WARN] Session batch status nije snimljen: {exc}\n'))
        try:
            manifest=Path(out_dir)/'PA800_BATCH_RESUME.json';tmp=manifest.with_suffix('.json.tmp');tmp.write_text(json.dumps({'schema':'PA800_BATCH_RESUME_V2','session':'PA800_WORKSTATION_SESSION.json','cancelled':cancelled,'total':len(paths),'rows':manifest_rows},indent=2,ensure_ascii=False),encoding='utf-8');tmp.replace(manifest)
        except Exception as exc:self.worker_queue.put(('log',f'[WARN] Resume manifest nije snimljen: {exc}\n'))
        self.worker_queue.put(('done', ok, skipped, failed, len(paths),cancelled))

    def _poll_worker(self):
        try:
            while True:
                msg = self.worker_queue.get_nowait()
                kind = msg[0]
                if kind == 'log':
                    self._append_log(msg[1])
                elif kind == 'progress':
                    _, current, total, name = msg
                    self.progress.configure(value=current, maximum=max(1, total))
                    self.status.set(f'{current}/{total}: {name}')
                elif kind == 'done':
                    _, ok, skipped, failed, total, cancelled = msg
                    self.is_running = False
                    self.btn_selected.configure(state='normal')
                    self.btn_all.configure(state='normal')
                    self.btn_full_test.configure(state='normal')
                    self.btn_apply_training.configure(state='normal' if self._trained_model_accepted() else 'disabled')
                    self.btn_cancel.configure(state='disabled')
                    self.status.set(('Otkazano' if cancelled else 'Završeno')+f': PASS {ok}, SKIP {skipped}, FAIL {failed}')
                    self._append_log(f'=== {"CANCELLED" if cancelled else "DONE"}: PASS={ok} SKIP={skipped} FAIL={failed} TOTAL={total} ===\n')
                    if failed:
                        messagebox.showwarning('Batch završen', f'PASS: {ok}\nSKIP: {skipped}\nFAIL: {failed}')
                    elif not cancelled:
                        messagebox.showinfo('Batch završen', f'PASS: {ok}\nSKIP: {skipped}\nOutput: {self.output_dir.get()}')
                elif kind=='training_log':self._append_training_log(msg[1])
                elif kind=='training_done':
                    self.is_training=False;self.btn_train.configure(state='normal');self.btn_audit_training.configure(state='normal');self.training_progress.stop();code,model,logs=msg[1:]
                    if code==0:self.btn_activate_candidate.configure(state='normal');self.training_status.set('Kandidat je prošao acceptance — aktivni model NIJE promijenjen');self._append_training_log('=== CANDIDATE TRAINING + ACCEPTANCE PASS ===\nCandidate: %s\nActive model unchanged: %s\nLogovi: %s\n'%(model,self._trained_model_path(),logs));messagebox.showinfo('Trening','Kandidat je završen. Aktivni model nije promijenjen.\n\nZa primjenu klikni AKTIVIRAJ KANDIDATA.\n\nKandidat: %s'%model)
                    else:self.btn_apply_training.configure(state='disabled');self.training_status.set('Trening nije prošao acceptance/confidence gate');self._append_training_log('=== TRAINING / ACCEPTANCE FAIL (exit %s) ===\n'%code);messagebox.showerror('Trening','Model nije prošao acceptance/confidence gate. Detalji su prikazani u GUI logu.')
                elif kind=='training_failed':
                    self.is_training=False;self.btn_train.configure(state='normal');self.btn_audit_training.configure(state='normal');self.training_progress.stop();self.training_status.set('Greška treninga');self._append_training_log('[FATAL] '+msg[1]+'\n');messagebox.showerror('Trening',msg[1])
                elif kind=='training_audit_done':
                    self.is_training=False;self.btn_train.configure(state='normal');self.btn_audit_training.configure(state='normal');self.training_progress.stop();code=msg[1]
                    self.training_status.set('Folder je spreman za trening' if code==0 else 'Folder nije spreman — vidi razloge u logu')
                    messagebox.showinfo('Training folder audit','Audit je završen. Detalji su prikazani u GUI logu.') if code==0 else messagebox.showwarning('Training folder audit','Audit nije prošao. Pogledaj REJECT redove i split sažetak u GUI logu.')
                elif kind=='audit':
                    self.audit_text.configure(state='normal');self.audit_text.delete('1.0','end');self.audit_text.insert('1.0',msg[1]);self.audit_text.configure(state='disabled')
                elif kind=='context':
                    self.context_text.configure(state='normal');self.context_text.delete('1.0','end');self.context_text.insert('1.0',msg[1]);self.context_text.configure(state='disabled')
                elif kind=='pattern_advisor':
                    self.pattern_text.configure(state='normal');self.pattern_text.delete('1.0','end');self.pattern_text.insert('1.0',msg[1]);self.pattern_text.configure(state='disabled')
                elif kind=='pattern_generation_file':
                    payload=msg[1];self.pattern_text.configure(state='normal');self.pattern_text.delete('1.0','end');self.pattern_text.insert('1.0',json.dumps(payload,indent=2,ensure_ascii=False));self.pattern_text.configure(state='disabled');self.pattern_generation_status.set('PASS: %s | pitch nota=%s'%(Path(payload['output']).name,payload.get('summary',{}).get('pitch_changed_notes',0)))
                elif kind=='pattern_generation_done':
                    _kind,ok,skipped,failed,total=msg;self.btn_generate_pattern.configure(state='normal');self.pattern_generation_status.set('Gotovo: PASS=%d SKIP=%d FAIL=%d TOTAL=%d'%(ok,skipped,failed,total));messagebox.showinfo('Pattern iz akorda','Generisanje završeno.\n\nPASS=%d  SKIP=%d  FAIL=%d'%(ok,skipped,failed))
                elif kind=='pattern_generation_error':
                    self.pattern_text.configure(state='normal');self.pattern_text.delete('1.0','end');self.pattern_text.insert('1.0',msg[1]);self.pattern_text.configure(state='disabled');self.pattern_generation_status.set('FAIL — detalji su u Pattern Brain logu')
                elif kind=='audition':
                    self.audition_text.configure(state='normal');self.audition_text.delete('1.0','end');self.audition_text.insert('1.0',msg[1]);self.audition_text.configure(state='disabled')
                elif kind=='repair_context':
                    self._latest_repair_context={'input':msg[1],'base':msg[2],'report':msg[3]}
                    for button in self.repair_variant_buttons:button.configure(state='normal')
                elif kind=='mix_fx':
                    self.mix_fx_text.configure(state='normal');self.mix_fx_text.delete('1.0','end');self.mix_fx_text.insert('1.0',msg[1]);self.mix_fx_text.configure(state='disabled')
                elif kind=='compatibility':
                    self.compatibility_text.configure(state='normal');self.compatibility_text.delete('1.0','end');self.compatibility_text.insert('1.0',msg[1]);self.compatibility_text.configure(state='disabled')
                elif kind=='mixer':self._render_mixer(msg[1])
                elif kind=='session':
                    self.session_text.configure(state='normal');self.session_text.delete('1.0','end');self.session_text.insert('1.0',msg[1]);self.session_text.configure(state='disabled')
                elif kind=='quality':
                    self.quality_text.configure(state='normal');self.quality_text.delete('1.0','end');self.quality_text.insert('1.0',msg[1]);self.quality_text.configure(state='disabled')
                elif kind=='musician':
                    self.musician_text.configure(state='normal');self.musician_text.delete('1.0','end');self.musician_text.insert('1.0',msg[1]);self.musician_text.configure(state='disabled')
                elif kind=='factory_usage':
                    self.factory_usage_text.configure(state='normal');self.factory_usage_text.delete('1.0','end');self.factory_usage_text.insert('1.0',msg[1]);self.factory_usage_text.configure(state='disabled')
        except queue.Empty:
            pass
        self.after(120, self._poll_worker)

    def _append_log(self, text):
        self.log.configure(state='normal')
        self.log.insert('end', text)
        self.log.see('end')
        self.log.configure(state='disabled')

    def _cancel_batch(self):
        if self.is_running:self.cancel_event.set();self.status.set('Otkazivanje nakon trenutnog fajla...')

    def _on_close(self):
        self._remember_settings()
        self.destroy()

    def _build_audit(self):
        self.audit_text=tk.Text(self.audit_tab,wrap='none',state='disabled');ys=ttk.Scrollbar(self.audit_tab,orient='vertical',command=self.audit_text.yview);xs=ttk.Scrollbar(self.audit_tab,orient='horizontal',command=self.audit_text.xview);self.audit_text.configure(yscrollcommand=ys.set,xscrollcommand=xs.set);self.audit_text.grid(row=0,column=0,sticky='nsew');ys.grid(row=0,column=1,sticky='ns');xs.grid(row=1,column=0,sticky='ew');self.audit_tab.rowconfigure(0,weight=1);self.audit_tab.columnconfigure(0,weight=1)

    def _build_context_view(self):
        self.context_text=tk.Text(self.context_tab,wrap='none',state='disabled');ys=ttk.Scrollbar(self.context_tab,orient='vertical',command=self.context_text.yview);xs=ttk.Scrollbar(self.context_tab,orient='horizontal',command=self.context_text.xview);self.context_text.configure(yscrollcommand=ys.set,xscrollcommand=xs.set);self.context_text.grid(row=0,column=0,sticky='nsew');ys.grid(row=0,column=1,sticky='ns');xs.grid(row=1,column=0,sticky='ew');self.context_tab.rowconfigure(0,weight=1);self.context_tab.columnconfigure(0,weight=1)

    def _build_pattern_view(self):
        self.pattern_chords=tk.StringVar(value=self.settings.get('pattern_chords','C | Am | F | G7'));self.pattern_include_solo=tk.BooleanVar(value=bool(self.settings.get('pattern_include_solo',True)));self.pattern_generation_status=tk.StringVar(value='Odaberi template MIDI u tabu Optimizer, zatim upiši po jedan akord za svaki takt.')
        top=ttk.LabelFrame(self.pattern_tab,text='Profesionalni chord-conditioned Pattern Generator');top.grid(row=0,column=0,columnspan=2,sticky='ew',padx=8,pady=8)
        ttk.Label(top,text='Akordi').grid(row=0,column=0,sticky='w',padx=8,pady=7);entry=ttk.Entry(top,textvariable=self.pattern_chords);entry.grid(row=0,column=1,sticky='ew',padx=8,pady=7);entry.bind('<FocusOut>',lambda _event:self._remember_settings())
        ttk.Checkbutton(top,text='Revoice Solo/Lead',variable=self.pattern_include_solo,command=self._remember_settings).grid(row=0,column=2,padx=8,pady=7)
        self.btn_generate_pattern=ttk.Button(top,text='GENERISI PATTERN IZ AKORDA',command=self._start_pattern_generation);self.btn_generate_pattern.grid(row=0,column=3,padx=8,pady=7)
        ttk.Label(top,text='Primjer: C | Am | F | G7 · ponavljanje: C*2 · slash bass: C/E · podržani maj7, m7, dim, aug, sus2/4 i power5.',foreground='#555').grid(row=1,column=0,columnspan=4,sticky='w',padx=8,pady=(0,4))
        ttk.Label(top,text='Factory/Gold template čuva ritam, velocity, gate, Sound, RX/DNC, kontrolere i dužinu; generator mijenja samo verifikovani pitch.',foreground='#555').grid(row=2,column=0,columnspan=4,sticky='w',padx=8,pady=(0,4))
        ttk.Label(top,textvariable=self.pattern_generation_status).grid(row=3,column=0,columnspan=4,sticky='w',padx=8,pady=(0,7));top.columnconfigure(1,weight=1)
        self.pattern_text=tk.Text(self.pattern_tab,wrap='none',state='disabled');ys=ttk.Scrollbar(self.pattern_tab,orient='vertical',command=self.pattern_text.yview);xs=ttk.Scrollbar(self.pattern_tab,orient='horizontal',command=self.pattern_text.xview);self.pattern_text.configure(yscrollcommand=ys.set,xscrollcommand=xs.set);self.pattern_text.grid(row=1,column=0,sticky='nsew');ys.grid(row=1,column=1,sticky='ns');xs.grid(row=2,column=0,sticky='ew');self.pattern_tab.rowconfigure(1,weight=1);self.pattern_tab.columnconfigure(0,weight=1)

    def _start_pattern_generation(self):
        paths=self._selected_paths()
        if not paths:return messagebox.showwarning('Pattern Generator','U tabu Optimizer odaberi jedan ili više Factory/Gold/template MIDI fajlova.')
        try:chords=parse_chord_progression(self.pattern_chords.get())
        except Exception as exc:return messagebox.showerror('Akordi',str(exc))
        out_dir=Path(self.output_dir.get()) if self.output_dir.get() else None
        if out_dir is None:return messagebox.showerror('Output folder','U tabu Optimizer izaberi OUTPUT folder.')
        try:out_dir.mkdir(parents=True,exist_ok=True)
        except Exception as exc:return messagebox.showerror('Output folder',str(exc))
        preview=' | '.join(row['label'] for row in chords[:16])+(' | ...' if len(chords)>16 else '')
        if not messagebox.askyesno('Generisi pattern iz akorda','Template fajlova: %d\nAkordi: %s\n\nRitam, velocity, gate, Sound/RX/DNC, CC i struktura ostaju identični. Mijenja se samo dozvoljeni tonalni pitch. Neuralni model se ne trenira. Nastaviti?'%(len(paths),preview)):return
        self._remember_settings();self.btn_generate_pattern.configure(state='disabled');self.pattern_generation_status.set('Generisanje i pitch-only verifikacija u toku...')
        threading.Thread(target=self._pattern_generation_worker,args=(paths,out_dir,self.pattern_chords.get(),self.pattern_include_solo.get(),self.content_type.get(),self.overwrite.get()),daemon=True).start()

    def _pattern_generation_worker(self,paths,out_dir,progression,include_solo,content_type,overwrite):
        ok=skipped=failed=0
        for path in paths:
            output=Path(out_dir)/(Path(path).stem+'_CHORD_PATTERN.mid')
            if output.exists() and not overwrite:
                skipped+=1;continue
            try:
                report=generate_chord_pattern(path,output,progression,include_solo=include_solo,content_type=content_type);ok+=1;self.worker_queue.put(('pattern_generation_file',report))
            except Exception:
                failed+=1;self.worker_queue.put(('pattern_generation_error','[FAIL] %s\n%s'%(Path(path).name,traceback.format_exc())))
        self.worker_queue.put(('pattern_generation_done',ok,skipped,failed,len(paths)))

    def _build_audition_view(self):
        tools=ttk.Frame(self.audition_tab);tools.grid(row=0,column=0,columnspan=2,sticky='ew',padx=8,pady=8)
        self.repair_variant_buttons=[]
        for label in ('Repair','Natural','Expressive'):
            button=ttk.Button(tools,text='ACCEPT '+label.upper(),state='disabled',command=lambda value=label:self._apply_repair_variant(value));button.pack(side='left',padx=(0,6));self.repair_variant_buttons.append(button)
        ttk.Button(tools,text='REJECT ALL',command=self._reject_repair_variants).pack(side='left',padx=(8,0))
        ttk.Label(tools,text='A/B menja samo exact Factory velocity; ritam i trileri ostaju iz verifikovanog outputa.',foreground='#666').pack(side='left',padx=12)
        self.audition_text=tk.Text(self.audition_tab,wrap='none',state='disabled');ys=ttk.Scrollbar(self.audition_tab,orient='vertical',command=self.audition_text.yview);xs=ttk.Scrollbar(self.audition_tab,orient='horizontal',command=self.audition_text.xview);self.audition_text.configure(yscrollcommand=ys.set,xscrollcommand=xs.set);self.audition_text.grid(row=1,column=0,sticky='nsew');ys.grid(row=1,column=1,sticky='ns');xs.grid(row=2,column=0,sticky='ew');self.audition_tab.rowconfigure(1,weight=1);self.audition_tab.columnconfigure(0,weight=1)

    def _apply_repair_variant(self,label):
        context=self._latest_repair_context
        if not context:return messagebox.showwarning('A/B Audition','Prvo pokreni optimizaciju MIDI fajla.')
        base=Path(context['base']);out_dir=Path(self.output_dir.get() or base.parent);output=out_dir/(base.stem+'_AB_'+label.upper()+base.suffix)
        try:
            preview=_describe_repair_variant(base,context['report'],label);keys=preview['affected_note_keys'];shown='\n'.join('track=%s ch=%s note=%s occurrence=%s'%tuple(key) for key in keys[:8]);extra='\n... +%d nota'%(len(keys)-8) if len(keys)>8 else ''
            if not messagebox.askyesno('A/B Audition',f'Kreirati posebnu {label} varijantu?\n\n{output.name}\n\nTačno Factory velocity promjena: {len(keys)}\n{shown}{extra}'):return
            result=_create_repair_variant(base,context['report'],output,label)
            session=WorkstationSession(self._session_path() or (out_dir/'PA800_WORKSTATION_SESSION.json'));variant=session.record_variant(context['input'],output,result['sidecar'],{'repair_variant':label,'factory_data_only':True},'A/B '+label);session._record_audition_decision('ACCEPT',label,context['input'],output,context['report'],{'variant_id':variant['id'],'applied_velocity_changes':result['applied_velocity_changes']})
            self._refresh_session_view();messagebox.showinfo('A/B Audition',f'Kreirano: {output.name}\nFactory velocity promjene: {result["applied_velocity_changes"]}')
        except Exception as exc:messagebox.showerror('A/B Audition',str(exc))

    def _reject_repair_variants(self):
        context=self._latest_repair_context
        if not context:return
        path=self._session_path()
        if path:WorkstationSession(path)._record_audition_decision('REJECT',None,context['input'],None,context['report'],{'reason':'musician_rejected_all_ab_variants'})
        self._latest_repair_context=None
        for button in self.repair_variant_buttons:button.configure(state='disabled')
        self._refresh_session_view();messagebox.showinfo('A/B Audition','Kandidati su odbijeni. Nijedan MIDI fajl nije promijenjen.')

    def _build_mix_fx_view(self):
        self.mix_fx_text=tk.Text(self.mix_fx_tab,wrap='none',state='disabled');ys=ttk.Scrollbar(self.mix_fx_tab,orient='vertical',command=self.mix_fx_text.yview);xs=ttk.Scrollbar(self.mix_fx_tab,orient='horizontal',command=self.mix_fx_text.xview);self.mix_fx_text.configure(yscrollcommand=ys.set,xscrollcommand=xs.set);self.mix_fx_text.grid(row=0,column=0,sticky='nsew');ys.grid(row=0,column=1,sticky='ns');xs.grid(row=1,column=0,sticky='ew');self.mix_fx_tab.rowconfigure(0,weight=1);self.mix_fx_tab.columnconfigure(0,weight=1)

    def _build_compatibility_view(self):
        self.compatibility_text=tk.Text(self.compatibility_tab,wrap='none',state='disabled');ys=ttk.Scrollbar(self.compatibility_tab,orient='vertical',command=self.compatibility_text.yview);xs=ttk.Scrollbar(self.compatibility_tab,orient='horizontal',command=self.compatibility_text.xview);self.compatibility_text.configure(yscrollcommand=ys.set,xscrollcommand=xs.set);self.compatibility_text.grid(row=0,column=0,sticky='nsew');ys.grid(row=0,column=1,sticky='ns');xs.grid(row=1,column=0,sticky='ew');self.compatibility_tab.rowconfigure(0,weight=1);self.compatibility_tab.columnconfigure(0,weight=1)

    def _build_mixer_view(self):
        columns=('Track','Ch','Function','Family','Sound','Vel before','Vel after','FX','Voice','Evidence');self.mixer_tree=ttk.Treeview(self.mixer_tab,columns=columns,show='headings')
        widths=(55,40,125,95,180,80,80,135,130,70)
        for column,width in zip(columns,widths):self.mixer_tree.heading(column,text=column);self.mixer_tree.column(column,width=width,anchor='center')
        scroll=ttk.Scrollbar(self.mixer_tab,orient='vertical',command=self.mixer_tree.yview);self.mixer_tree.configure(yscrollcommand=scroll.set);self.mixer_tree.pack(side='left',fill='both',expand=True);scroll.pack(side='right',fill='y')

    def _render_mixer(self,snapshot):
        for item in self.mixer_tree.get_children():self.mixer_tree.delete(item)
        for row in snapshot.get('rows',[]):
            self.mixer_tree.insert('', 'end',values=(row.get('track'),row.get('channel'),row.get('function'),row.get('family'),row.get('sound'),row.get('velocity_before'),row.get('velocity_after'),row.get('fx_status'),row.get('voice_status'),row.get('evidence_level')))

    def _session_path(self):
        return Path(self.output_dir.get())/'PA800_WORKSTATION_SESSION.json' if self.output_dir.get() else None

    def _refresh_session_view(self):
        path=self._session_path()
        if not path or not path.exists():payload={'status':'NO_SESSION','expected_path':str(path) if path else None}
        else:payload=WorkstationSession(path).data
        self.session_text.configure(state='normal');self.session_text.delete('1.0','end');self.session_text.insert('1.0',json.dumps(payload,indent=2,ensure_ascii=False));self.session_text.configure(state='disabled')

    def _undo_session(self):
        path=self._session_path()
        if not path or not path.exists():messagebox.showwarning('Session','Nema session manifesta u OUTPUT folderu.');return
        WorkstationSession(path).undo();self._refresh_session_view()

    def _redo_session(self):
        path=self._session_path()
        if not path or not path.exists():messagebox.showwarning('Session','Nema session manifesta u OUTPUT folderu.');return
        WorkstationSession(path).redo();self._refresh_session_view()

    def _attach_audio_reference(self):
        path=self._session_path()
        if not path or not path.exists():messagebox.showwarning('Session','Prvo napravi bar jednu output varijantu.');return
        audio=filedialog.askopenfilename(title='Izaberi audio A/B reference',filetypes=[('WAV','*.wav'),('Audio','*.wav *.aif *.aiff'),('All files','*.*')])
        if audio:WorkstationSession(path).attach_audio(audio);self._refresh_session_view()

    def _build_session_view(self):
        toolbar=ttk.Frame(self.session_tab);toolbar.pack(fill='x',padx=8,pady=8);ttk.Button(toolbar,text='REFRESH',command=self._refresh_session_view).pack(side='left');ttk.Button(toolbar,text='UNDO ACTIVE',command=self._undo_session).pack(side='left',padx=6);ttk.Button(toolbar,text='REDO ACTIVE',command=self._redo_session).pack(side='left');ttk.Button(toolbar,text='ATTACH AUDIO A/B',command=self._attach_audio_reference).pack(side='left',padx=12);ttk.Label(toolbar,text='Undo/redo ne briše MIDI fajlove; mijenja samo aktivnu varijantu.',foreground='#666').pack(side='left')
        self.session_text=tk.Text(self.session_tab,wrap='none',state='disabled');self.session_text.pack(fill='both',expand=True,padx=8,pady=(0,8))

    def _build_quality_view(self):
        self.quality_text=tk.Text(self.quality_tab,wrap='none',state='disabled');self.quality_text.pack(fill='both',expand=True,padx=8,pady=8)

    def _build_musician_view(self):
        self.musician_text=tk.Text(self.musician_tab,wrap='word',state='disabled',font=('TkDefaultFont',11));self.musician_text.pack(fill='both',expand=True,padx=10,pady=10)

    def _build_factory_usage_view(self):
        self.factory_usage_text=tk.Text(self.factory_usage_tab,wrap='none',state='disabled',font=('TkFixedFont',10));ys=ttk.Scrollbar(self.factory_usage_tab,orient='vertical',command=self.factory_usage_text.yview);xs=ttk.Scrollbar(self.factory_usage_tab,orient='horizontal',command=self.factory_usage_text.xview);self.factory_usage_text.configure(yscrollcommand=ys.set,xscrollcommand=xs.set);self.factory_usage_text.grid(row=0,column=0,sticky='nsew',padx=(8,0),pady=(8,0));ys.grid(row=0,column=1,sticky='ns',pady=(8,0));xs.grid(row=1,column=0,sticky='ew',padx=(8,0),pady=(0,8));self.factory_usage_tab.rowconfigure(0,weight=1);self.factory_usage_tab.columnconfigure(0,weight=1)

    # ---------------- Factory MAX Lab ----------------
    def _build_factory(self):
        outer = self.factory_tab
        if not self.atomic.available:
            ttk.Label(outer, text='Factory ATOMIC MAX database not available. Run CreateBaza.bat.').pack(padx=20, pady=20)
            return
        c = self.atomic.corpus()
        head = ttk.Frame(outer)
        head.pack(fill='x', padx=10, pady=8)
        ttk.Label(head, text=f"Factory corpus: {c['styles']} styles   |   {c['notes']:,} Note-On atoms   |   {c['segments']:,} context/sound-state segments", font=('TkDefaultFont',11,'bold')).pack(side='left')
        sub = ttk.Notebook(outer)
        sub.pack(fill='both', expand=True, padx=10, pady=6)
        t1, t2, t3, t4 = ttk.Frame(sub), ttk.Frame(sub), ttk.Frame(sub), ttk.Frame(sub)
        sub.add(t1, text='Elements'); sub.add(t2, text='V1 → V4'); sub.add(t3, text='Techniques'); sub.add(t4, text='Controllers')
        self._elements_view(t1); self._progress_view(t2); self._tech_view(t3); self._controls_view(t4)

    def _tree(self, parent, cols, widths=None):
        tree = ttk.Treeview(parent, columns=cols, show='headings')
        for i, c in enumerate(cols):
            tree.heading(c, text=c)
            tree.column(c, width=(widths[i] if widths else 110), anchor='center')
        y = ttk.Scrollbar(parent, orient='vertical', command=tree.yview)
        tree.configure(yscrollcommand=y.set)
        tree.pack(side='left', fill='both', expand=True)
        y.pack(side='right', fill='y')
        return tree

    def _elements_view(self, parent):
        cols=['Element','Notes','Bars med','Roles med','Notes/bar','Onsets/bar','Repeat','ACC4','ACC5']; tree=self._tree(parent,cols,[130,100,70,80,85,85,75,70,70])
        for e in ELEMENTS:
            x=self.atomic.element(e)
            if not x: continue
            a=x.get('aggregate',{}); rp=x.get('role_presence',{})
            tree.insert('', 'end', values=(e,f"{x.get('notes',0):,}",x.get('bars_median'),x.get('active_roles',{}).get('p50'),a.get('notes_per_bar',{}).get('p50'),a.get('onsets_per_bar',{}).get('p50'),a.get('bar_repeat_similarity',{}).get('p50'),rp.get('ACC4'),rp.get('ACC5')))

    def _progress_view(self, parent):
        cols=['Transition','Role','Rhythm J','Same mask','Same Sound','Δ notes/bar','Δ register','Δ velocity']; tree=self._tree(parent,cols,[90,70,90,90,90,100,95,95])
        for tr in ['V1->V2','V2->V3','V3->V4']:
            for role in ROLES:
                x=self.atomic.variation_progression(tr,role)
                if not x: continue
                tree.insert('', 'end', values=(tr,role,x.get('rhythm_jaccard',{}).get('p50'),x.get('same_rhythm_fraction'),x.get('same_sound_fraction'),x.get('notes_per_bar',{}).get('delta',{}).get('p50'),x.get('register_width',{}).get('delta',{}).get('p50'),x.get('velocity_p50',{}).get('delta',{}).get('p50')))

    def _tech_view(self, parent):
        top=ttk.Frame(parent); top.pack(fill='x',pady=5)
        fam=tk.StringVar(value='ALL'); el=tk.StringVar(value='ALL')
        ttk.Label(top,text='Family').pack(side='left'); ttk.Combobox(top,textvariable=fam,values=['ALL','DRUM_KIT','PERCUSSION','BASS','GUITAR','PIANO','ORGAN','ACCORDION_REED','STRINGS','BRASS','WOODWIND','PAD','SYNTH_LEAD','MALLET','PLUCK','SFX','OTHER_ACC','OTHER'],state='readonly',width=18).pack(side='left',padx=5)
        ttk.Label(top,text='Element').pack(side='left'); ttk.Combobox(top,textvariable=el,values=['ALL']+ELEMENTS,state='readonly',width=16).pack(side='left',padx=5)
        body=ttk.Frame(parent); body.pack(fill='both',expand=True)
        cols=['Family','Role','Element','Notes','Ghost','Accent','Stacc','Legato','Dead/Mute','Strums','Trill','Trem','Grace','Special']; tree=self._tree(body,cols,[110,60,105,85,65,65,65,65,75,70,55,55,55,70])
        def refresh(*_):
            for i in tree.get_children(): tree.delete(i)
            rows=self.atomic.techniques_for(None if fam.get()=='ALL' else fam.get(),None,None if el.get()=='ALL' else el.get())
            for r in rows[:500]:
                tree.insert('', 'end', values=(r.get('family'),r.get('role'),r.get('element'),r.get('notes'),round(float(r.get('ghost_candidate_fraction') or 0),3),round(float(r.get('accent_candidate_fraction') or 0),3),round(float(r.get('staccato_fraction') or 0),3),round(float(r.get('legato_overlap_fraction') or 0),3),round(float(r.get('dead_mute_candidate_fraction') or 0),3),r.get('strum_candidates'),r.get('trill_runs'),r.get('tremolo_runs'),r.get('grace_candidates'),r.get('special_pitch_notes')))
        fam.trace_add('write',refresh); el.trace_add('write',refresh); refresh()

    def _controls_view(self, parent):
        txt=tk.Text(parent,wrap='word'); txt.pack(fill='both',expand=True,padx=8,pady=8)
        gc=self.atomic.controls.get('global_counts',{}); thr=self.atomic.controls.get('cc_threshold_summary',{})
        lines=['FACTORY CONTROLLER FORENSICS\n','All values are observations, not automatic articulation meanings.\n\n']
        for cc in [22,1,2,7,11,64,80,81]:
            lines.append(f'CC{cc}: {gc.get("cc:"+str(cc),0):,}')
            if str(cc) in thr: lines.append('  '+json_compact(thr[str(cc)]))
            lines.append('\n')
        lines.append(f'Pitch Bend: {gc.get("pb",0):,}\nChannel Aftertouch: {gc.get("ch_at",0):,}\nPoly Aftertouch: {gc.get("poly_at",0):,}\n')
        lines.append(f'NRPN sequences: {len(self.atomic.controls.get("nrpn_sequences",[]))}\nRPN sequences: {len(self.atomic.controls.get("rpn_sequences",[]))}\n')
        lines.append(f'CC80 Sound contexts: {len(self.atomic.controls.get("cc80_sounds",[]))}; CC81 Sound contexts: {len(self.atomic.controls.get("cc81_sounds",[]))}\n')
        txt.insert('1.0',''.join(lines)); txt.configure(state='disabled')


def json_compact(x):
    return ', '.join(f'{k}={v}' for k,v in x.items())


def main():
    App().mainloop()


if __name__ == '__main__':
    main()
