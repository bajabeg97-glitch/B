import importlib.util
import json
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
    zipped = batch._collect(zpath, extract_dir=tmp_path / "extracted")
    assert len(zipped) == 1 and zipped[0].name == "c.midi"


def test_write_batch_zip_packs_pass_midi_only(tmp_path):
    work = tmp_path / "work"
    work.mkdir()
    good = work / "001_rumba_noci_FG.mid"
    good.write_bytes(b"MThd\x00\x00\x00\x06\x00\x01\x00\x01\x00\x60")
    missing = work / "002_missing_FG.mid"
    zip_path = tmp_path / "FactoryGold_MAX_batch_001.zip"
    packed = batch.write_batch_zip(
        zip_path,
        [
            {
                "index": 1,
                "source_name": "rumba_noci.mid",
                "output": str(good),
                "changes": 12,
                "status": "PASS",
            },
            {
                "index": 2,
                "source_name": "broken.mid",
                "output": str(missing),
                "changes": 0,
                "status": "FAIL",
            },
        ],
    )
    assert packed["midi_count"] == 1
    assert zip_path.is_file()
    with zipfile.ZipFile(zip_path) as archive:
        names = archive.namelist()
        assert "001_rumba_noci_FG.mid" in names
        assert "002_missing_FG.mid" not in names
        assert not any(name.endswith(".tex") for name in names)
        manifest = json.loads(archive.read("batch.json"))
    assert manifest["midi_count"] == 1
    assert manifest["authority"]["velocity"] == "FACTORY_PROFILE_ONLY"
