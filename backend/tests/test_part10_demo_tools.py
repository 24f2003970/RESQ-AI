import importlib.util
import sqlite3
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def _load_preflight():
    spec = importlib.util.spec_from_file_location("resq_demo_preflight", ROOT / "scripts" / "demo_preflight.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_preflight_sqlite_probe_does_not_create_or_write_database(tmp_path, monkeypatch):
    module = _load_preflight()
    missing = tmp_path / "not-created.sqlite3"
    monkeypatch.setattr(module, "DB_PATH", missing)
    status, detail = module.read_only_schema()
    assert status is None
    assert "initialize" in detail
    assert not missing.exists()


def test_preflight_schema_reads_existing_database_without_mutation(tmp_path, monkeypatch):
    module = _load_preflight()
    path = tmp_path / "existing.sqlite3"
    with sqlite3.connect(path) as db:
        db.executescript("CREATE TABLE scenarios(id); CREATE TABLE events(id); CREATE TABLE checkpoints(id);")
        before = db.execute("SELECT name, sql FROM sqlite_master ORDER BY name").fetchall()
    monkeypatch.setattr(module, "DB_PATH", path)
    status, detail = module.read_only_schema()
    assert status is False
    assert "agent_event_outbox" in detail and "missions" in detail
    with sqlite3.connect(path) as db:
        assert db.execute("SELECT name, sql FROM sqlite_master ORDER BY name").fetchall() == before


def test_acceptance_runner_requires_explicit_test_commander_actions(tmp_path):
    completed = subprocess.run(
        [sys.executable, str(ROOT / "backend" / "demo_acceptance_part10.py"), "--output-dir", str(tmp_path)],
        cwd=ROOT, capture_output=True, text=True, check=False,
    )
    assert completed.returncode == 2
    assert "--test-commander-actions" in completed.stderr
    assert not list(tmp_path.glob("acceptance-report.*"))
