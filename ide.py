"""OPC IDE — a small Flask-based editor for the SimplC/OPC transpiler.

Run with:  uv run python ide.py   (then open http://127.0.0.1:5000)

Workflow:
  * Open a folder (workspace) from the top menu bar.
  * Browse and edit files in that folder (sandboxed to the workspace).
  * Syntax highlighting for .opc files via a custom CodeMirror mode.
  * One-click transpile that runs transpiler.py and shows the generated C.
  * Light / dark theme.
"""

import json
import os
import shlex
import shutil
import subprocess
import sys

from flask import Flask, jsonify, request, send_from_directory

# Standard OPC project layout: sources in OPC/, generated C in C/.
SRC_DIR = "OPC"
OUT_DIR = "C"

# ── configuration ────────────────────────────────────────────────────────────
APP_DIR = os.path.dirname(os.path.abspath(__file__))
TRANSPILER = os.path.join(APP_DIR, "transpiler.py")

# Persisted IDE settings (e.g. the last opened folder) live in the user's
# config directory so they survive restarts but stay out of the repo.
CONFIG_DIR = os.path.join(
    os.environ.get("XDG_CONFIG_HOME", os.path.expanduser("~/.config")),
    "opc-ide",
)
CONFIG_FILE = os.path.join(CONFIG_DIR, "settings.json")


def load_settings() -> dict:
    """Read persisted settings, tolerating a missing or corrupt file."""
    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def save_settings(settings: dict) -> None:
    """Persist settings, silently ignoring write failures."""
    try:
        os.makedirs(CONFIG_DIR, exist_ok=True)
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(settings, f, indent=2)
    except OSError:
        pass


def remember_workspace(path: str | None) -> None:
    """Record the last opened folder so it reopens on the next launch."""
    settings = load_settings()
    settings["last_folder"] = path
    save_settings(settings)


# The currently opened workspace folder. None until the user opens one.
workspace = {"root": None}


def restore_workspace() -> None:
    """Reopen the most recently used folder, like VS Code, if it still exists."""
    last = load_settings().get("last_folder")
    if last and os.path.isdir(last):
        workspace["root"] = os.path.abspath(last)

# Directories / files we never want to show in the tree.
IGNORE = {
    ".git", ".idea", ".venv", "__pycache__", ".pytest_cache",
    "node_modules", ".mypy_cache", ".ruff_cache",
}

# Extensions we treat as editable text.
TEXT_EXTS = {
    ".opc", ".sc", ".c", ".h", ".py", ".md", ".txt", ".toml",
    ".json", ".cfg", ".ini", ".sh", ".yml", ".yaml", ".lock",
}

app = Flask(__name__, static_folder="static", static_url_path="/static")

# Reopen the last-used folder at import time so it works under any launcher
# (python ide.py, flask run, gunicorn, …), not only the __main__ path.
restore_workspace()


# ── path safety ──────────────────────────────────────────────────────────────
def safe_path(rel: str) -> str:
    """Resolve a client path relative to the workspace, refusing escapes."""
    root = workspace["root"]
    if not root:
        raise ValueError("no folder open")
    rel = (rel or "").lstrip("/\\")
    full = os.path.abspath(os.path.join(root, rel))
    if full != root and not full.startswith(root + os.sep):
        raise ValueError("path escapes workspace")
    return full


def build_tree(path: str):
    """Recursively build a sorted file tree (folders first)."""
    entries = []
    try:
        names = sorted(os.listdir(path))
    except OSError:
        return entries
    names.sort(key=lambda n: (not os.path.isdir(os.path.join(path, n)), n.lower()))
    for name in names:
        if name in IGNORE:
            continue
        full = os.path.join(path, name)
        rel = os.path.relpath(full, workspace["root"])
        if os.path.isdir(full):
            entries.append({
                "name": name, "path": rel, "type": "dir",
                "children": build_tree(full),
            })
        else:
            entries.append({
                "name": name, "path": rel, "type": "file",
                "ext": os.path.splitext(name)[1].lower(),
            })
    return entries


