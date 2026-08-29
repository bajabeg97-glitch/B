import importlib.util
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "batch_factory_gold", ROOT / "tools" / "batch_factory_gold.py"
)
batch = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(batch)


def test_factory_gold_config_keeps_factory_velocity_and_gold_max_without_autopilot():
    cfg = batch.factory_gold_config()
    assert cfg.velocity_factory_data_only is True
    assert cfg.factory_gold_max is True
    assert cfg.mode == "max"
    assert cfg.export_preset == "auto"
    assert cfg.autopilot is False
    assert cfg.enable_timing and cfg.enable_gate
    assert cfg.trained_rhythm_only is False


def test_collect_reads_midi_and_zip(tmp_path):
    folder = tmp_path / "pack"
    folder.mkdir()
    (folder / "a.mid").write_bytes(b"MThd")
    (folder / "b.KAR").write_bytes(b"MThd")
    (folder / "skip.txt").write_text("no")
    found = batch._collect(folder)
    assert [p.name for p in found] == ["a.mid", "b.KAR"]
    zpath = tmp_path / "pack.zip"
    with zipfile.ZipFile(zpath, "w") as archive:
        archive.writestr("nested/c.midi", b"MThd")
    zipped = batch._collect(zpath)
    assert len(zipped) == 1 and zipped[0].name == "c.midi"


def test_write_batch_tex_contains_description_template(tmp_path):
    path = tmp_path / "batch_001.tex"
    batch.write_batch_tex(
        path,
        1,
        [
            {
                "index": 1,
                "source_name": "rumba_noci.mid",
                "output": "001_rumba_noci_FG.mid",
                "changes": 12,
                "status": "PASS",
            }
        ],
        "2026-08-30 00:00 UTC",
        batch_size=100,
    )
    text = path.read_text(encoding="utf-8")
    assert "Velocity = Factory profil" in text
    assert "CC11 = Gold" in text
    assert "rumba\\_noci.mid" in text
    assert "batch 001" in text
    assert "Veličina grupe: 100" in text
