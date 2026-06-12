"""Backend tests for the IDE's new file-management endpoints.

Covers the three additions to ``ide.py`` that power the upgraded file browser:
``/api/rename``, ``/api/move``, ``/api/delete_many`` — plus their rejection
of unsafe paths and the workspace root.
"""
from __future__ import annotations

import importlib
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


@dataclass
class IdeHandle:
    ide: object
    root: Path
    client: object


@pytest.fixture
def ide_app(tmp_path, monkeypatch):
    """Import ``ide`` with a clean per-test workspace as the current folder.

    The module keeps a module-level ``workspace`` dict; we point it at a fresh
    temp directory so tests are isolated from any real folder on disk.
    """
    monkeypatch.chdir(tmp_path)
    if "ide" in sys.modules:
        del sys.modules["ide"]
    ide = importlib.import_module("ide")
    ide.workspace["root"] = str(tmp_path)
    (tmp_path / "OPC").mkdir()
    (tmp_path / "C").mkdir()
    handle = IdeHandle(ide=ide, root=tmp_path, client=ide.app.test_client())
    yield handle
    ide.workspace["root"] = None


def _post(handle, url, body):
    return handle.client.post(url, data=json.dumps(body), content_type="application/json")


# ── /api/rename ──────────────────────────────────────────────────────────────
class TestRename:
    def test_rename_file(self, ide_app):
        (ide_app.root / "OPC" / "foo.opc").write_text("x")
        r = _post(ide_app, "/api/rename", {"path": "OPC/foo.opc", "new_name": "bar.opc"})
        assert r.status_code == 200
        assert r.get_json() == {
            "ok": True,
            "old_path": "OPC/foo.opc",
            "new_path": "OPC/bar.opc",
        }
        assert not (ide_app.root / "OPC" / "foo.opc").exists()
        assert (ide_app.root / "OPC" / "bar.opc").read_text() == "x"

    def test_rename_rejects_path_separator(self, ide_app):
        (ide_app.root / "OPC" / "foo.opc").write_text("x")
        r = _post(ide_app, "/api/rename", {"path": "OPC/foo.opc", "new_name": "../escape"})
        assert r.status_code == 400
        assert "separator" in r.get_json()["error"]
        assert (ide_app.root / "OPC" / "foo.opc").exists()

    def test_rename_rejects_empty(self, ide_app):
        (ide_app.root / "OPC" / "foo.opc").write_text("x")
        r = _post(ide_app, "/api/rename", {"path": "OPC/foo.opc", "new_name": "   "})
        assert r.status_code == 400

    def test_rename_rejects_overwrite(self, ide_app):
        (ide_app.root / "OPC" / "foo.opc").write_text("a")
        (ide_app.root / "OPC" / "bar.opc").write_text("b")
        r = _post(ide_app, "/api/rename", {"path": "OPC/foo.opc", "new_name": "bar.opc"})
        assert r.status_code == 409

    def test_rename_rejects_workspace_root(self, ide_app):
        r = _post(ide_app, "/api/rename", {"path": ".", "new_name": "X"})
        assert r.status_code == 400

    def test_rename_rejects_escape(self, ide_app):
        r = _post(ide_app, "/api/rename", {"path": "../etc/passwd", "new_name": "x"})
        assert r.status_code == 400