# ── routes ───────────────────────────────────────────────────────────────────
@app.route("/")
def index():
    return send_from_directory("static", "index.html")


@app.route("/api/state")
def api_state():
    """Whether a workspace is open and which one."""
    root = workspace["root"]
    return jsonify({
        "open": bool(root),
        "name": os.path.basename(root) if root else None,
        "path": root,
    })


@app.route("/api/listdirs")
def api_listdirs():
    """List subdirectories of a path — used by the folder picker.

    Defaults to the workspace (if open) or the user's home directory.
    """
    path = request.args.get("path", "")
    if not path:
        path = workspace["root"] or os.path.expanduser("~")
    path = os.path.abspath(path)
    if not os.path.isdir(path):
        return jsonify({"error": "not a directory"}), 400
    dirs = []
    try:
        for name in sorted(os.listdir(path), key=str.lower):
            if name.startswith(".") or name in IGNORE:
                continue
            full = os.path.join(path, name)
            if os.path.isdir(full):
                dirs.append({"name": name, "path": full})
    except OSError as e:
        return jsonify({"error": str(e)}), 500
    parent = os.path.dirname(path)
    return jsonify({
        "path": path,
        "parent": parent if parent != path else None,
        "dirs": dirs,
    })


@app.route("/api/open", methods=["POST"])
def api_open():
    """Open a folder as the active workspace.

    Every OPC project uses the layout  <root>/OPC  and  <root>/C  — these
    folders are created on open if missing so the structure is guaranteed.
    """
    data = request.get_json(silent=True) or {}
    path = os.path.abspath(data.get("path", ""))
    if not os.path.isdir(path):
        return jsonify({"error": "not a directory"}), 400
    workspace["root"] = path
    for sub in (SRC_DIR, OUT_DIR):
        try:
            os.makedirs(os.path.join(path, sub), exist_ok=True)
        except OSError:
            pass
    remember_workspace(path)
    return jsonify({"ok": True, "name": os.path.basename(path), "path": path})


def c_output_for(rel_opc: str) -> str:
    """Map an OPC source path to its generated C path under the C/ dir.

    OPC/foo.opc      -> C/foo.c
    OPC/sub/bar.opc  -> C/sub/bar.c
    foo.opc          -> C/foo.c     (loose files still land in C/)
    """
    parts = rel_opc.replace("\\", "/").split("/")
    inner = "/".join(parts[1:]) if parts and parts[0] == SRC_DIR else rel_opc
    return os.path.join(OUT_DIR, os.path.splitext(inner)[0] + ".c")


def resolve_c_rel(rel_path: str) -> str:
    """Given an .opc or .c relative path, return the relevant .c relative path."""
    ext = os.path.splitext(rel_path)[1].lower()
    if ext in (".opc", ".sc"):
        return c_output_for(rel_path)
    return rel_path


@app.route("/api/tree")
def api_tree():
    if not workspace["root"]:
        return jsonify({"open": False, "tree": []})
    return jsonify({
        "open": True,
        "root": os.path.basename(workspace["root"]),
        "path": workspace["root"],
        "tree": build_tree(workspace["root"]),
    })


@app.route("/api/file")
def api_read_file():
    try:
        full = safe_path(request.args.get("path", ""))
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    if not os.path.isfile(full):
        return jsonify({"error": "not a file"}), 404
    ext = os.path.splitext(full)[1].lower()
    if ext and ext not in TEXT_EXTS:
        return jsonify({"error": f"binary or unsupported file ({ext})"}), 415
    try:
        with open(full, "r", encoding="utf-8") as f:
            content = f.read()
    except (OSError, UnicodeDecodeError) as e:
        return jsonify({"error": str(e)}), 500
    return jsonify({
        "path": os.path.relpath(full, workspace["root"]),
        "content": content, "ext": ext,
    })


