"""Batch MIDI through Factory velocity + Gold performance authority.

Groups outputs into folders of 100 and writes a .tex catalog for each batch
so the set can be described (žanr, tempo, Factory/Gold autoritet).
"""
from __future__ import annotations

import argparse
import json
import sys
import traceback
import zipfile
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

MIDI_SUFFIXES = {".mid", ".midi", ".kar"}
BATCH_SIZE = 100


def _collect(source: Path) -> list[Path]:
    if source.is_file() and source.suffix.lower() in {".zip"}:
        dest = source.with_name(source.stem + "_extracted")
        dest.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(source) as archive:
            archive.extractall(dest)
        source = dest
    if source.is_file() and source.suffix.lower() in MIDI_SUFFIXES:
        return [source]
    files = [p for p in source.rglob("*") if p.is_file() and p.suffix.lower() in MIDI_SUFFIXES]
    return sorted(files, key=lambda p: str(p).lower())


def _tex_escape(text) -> str:
    repl = {
        "\\": r"\textbackslash{}",
        "&": r"\&",
        "%": r"\%",
        "$": r"\$",
        "#": r"\#",
        "_": r"\_",
        "{": r"\{",
        "}": r"\}",
        "~": r"\textasciitilde{}",
        "^": r"\textasciicircum{}",
    }
    return "".join(repl.get(ch, ch) for ch in str(text))


def _authority_block() -> str:
    return r"""
\section{Autoritet (obavezno za deskripciju)}
\begin{itemize}
  \item \textbf{Velocity} --- isključivo Factory profil (\texttt{PROFILE\_ONLY}). Neural ne smije pisati velocity.
  \item \textbf{Gold} --- groove, drum/bass pattern, strum, fill sadržaj, solo fraze, Expression CC11, ukrasi --- tamo gdje evidencija dopušta apply.
  \item \textbf{Factory veto} --- PA800 struktura, Guitar Mode / PowerChord voicing, Brass, Strings/Pad, RX/DNC zaštita.
\end{itemize}
"""


def factory_gold_config():
    from pa800_optimizer.config import OptimizeConfig

    cfg = OptimizeConfig()
    # Explicit Factory+Gold MAX: velocity stays Factory PROFILE_ONLY.
    # Autopilot is off so a coverage guard cannot lock_preserve after the user
    # already authorized Gold timing/groove/strum/fill/solo/CC11.
    cfg.enable_full_optimization_test()
    cfg.velocity_factory_data_only = True
    cfg.factory_gold_max = True
    cfg.apply_trained_rhythm_model = True
    cfg.trained_rhythm_only = False
    cfg.autopilot = False
    cfg.mode = "max"
    cfg.export_preset = "auto"
    return cfg


