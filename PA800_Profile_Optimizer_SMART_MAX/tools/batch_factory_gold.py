"""Batch MIDI through Factory velocity + Gold performance authority.

Groups outputs into ZIP archives of 100 MIDI files.
Velocity = Factory PROFILE_ONLY. Timing/groove/strum/fill/solo/CC11 = Gold
where evidence allows. RX/DNC and Voice stay Factory veto.
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


def _collect(source: Path, extract_dir: Path | None = None) -> list[Path]:
    if source.is_file() and source.suffix.lower() == ".zip":
        dest = extract_dir or source.with_name(source.stem + "_extracted")
        dest.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(source) as archive:
            archive.extractall(dest)
        source = dest
    if source.is_file() and source.suffix.lower() in MIDI_SUFFIXES:
        return [source]
    files = [p for p in source.rglob("*") if p.is_file() and p.suffix.lower() in MIDI_SUFFIXES]
    return sorted(files, key=lambda p: str(p).lower())


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


def write_batch_zip(path: Path, rows: list[dict]) -> dict:
    """Write one delivery ZIP with PASS MIDI only. No .tex."""
    path.parent.mkdir(parents=True, exist_ok=True)
    packed = []
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for row in rows:
            midi = Path(row.get("output") or "")
            if row.get("status") != "PASS" or not midi.is_file():
                continue
            archive.write(midi, midi.name)
            packed.append(midi.name)
        archive.writestr(
            "batch.json",
            json.dumps(
                {
                    "schema": "PA800_FACTORY_GOLD_BATCH_ZIP_V1",
                    "midi_count": len(packed),
                    "authority": {
                        "velocity": "FACTORY_PROFILE_ONLY",
                        "timing_gate_groove_strum_fill_solo_cc11": "GOLD_WHERE_EVIDENCE_ALLOWS",
                        "structure_rx_dnc_voice": "FACTORY_VETO",
                    },
                    "files": packed,
                    "rows": rows,
                },
                indent=2,
                ensure_ascii=False,
            )
            + "\n",
        )
    return {"zip": str(path), "midi_count": len(packed), "files": packed}


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

    from pa800_optimizer.optimizer import Optimizer

    optimizer = Optimizer(factory_gold_config())

    out_root = Path(args.output).expanduser().resolve()
    out_root.mkdir(parents=True, exist_ok=True)
    sources = _collect(Path(args.input).expanduser().resolve(), extract_dir=out_root / "_extracted")
    if args.limit:
        sources = sources[: args.limit]
    if not sources:
        print("Nema MIDI/KAR fajlova u:", args.input)
        return 1

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
        "zips": [],
    }

    batch_rows: list[dict] = []
    batch_index = 1
    for i, source in enumerate(sources, 1):
        folder = out_root / "work" / ("batch_%03d" % batch_index)
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
            zip_path = out_root / ("FactoryGold_MAX_batch_%03d.zip" % batch_index)
            packed = write_batch_zip(zip_path, batch_rows)
            ledger["zips"].append(
                {
                    "batch": batch_index,
                    "files": len(batch_rows),
                    "midi_in_zip": packed["midi_count"],
                    "zip": packed["zip"],
                }
            )
            print("ZIP", zip_path.name, "midi=", packed["midi_count"])
            batch_rows = []
            batch_index += 1

    (out_root / "LEDGER.json").write_text(json.dumps(ledger, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print("Gotovo. ZIP arhiva:", len(ledger["zips"]))
    print("Izlaz:", out_root)
    return 0 if ledger["source_count"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