@app.route("/api/save", methods=["POST"])
def api_save_file():
    data = request.get_json(silent=True) or {}
    try:
        full = safe_path(data.get("path", ""))
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    if os.path.isdir(full):
        return jsonify({"error": "is a directory"}), 400
    try:
        os.makedirs(os.path.dirname(full), exist_ok=True)
        with open(full, "w", encoding="utf-8") as f:
            f.write(data.get("content", ""))
    except OSError as e:
        return jsonify({"error": str(e)}), 500
    return jsonify({"ok": True, "path": os.path.relpath(full, workspace["root"])})


@app.route("/api/create", methods=["POST"])
def api_create():
    data = request.get_json(silent=True) or {}
    try:
        full = safe_path(data.get("path", ""))
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    if os.path.exists(full):
        return jsonify({"error": "already exists"}), 409
    try:
        if data.get("type") == "dir":
            os.makedirs(full, exist_ok=True)
        else:
            os.makedirs(os.path.dirname(full), exist_ok=True)
            with open(full, "w", encoding="utf-8") as f:
                f.write("")
    except OSError as e:
        return jsonify({"error": str(e)}), 500
    return jsonify({"ok": True, "path": os.path.relpath(full, workspace["root"])})


@app.route("/api/delete", methods=["POST"])
def api_delete():
    data = request.get_json(silent=True) or {}
    try:
        full = safe_path(data.get("path", ""))
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    if full == workspace["root"]:
        return jsonify({"error": "cannot delete workspace root"}), 400
    try:
        if os.path.isdir(full):
            shutil.rmtree(full)
        elif os.path.exists(full):
            os.remove(full)
        else:
            return jsonify({"error": "not found"}), 404
    except OSError as e:
        return jsonify({"error": str(e)}), 500
    return jsonify({"ok": True})


# ── batch / mutation helpers (rename, move, multi-delete) ───────────────────
def _validate_basename(name: str) -> str | None:
    """Return an error message if `name` is not a safe single-segment filename."""
    if not name or not name.strip():
        return "name must not be empty"
    if name != name.strip():
        return "name must not have leading or trailing whitespace"
    if name in (".", ".."):
        return "name must not be . or .."
    if "/" in name or "\\" in name:
        return "name must not contain a path separator"
    if os.sep in name or (os.altsep and os.altsep in name):
        return "name must not contain a path separator"
    if name in IGNORE:
        return "name is reserved"
    return None


def _inside(child: str, parent: str) -> bool:
    """True if `child` is the same path as `parent` or sits inside it."""
    child = os.path.abspath(child)
    parent = os.path.abspath(parent)
    if child == parent:
        return True
    return child.startswith(parent + os.sep)


@app.route("/api/rename", methods=["POST"])
def api_rename():
    """Rename a file or folder within its current parent directory.

    Body: { "path": "OPC/foo.opc", "new_name": "bar.opc" }
    """
    data = request.get_json(silent=True) or {}
    try:
        full = safe_path(data.get("path", ""))
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    new_name = data.get("new_name", "")
    err = _validate_basename(new_name)
    if err:
        return jsonify({"error": err}), 400
    if full == workspace["root"]:
        return jsonify({"error": "cannot rename workspace root"}), 400
    parent = os.path.dirname(full)
    target = os.path.join(parent, new_name)
    if not _inside(target, workspace["root"]):
        return jsonify({"error": "rename would escape workspace"}), 400
    if os.path.exists(target):
        return jsonify({"error": f"'{new_name}' already exists"}), 409
    try:
        os.rename(full, target)
    except OSError as e:
        return jsonify({"error": str(e)}), 500
    return jsonify({
        "ok": True,
        "old_path": os.path.relpath(full, workspace["root"]),
        "new_path": os.path.relpath(target, workspace["root"]),
    })