def write_batch_tex(path: Path, batch_index: int, rows: list[dict], started: str, batch_size: int = BATCH_SIZE) -> None:
    passed = sum(1 for row in rows if row.get("status") == "PASS")
    failed = sum(1 for row in rows if row.get("status") != "PASS")
    lines = [
        r"\documentclass[11pt,a4paper]{article}",
        r"\usepackage[utf8]{inputenc}",
        r"\usepackage[T1]{fontenc}",
        r"\usepackage[croatian]{babel}",
        r"\usepackage{longtable,booktabs,geometry,hyperref}",
        r"\geometry{margin=22mm}",
        r"\title{Factory+Gold batch %03d}" % batch_index,
        r"\author{PA800 Profile Optimizer}",
        r"\date{%s}" % _tex_escape(started),
        r"\begin{document}",
        r"\maketitle",
        _authority_block(),
        r"\section{Kako deskriptirati ovaj batch}",
        r"U opisu (Drive, Pa800 set lista, YouTube, katalog) napiši tačno ovo:",
        r"\begin{quote}",
        r"\texttt{PA800 Factory+Gold MAX --- batch %03d --- %d MIDI.}\\" % (batch_index, len(rows)),
        r"Velocity = Factory profil (ne Gold, ne neural).\\",
        r"Timing/gate/groove/strum/fill/solo/CC11 = Gold gdje je evidencija dovoljna.\\",
        r"RX/DNC i Voice struktura ostaju Factory veto. Hardware A/B nije urađen.",
        r"\end{quote}",
        r"\section{Sažetak}",
        r"Fajlova: %d. PASS: %d. FAIL: %d. Veličina grupe: %d." % (len(rows), passed, failed, batch_size),
        r"\section{Popis}",
        r"\begin{longtable}{r p{4.2cm} p{4.2cm} r p{2.2cm}}",
        r"\toprule \# & Izvor & Izlaz & Izmjene & Status \\ \midrule",
        r"\endfirsthead",
        r"\toprule \# & Izvor & Izlaz & Izmjene & Status \\ \midrule",
        r"\endhead",
    ]
    for row in rows:
        lines.append(
            "%d & %s & %s & %s & %s \\\\"
            % (
                row["index"],
                _tex_escape(row.get("source_name", "")),
                _tex_escape(Path(row.get("output") or "").name),
                row.get("changes", 0),
                _tex_escape(row.get("status", "")),
            )
        )
    lines += [
        r"\bottomrule",
        r"\end{longtable}",
        r"\section{Polja za tvoj opis (popuni ručno)}",
        r"\begin{itemize}",
        r"\item Žanr / ples: \underline{\hspace{6cm}}",
        r"\item BPM raspon: \underline{\hspace{3cm}}",
        r"\item Tonaliteti: \underline{\hspace{6cm}}",
        r"\item Song ili Style: \underline{\hspace{4cm}}",
        r"\item Pa800 banka / User Style broj: \underline{\hspace{4cm}}",
        r"\item Napomena (live, vokal, rumba, rock\ldots): \underline{\hspace{8cm}}",
        r"\end{itemize}",
        r"\end{document}",
        "",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")


def process_one(optimizer, source: Path, dest: Path, report: Path):
    dest.parent.mkdir(parents=True, exist_ok=True)
    return optimizer.optimize(str(source), str(dest), str(report))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", help="Folder, .zip ili jedan MIDI")
    parser.add_argument("--output", default=str(ROOT.parents[0] / "output" / "factory_gold_batches"))
    parser.add_argument("--batch-size", type=int, default=BATCH_SIZE)
    parser.add_argument("--limit", type=int, default=0, help="0 = svi fajlovi")
    args = parser.parse_args(argv)

    from pa800_optimizer.config import OptimizeConfig
    from pa800_optimizer.optimizer import Optimizer

    cfg = OptimizeConfig()
    # Explicit Factory+Gold MAX: velocity stays Factory PROFILE_ONLY.
    # Autopilot is off so a coverage guard cannot lock_preserve after the user
    # already authorized Gold timing/groove/strum/fill/solo/CC11.
    cfg.enable_full_optimization_test()
    cfg.velocity_factory_data_only = True
    cfg.factory_gold_max = True
    cfg.apply_trained_rhythm_model = True
    cfg.trained_rhythm_only = False
    cfg.autopilot = False
    cfg.mode = "max"
    cfg.export_preset = "auto"
    optimizer = Optimizer(cfg)

    sources = _collect(Path(args.input).expanduser().resolve())
    if args.limit:
        sources = sources[: args.limit]
    if not sources:
        print("Nema MIDI/KAR fajlova u:", args.input)
        return 1

    out_root = Path(args.output).expanduser().resolve()
    out_root.mkdir(parents=True, exist_ok=True)
    started = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    ledger = {
        "schema": "PA800_FACTORY_GOLD_BATCH_V1",
        "started_utc": started,
        "authority": {
            "velocity": "FACTORY_PROFILE_ONLY",
            "timing_gate_groove_strum_fill_solo_cc11": "GOLD_WHERE_EVIDENCE_ALLOWS",
            "structure_rx_dnc_voice": "FACTORY_VETO",
            "neural_velocity": False,
        },
        "batch_size": args.batch_size,
        "source_count": len(sources),
        "batches": [],
    }

    batch_rows: list[dict] = []
    batch_index = 1
    for i, source in enumerate(sources, 1):
        folder = out_root / ("batch_%03d" % batch_index)
        folder.mkdir(parents=True, exist_ok=True)
        stem = "%03d_%s" % (((i - 1) % args.batch_size) + 1, source.stem)
        dest = folder / (stem + "_FG.mid")
        report_path = folder / (stem + "_FG.report.json")
        row = {
            "index": i,
            "source": str(source),
            "source_name": source.name,
            "output": str(dest),
            "report": str(report_path),
        }
        try:
            rep = process_one(optimizer, source, dest, report_path)
            row.update(
                {
                    "status": "PASS",
                    "changes": len(rep.changes),
                    "content_type": rep.content_type,
                    "quality": (rep.quality_gate or {}).get("score_percent"),
                    "verifier": bool((rep.verifier or {}).get("pass")),
                }
            )
            print("PASS", i, "/", len(sources), source.name, "changes=", row["changes"])
        except Exception as exc:
            row.update({"status": "FAIL", "error": repr(exc), "changes": 0})
            (folder / (stem + "_FG.fail.txt")).write_text(traceback.format_exc(), encoding="utf-8")
            print("FAIL", i, "/", len(sources), source.name, ":", exc)
        batch_rows.append(row)
        if i % args.batch_size == 0 or i == len(sources):
            tex = folder / ("batch_%03d.tex" % batch_index)
            js = folder / ("batch_%03d.json" % batch_index)
            write_batch_tex(tex, batch_index, batch_rows, started, args.batch_size)
            js.write_text(json.dumps(batch_rows, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
            ledger["batches"].append(
                {"batch": batch_index, "files": len(batch_rows), "tex": str(tex), "json": str(js)}
            )
            batch_rows = []
            batch_index += 1

    (out_root / "LEDGER.json").write_text(json.dumps(ledger, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print("Gotovo. Batch foldera:", len(ledger["batches"]))
    print("Izlaz:", out_root)
    return 0 if ledger["source_count"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