# ── /api/move ────────────────────────────────────────────────────────────────
class TestMove:
    def test_move_file_into_directory(self, ide_app):
        (ide_app.root / "OPC" / "sub").mkdir()
        (ide_app.root / "OPC" / "foo.opc").write_text("x")
        r = _post(ide_app, "/api/move", {"sources": ["OPC/foo.opc"], "dest_dir": "OPC/sub"})
        assert r.status_code == 200
        body = r.get_json()
        assert body["ok"] is True
        assert body["moves"] == [{"old_path": "OPC/foo.opc", "new_path": "OPC/sub/foo.opc"}]
        assert not (ide_app.root / "OPC" / "foo.opc").exists()
        assert (ide_app.root / "OPC" / "sub" / "foo.opc").exists()

    def test_move_folder_into_descendant_rejected(self, ide_app):
        (ide_app.root / "OPC" / "a" / "b").mkdir(parents=True)
        r = _post(ide_app, "/api/move", {"sources": ["OPC/a"], "dest_dir": "OPC/a/b"})
        body = r.get_json()
        assert body["ok"] is False
        assert "itself" in body["errors"][0]["error"]
        assert (ide_app.root / "OPC" / "a").exists()

    def test_move_into_workspace_root_is_allowed(self, ide_app):
        """Dragging a file out of a subfolder into the root is a normal move."""
        (ide_app.root / "OPC" / "sub").mkdir()
        (ide_app.root / "OPC" / "sub" / "foo.opc").write_text("x")
        r = _post(ide_app, "/api/move", {"sources": ["OPC/sub/foo.opc"], "dest_dir": "."})
        body = r.get_json()
        assert body["ok"] is True
        assert body["moves"] == [{"old_path": "OPC/sub/foo.opc", "new_path": "foo.opc"}]
        assert (ide_app.root / "foo.opc").exists()

    def test_move_overwrite_rejected(self, ide_app):
        (ide_app.root / "OPC" / "sub").mkdir()
        (ide_app.root / "OPC" / "sub" / "x.opc").write_text("dest")
        (ide_app.root / "OPC" / "x.opc").write_text("src")
        r = _post(ide_app, "/api/move", {"sources": ["OPC/x.opc"], "dest_dir": "OPC/sub"})
        body = r.get_json()
        assert body["ok"] is False
        assert "already exists" in body["errors"][0]["error"]
        # both copies still exist
        assert (ide_app.root / "OPC" / "x.opc").exists()
        assert (ide_app.root / "OPC" / "sub" / "x.opc").read_text() == "dest"

    def test_move_workspace_root_rejected(self, ide_app):
        r = _post(ide_app, "/api/move", {"sources": ["."], "dest_dir": "OPC"})
        body = r.get_json()
        assert body["ok"] is False
        assert "workspace root" in body["errors"][0]["error"]


# ── /api/delete_many ─────────────────────────────────────────────────────────
class TestDeleteMany:
    def test_delete_files_and_folders(self, ide_app):
        (ide_app.root / "OPC" / "sub").mkdir()
        (ide_app.root / "OPC" / "sub" / "deep.opc").write_text("d")
        (ide_app.root / "OPC" / "a.opc").write_text("a")
        (ide_app.root / "OPC" / "b.opc").write_text("b")
        r = _post(ide_app, "/api/delete_many",
                  {"paths": ["OPC/a.opc", "OPC/b.opc", "OPC/sub"]})
        body = r.get_json()
        assert body["ok"] is True
        assert sorted(body["deleted"]) == ["OPC/a.opc", "OPC/b.opc", "OPC/sub"]
        assert not (ide_app.root / "OPC" / "a.opc").exists()
        assert not (ide_app.root / "OPC" / "sub").exists()

    def test_delete_rejects_workspace_root(self, ide_app):
        r = _post(ide_app, "/api/delete_many", {"paths": ["."]})
        body = r.get_json()
        assert body["ok"] is False
        assert "workspace root" in body["errors"][0]["error"]

    def test_delete_rejects_path_escape(self, ide_app):
        r = _post(ide_app, "/api/delete_many", {"paths": ["../something"]})
        body = r.get_json()
        assert body["ok"] is False
        assert body["errors"]

    def test_delete_empty_list(self, ide_app):
        r = _post(ide_app, "/api/delete_many", {"paths": []})
        assert r.status_code == 400

    def test_delete_reports_partial_failure(self, ide_app):
        (ide_app.root / "OPC" / "real.opc").write_text("x")
        r = _post(ide_app, "/api/delete_many",
                  {"paths": ["OPC/real.opc", "OPC/missing.opc"]})
        body = r.get_json()
        assert body["ok"] is False
        assert "OPC/real.opc" in body["deleted"]
        assert any("not found" in e["error"] for e in body["errors"])