@app.route("/api/move", methods=["POST"])
def api_move():
    """Move one or more files/folders into an existing directory.

    Body: { "sources": ["OPC/a.opc", "OPC/sub"], "dest_dir": "OPC/other" }

    Response: { "ok": bool, "moves": [{old_path, new_path}, ...], "errors": [...] }
    The ``moves`` list lets the client remap open tabs and expanded folders
    to the new locations without a second round-trip.
    """
    data = request.get_json(silent=True) or {}
    sources = data.get("sources") or []
    dest_rel = data.get("dest_dir", "")
    if not isinstance(sources, list) or not sources:
        return jsonify({"error": "sources must be a non-empty list"}), 400
    try:
        dest_full = safe_path(dest_rel)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    if not os.path.isdir(dest_full):
        return jsonify({"error": "destination is not a directory"}), 400

    moves, errors = [], []
    for src_rel in sources:
        try:
            src_full = safe_path(src_rel)
        except ValueError as e:
            errors.append({"path": src_rel, "error": str(e)})
            continue
        if src_full == workspace["root"]:
            errors.append({"path": src_rel, "error": "cannot move workspace root"})
            continue
        # Refuse moves that drop a folder into itself or one of its descendants.
        if _inside(dest_full, src_full):
            errors.append({"path": src_rel, "error": "cannot move into itself"})
            continue
        if src_full == dest_full:
            errors.append({"path": src_rel, "error": "source and destination are the same"})
            continue
        target = os.path.join(dest_full, os.path.basename(src_full))
        if not _inside(target, workspace["root"]):
            errors.append({"path": src_rel, "error": "move would escape workspace"})
            continue
        if os.path.exists(target):
            errors.append({"path": src_rel, "error": f"'{os.path.basename(target)}' already exists at destination"})
            continue
        try:
            os.rename(src_full, target)
            moves.append({
                "old_path": os.path.relpath(src_full, workspace["root"]),
                "new_path": os.path.relpath(target, workspace["root"]),
            })
        except OSError as e:
            errors.append({"path": src_rel, "error": str(e)})

    return jsonify({"ok": not errors, "moves": moves, "errors": errors})


@app.route("/api/delete_many", methods=["POST"])
def api_delete_many():
    """Delete several files/folders in one call.

    Body: { "paths": ["OPC/a.opc", "OPC/sub"] }
    Sources are sorted deepest-first so children vanish before their parents.
    """
    data = request.get_json(silent=True) or {}
    paths = data.get("paths") or []
    if not isinstance(paths, list) or not paths:
        return jsonify({"error": "paths must be a non-empty list"}), 400

    resolved = []
    errors = []
    for p in paths:
        try:
            full = safe_path(p)
        except ValueError as e:
            errors.append({"path": p, "error": str(e)})
            continue
        if full == workspace["root"]:
            errors.append({"path": p, "error": "cannot delete workspace root"})
            continue
        resolved.append(full)

    # Deepest-first: longer paths come first so children are deleted before parents.
    resolved.sort(key=lambda p: -len(p))
    deleted = []
    for full in resolved:
        if not os.path.exists(full):
            errors.append({"path": os.path.relpath(full, workspace["root"]), "error": "not found"})
            continue
        try:
            if os.path.isdir(full):
                shutil.rmtree(full)
            else:
                os.remove(full)
            deleted.append(os.path.relpath(full, workspace["root"]))
        except OSError as e:
            errors.append({"path": os.path.relpath(full, workspace["root"]), "error": str(e)})
    return jsonify({"ok": not errors, "deleted": deleted, "errors": errors})


@app.route("/api/transpile", methods=["POST"])
def api_transpile():
    """Run the transpiler on a saved .opc file; output lands in the C/ dir."""
    data = request.get_json(silent=True) or {}
    rel = data.get("path", "")
    try:
        full = safe_path(rel)
        out_rel = c_output_for(rel)
        out_path = safe_path(out_rel)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    if not os.path.isfile(full):
        return jsonify({"error": "file not found — save it first"}), 404

    try:
        os.makedirs(os.path.dirname(out_path), exist_ok=True)
    except OSError as e:
        return jsonify({"error": str(e)}), 500

    try:
        proc = subprocess.run(
            [sys.executable, TRANSPILER, full, out_path],
            capture_output=True, text=True, cwd=workspace["root"], timeout=30,
        )
    except subprocess.TimeoutExpired:
        return jsonify({"error": "transpiler timed out"}), 500

    if proc.returncode != 0:
        return jsonify({
            "ok": False, "stdout": proc.stdout,
            "stderr": proc.stderr or "transpiler failed",
        })

    c_code = ""
    if os.path.isfile(out_path):
        with open(out_path, "r", encoding="utf-8") as f:
            c_code = f.read()
    return jsonify({
        "ok": True, "c": c_code,
        "output_path": os.path.relpath(out_path, workspace["root"]),
        "stdout": proc.stdout, "stderr": proc.stderr,
    })


@app.route("/api/compile", methods=["POST"])
def api_compile():
    """Compile a C file (from an .opc or .c path) with user-supplied flags."""
    data = request.get_json(silent=True) or {}
    compiler = (data.get("compiler") or "gcc").strip()
    flags = data.get("flags", "-Wall -Wextra -lm")
    try:
        c_rel = resolve_c_rel(data.get("path", ""))
        c_full = safe_path(c_rel)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    if not os.path.isfile(c_full):
        return jsonify({"error": f"{c_rel} not found — transpile first"}), 404

    binary = os.path.splitext(c_full)[0]
    try:
        flag_list = shlex.split(flags)
    except ValueError as e:
        return jsonify({"error": f"bad flags: {e}"}), 400

    cmd = [compiler, os.path.basename(c_full)] + flag_list + ["-o", os.path.basename(binary)]
    try:
        proc = subprocess.run(
            cmd, capture_output=True, text=True,
            cwd=os.path.dirname(c_full), timeout=60,
        )
    except FileNotFoundError:
        return jsonify({"error": f"compiler '{compiler}' not found"}), 400
    except subprocess.TimeoutExpired:
        return jsonify({"error": "compilation timed out"}), 500

    return jsonify({
        "ok": proc.returncode == 0,
        "command": " ".join(cmd),
        "returncode": proc.returncode,
        "stdout": proc.stdout,
        "stderr": proc.stderr,
        "binary": os.path.relpath(binary, workspace["root"]) if proc.returncode == 0 else None,
    })


@app.route("/api/run", methods=["POST"])
def api_run():
    """Execute a compiled binary (derived from an .opc/.c path) and capture output."""
    data = request.get_json(silent=True) or {}
    try:
        c_rel = resolve_c_rel(data.get("path", ""))
        binary = safe_path(os.path.splitext(c_rel)[0])
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    if not os.path.isfile(binary):
        return jsonify({"error": "no binary — compile first"}), 404

    stdin_data = data.get("stdin", "")
    try:
        proc = subprocess.run(
            [binary], capture_output=True, text=True,
            cwd=os.path.dirname(binary), timeout=30,
            input=stdin_data if stdin_data else None,
        )
    except subprocess.TimeoutExpired:
        return jsonify({"error": "program timed out (30s)"}), 500
    except OSError as e:
        return jsonify({"error": str(e)}), 500

    return jsonify({
        "ok": proc.returncode == 0,
        "returncode": proc.returncode,
        "stdout": proc.stdout,
        "stderr": proc.stderr,
    })


if __name__ == "__main__":
    if workspace["root"]:
        print(f"OPC IDE — reopened last folder: {workspace['root']}")
    print("OPC IDE — open http://127.0.0.1:5000")
    app.run(debug=True, port=5000)
