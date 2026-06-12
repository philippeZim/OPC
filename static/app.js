// ── OPC IDE frontend ────────────────────────────────────────────────────────
const $ = (sel) => document.querySelector(sel);

const state = {
  openFiles: new Map(), // path -> { content, ext, dirty }
  active: null,
  expanded: new Set(),
  workspace: null, // absolute path of open folder, or null
  treeSelection: new Set(), // paths currently highlighted in the explorer
  treeAnchor: null,         // last single/ctrl-clicked path (anchor for shift-range)
};

let suppressChange = false;

// ── CodeMirror setup ─────────────────────────────────────────────────────────
function modeForExt(ext) {
  switch (ext) {
    case ".opc":
    case ".sc": return "opc";
    case ".c":
    case ".h": return "text/x-csrc";
    case ".py": return "python";
    case ".md": return "markdown";
    default: return "text/plain";
  }
}

const editor = CodeMirror.fromTextArea($("#editor"), {
  lineNumbers: true, mode: "opc", theme: "monokai", indentUnit: 4, tabSize: 4,
  indentWithTabs: false, autoCloseBrackets: true, styleActiveLine: true,
  matchBrackets: true, lineWrapping: false,
  extraKeys: { "Ctrl-Space": triggerHint },
});
editor.setSize("100%", "100%");

// ── autocomplete (PyCharm-style) ─────────────────────────────────────────────
// Only the SimplC/OPC files get the language-aware completer.
function triggerHint(cm) {
  if (!cm._isOpc || !CodeMirror.hint || !CodeMirror.hint.opc) return;
  cm.showHint({
    hint: CodeMirror.hint.opc,
    completeSingle: false,
    closeOnUnfocus: true,
  });
}

// Pop the menu up automatically as you type identifiers, `.` or `:`.
editor.on("inputRead", (cm, change) => {
  if (!cm._isOpc || change.origin !== "+input") return;
  if (cm.state.completionActive) return;
  const typed = change.text[change.text.length - 1] || "";
  const ch = typed.slice(-1);
  if (!/[A-Za-z_.:]/.test(ch)) return;
  const tok = cm.getTokenAt(cm.getCursor());
  if (tok.type === "string" || tok.type === "string-2" || tok.type === "comment") return;
  triggerHint(cm);
});

const output = CodeMirror.fromTextArea($("#output"), {
  lineNumbers: true, mode: "text/x-csrc", theme: "monokai",
  readOnly: true, styleActiveLine: false,
});
output.setSize("100%", "100%");

editor.on("change", () => {
  if (!state.active || suppressChange) return;
  const f = state.openFiles.get(state.active);
  if (f && !f.dirty) {
    f.dirty = true;
    renderTabs();
    updateDirty();
  }
});

// ── toast ────────────────────────────────────────────────────────────────────
let toastTimer;
function toast(msg, isError = false) {
  const t = $("#toast");
  t.textContent = msg;
  t.classList.toggle("error", isError);
  t.hidden = false;
  requestAnimationFrame(() => t.classList.add("show"));
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => {
    t.classList.remove("show");
    setTimeout(() => (t.hidden = true), 200);
  }, 2600);
}

// ── API helper ───────────────────────────────────────────────────────────────
async function api(url, opts) {
  const res = await fetch(url, opts);
  let data;
  try { data = await res.json(); } catch { data = {}; }
  if (!res.ok) throw new Error(data.error || res.statusText);
  return data;
}

function jsonPost(url, body) {
  return api(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
}

// ── workspace state ──────────────────────────────────────────────────────────
function setWorkspaceUI(open) {
  $("#btn-side-new").disabled = !open;
  $("#btn-side-new-folder").disabled = !open;
  $("#btn-refresh").disabled = !open;
  $("#no-workspace").hidden = open;
  $("#tree").style.display = open ? "block" : "none";
  $("#empty-msg").textContent = open
    ? "Open a file from the explorer to start editing."
    : "Open a folder to get started.";
  // the empty-state CTA only makes sense before a folder is open
  $("#btn-open-folder-3").style.display = open ? "none" : "";
  if (!open) {
    state.treeSelection.clear();
    updateSidebarHeader();
  }
}

async function refreshState() {
  const s = await api("/api/state");
  state.workspace = s.open ? s.path : null;
  setWorkspaceUI(s.open);
  if (s.open) await loadTree();
}

// ── file tree ────────────────────────────────────────────────────────────────
async function loadTree() {
  const data = await api("/api/tree");
  $("#root-name").textContent = data.open ? data.root : "explorer";
  const tree = $("#tree");
  tree.innerHTML = "";
  (data.tree || []).forEach((node) => tree.appendChild(renderNode(node, 0)));
  // drop selection entries that no longer exist on disk
  const present = new Set(visibleTreeRows().map((r) => r.dataset.path));
  let changed = false;
  for (const p of state.treeSelection) {
    if (!present.has(p)) { state.treeSelection.delete(p); changed = true; }
  }
  if (changed) updateSidebarHeader();
  applySelectionToDom();
}

function extClass(ext) { return "ext-" + (ext || "").replace(".", ""); }
function fileIcon(ext) {
  if (ext === ".opc" || ext === ".sc") return "◇";
  if (ext === ".c" || ext === ".h") return "©";
  if (ext === ".py") return "py";
  if (ext === ".md") return "▤";
  return "•";
}

function renderNode(node, depth) {
  if (node.type === "dir") {
    const wrap = document.createElement("div");
    const row = document.createElement("div");
    row.className = "node-row dir-row";
    row.dataset.path = node.path;
    row.dataset.type = "dir";
    const isOpen = state.expanded.has(node.path);
    row.innerHTML = `
      <span class="node-caret ${isOpen ? "open" : ""}">▶</span>
      <span class="node-icon">${isOpen ? "📂" : "📁"}</span>
      <span class="node-label">${node.name}</span>`;
    const children = document.createElement("div");
    children.className = "node-children";
    children.hidden = !isOpen;
    node.children.forEach((c) => children.appendChild(renderNode(c, depth + 1)));

    wireRow(row, {
      onPrimaryClick: () => {
        const nowOpen = children.hidden;
        children.hidden = !nowOpen;
        row.querySelector(".node-caret").classList.toggle("open", nowOpen);
        row.querySelector(".node-icon").textContent = nowOpen ? "📂" : "📁";
        if (nowOpen) state.expanded.add(node.path);
        else state.expanded.delete(node.path);
      },
    });
    wrap.appendChild(row);
    wrap.appendChild(children);
    return wrap;
  }

  const row = document.createElement("div");
  row.className = "node-row file-node";
  row.dataset.path = node.path;
  row.dataset.type = "file";
  row.innerHTML = `
    <span class="node-caret"></span>
    <span class="node-icon ${extClass(node.ext)}">${fileIcon(node.ext)}</span>
    <span class="node-label">${node.name}</span>`;
  wireRow(row, { onPrimaryClick: () => openFile(node.path) });
  return row;
}

// Wire click / shift / ctrl-click / contextmenu / drag&drop for a tree row.
function wireRow(row, { onPrimaryClick }) {
  row.addEventListener("click", (e) => {
    if (e.target.closest(".node-rename")) return; // don't change selection while renaming
    const path = row.dataset.path;
    if (e.shiftKey && state.treeAnchor) {
      selectRange(state.treeAnchor, path);
    } else if (e.ctrlKey || e.metaKey) {
      toggleSelection(path);
      state.treeAnchor = path;
    } else {
      setSelection([path]);
      state.treeAnchor = path;
      onPrimaryClick();
    }
  });

  row.addEventListener("dblclick", () => {
    if (row.dataset.type !== "file") return;
    startRename(row.dataset.path);
  });

  row.addEventListener("contextmenu", (e) => {
    e.preventDefault();
    const path = row.dataset.path;
    if (!state.treeSelection.has(path)) {
      setSelection([path]);
      state.treeAnchor = path;
    }
    openContextMenu(e.clientX, e.clientY, { type: row.dataset.type, path });
  });

  // Drag source — drag a single row, or the whole selection if this row is in it.
  row.draggable = true;
  row.addEventListener("dragstart", (e) => {
    const path = row.dataset.path;
    if (!state.treeSelection.has(path)) {
      setSelection([path]);
    }
    const sources = [...state.treeSelection];
    e.dataTransfer.effectAllowed = "move";
    e.dataTransfer.setData("application/x-opc-paths", JSON.stringify(sources));
    e.dataTransfer.setData("text/plain", sources.join("\n"));
    row.classList.add("drag-source");
  });
  row.addEventListener("dragend", () => {
    row.classList.remove("drag-source");
    document.querySelectorAll(".drop-target").forEach((el) => el.classList.remove("drop-target"));
  });

  if (row.dataset.type === "dir") {
    row.addEventListener("dragover", (e) => {
      if (!hasInternalPaths(e.dataTransfer)) return;
      e.preventDefault();
      e.dataTransfer.dropEffect = "move";
      row.classList.add("drop-target");
    });
    row.addEventListener("dragleave", (e) => {
      // ignore dragleave on children bubbling up
      if (e.target === row) row.classList.remove("drop-target");
    });
    row.addEventListener("drop", async (e) => {
      e.preventDefault();
      row.classList.remove("drop-target");
      const raw = e.dataTransfer.getData("application/x-opc-paths");
      if (!raw) return;
      let sources;
      try { sources = JSON.parse(raw); } catch { return; }
      await moveInto(sources, row.dataset.path);
    });
  }
}

function hasInternalPaths(dt) {
  if (!dt) return false;
  return [...dt.types].includes("application/x-opc-paths");
}

// ── selection model ──────────────────────────────────────────────────────────
function setSelection(paths) {
  state.treeSelection = new Set(paths);
  applySelectionToDom();
  updateSidebarHeader();
}

function toggleSelection(path) {
  if (state.treeSelection.has(path)) state.treeSelection.delete(path);
  else state.treeSelection.add(path);
  applySelectionToDom();
  updateSidebarHeader();
}

// Add every visible row between `from` and `to` (inclusive), preserving current
// selection — VSCode-style shift-click.
function selectRange(from, to) {
  const rows = visibleTreeRows();
  const a = rows.findIndex((r) => r.dataset.path === from);
  const b = rows.findIndex((r) => r.dataset.path === to);
  if (a === -1 || b === -1) {
    setSelection([to]);
    return;
  }
  const [lo, hi] = a < b ? [a, b] : [b, a];
  const next = new Set(state.treeSelection);
  for (let i = lo; i <= hi; i++) next.add(rows[i].dataset.path);
  state.treeSelection = next;
  applySelectionToDom();
  updateSidebarHeader();
}

function visibleTreeRows() {
  return [...document.querySelectorAll(".node-row")].filter((r) => r.offsetParent !== null);
}

function applySelectionToDom() {
  document.querySelectorAll(".node-row").forEach((el) => {
    el.classList.toggle("selected", state.treeSelection.has(el.dataset.path));
  });
}

function clearSelection() {
  setSelection([]);
}

function selectedPaths() {
  return [...state.treeSelection];
}

// ── sidebar header (root label <-> "N selected" action bar) ────────────────
function updateSidebarHeader() {
  const n = state.treeSelection.size;
  const def = $("#sidebar-header-default");
  const sel = $("#sidebar-header-selection");
  if (n === 0) {
    def.hidden = false;
    sel.hidden = true;
  } else {
    def.hidden = true;
    sel.hidden = false;
    $("#sel-count").textContent = String(n);
  }
}

function highlightActiveInTree() {
  document.querySelectorAll(".file-node").forEach((el) => {
    el.classList.toggle("active", el.dataset.path === state.active);
  });
  applySelectionToDom();
}

// ── open / switch / close files ──────────────────────────────────────────────
async function openFile(path) {
  if (state.openFiles.has(path)) { activate(path); return; }
  try {
    const data = await api("/api/file?path=" + encodeURIComponent(path));
    state.openFiles.set(path, { content: data.content, ext: data.ext, dirty: false });
    activate(path);
  } catch (e) {
    toast(e.message, true);
  }
}

function activate(path) {
  if (state.active && state.openFiles.has(state.active)) {
    state.openFiles.get(state.active).content = editor.getValue();
  }
  state.active = path;
  const f = state.openFiles.get(path);
  $("#empty-state").style.display = "none";

  const isOpc = f.ext === ".opc" || f.ext === ".sc";

  suppressChange = true;
  editor.swapDoc(CodeMirror.Doc(f.content, modeForExt(f.ext)));
  editor._isOpc = isOpc;
  suppressChange = false;

  $("#active-path").textContent = path;
  $("#btn-save").disabled = false;
  $("#btn-transpile").disabled = !isOpc;
  $("#btn-buildrun").disabled = !(isOpc || f.ext === ".c");

  renderTabs();
  highlightActiveInTree();
  updateDirty();
  editor.focus();
}

function showEmptyEditor() {
  state.active = null;
  editor.setValue("");
  $("#empty-state").style.display = "flex";
  $("#active-path").textContent = "No file open";
  $("#btn-save").disabled = true;
  $("#btn-transpile").disabled = true;
  $("#btn-buildrun").disabled = true;
  renderTabs();
  updateDirty();
}

async function closeFile(path) {
  const f = state.openFiles.get(path);
  if (f && f.dirty) {
    const discard = await showConfirm({
      title: "Discard changes",
      message: `Discard unsaved changes to ${path}?`,
      okLabel: "Discard",
    });
    if (!discard) return;
  }
  state.openFiles.delete(path);
  if (state.active === path) {
    state.active = null;
    const next = [...state.openFiles.keys()].pop();
    if (next) activate(next);
    else showEmptyEditor();
  } else {
    renderTabs();
  }
}

function renderTabs() {
  const bar = $("#tabbar");
  bar.innerHTML = "";
  for (const [path, f] of state.openFiles) {
    const tab = document.createElement("div");
    tab.className = "tab" + (path === state.active ? " active" : "");
    const name = path.split("/").pop();
    tab.innerHTML = `
      ${f.dirty ? '<span class="tab-dot"></span>' : ""}
      <span class="tab-label">${name}</span>
      <span class="tab-close">✕</span>`;
    tab.addEventListener("click", (e) => {
      if (e.target.classList.contains("tab-close")) {
        e.stopPropagation();
        closeFile(path);
      } else {
        activate(path);
      }
    });
    bar.appendChild(tab);
  }
}

function updateDirty() {
  const f = state.active && state.openFiles.get(state.active);
  $("#dirty-dot").hidden = !(f && f.dirty);
}

// ── save ─────────────────────────────────────────────────────────────────────
async function saveActive() {
  if (!state.active) return;
  const f = state.openFiles.get(state.active);
  const content = editor.getValue();
  try {
    await jsonPost("/api/save", { path: state.active, content });
    f.content = content;
    f.dirty = false;
    renderTabs();
    updateDirty();
    toast("Saved " + state.active.split("/").pop());
  } catch (e) {
    toast(e.message, true);
  }
}

// ── transpile ────────────────────────────────────────────────────────────────
async function transpileActive() {
  if (!state.active) return false;
  const f = state.openFiles.get(state.active);
  if (f.ext !== ".opc" && f.ext !== ".sc") return true; // .c file: nothing to transpile
  if (f.dirty) await saveActive();
  const btn = $("#btn-transpile");
  btn.disabled = true;
  btn.textContent = "…";
  let ok = false;
  try {
    const data = await jsonPost("/api/transpile", { path: state.active });
    openOutput();
    const log = $("#output-log");
    if (data.ok) {
      output.setValue(data.c || "");
      const msg = (data.stdout || "").trim();
      log.hidden = !msg;
      log.classList.toggle("ok", true);
      log.textContent = msg;
      toast("Transpiled → " + data.output_path);
      await loadTree(); // new .c/.h files may have appeared
      ok = true;
    } else {
      output.setValue("");
      log.hidden = false;
      log.classList.remove("ok");
      log.textContent = (data.stderr || "Transpilation failed.").trim();
      toast("Transpile failed", true);
    }
  } catch (e) {
    toast(e.message, true);
  } finally {
    btn.disabled = false;
    btn.textContent = "▸ Transpile";
  }
  return ok;
}

function openOutput() {
  $("#output-pane").classList.add("open");
  document.body.classList.add("output-open");
  setTimeout(() => output.refresh(), 0);
}
function closeOutput() {
  $("#output-pane").classList.remove("open");
  document.body.classList.remove("output-open");
}

// ── name modal (create file / folder) ────────────────────────────────────────
function showModal({ title, placeholder, okLabel, prefix, defaultValue, onOk }) {
  const overlay = $("#modal-overlay");
  $("#modal-title").textContent = title;
  $("#modal-message").textContent = "";
  const input = $("#modal-input");
  input.value = defaultValue || "";
  input.placeholder = placeholder || "";
  $("#modal-ok").textContent = okLabel;
  const prefixEl = $("#modal-prefix");
  if (prefix) {
    prefixEl.textContent = prefix;
    prefixEl.hidden = false;
  } else {
    prefixEl.textContent = "";
    prefixEl.hidden = true;
  }
  overlay.hidden = false;
  setTimeout(() => { input.focus(); input.select(); }, 0);

  const ok = $("#modal-ok");
  const cancel = $("#modal-cancel");
  const close = () => {
    overlay.hidden = true;
    ok.onclick = cancel.onclick = input.onkeydown = null;
  };
  ok.onclick = async () => {
    const val = input.value.trim();
    if (!val) return;
    try {
      await onOk(val);
      close();
    } catch (e) {
      $("#modal-message").textContent = e.message;
    }
  };
  cancel.onclick = close;
  input.onkeydown = (e) => {
    if (e.key === "Enter") { e.preventDefault(); ok.onclick(); }
    if (e.key === "Escape") close();
  };
}

// ── confirm modal (delete / discard) ─────────────────────────────────────────
// A promise-based replacement for the native window.confirm() popup.
function showConfirm({ title, message, okLabel = "Delete", danger = true }) {
  return new Promise((resolve) => {
    const overlay = $("#confirm-overlay");
    $("#confirm-title").textContent = title;
    $("#confirm-message").textContent = message;
    const ok = $("#confirm-ok");
    const cancel = $("#confirm-cancel");
    ok.textContent = okLabel;
    ok.className = "btn " + (danger ? "btn-danger" : "btn-primary");
    overlay.hidden = false;
    setTimeout(() => ok.focus(), 0);

    const close = (result) => {
      overlay.hidden = true;
      ok.onclick = cancel.onclick = overlay.onclick = null;
      document.removeEventListener("keydown", onKey, true);
      resolve(result);
    };
    const onKey = (e) => {
      if (e.key === "Escape") { e.preventDefault(); close(false); }
      else if (e.key === "Enter") { e.preventDefault(); close(true); }
    };
    ok.onclick = () => close(true);
    cancel.onclick = () => close(false);
    overlay.onclick = (e) => { if (e.target === overlay) close(false); };
    document.addEventListener("keydown", onKey, true);
  });
}

// Pick a directory to land a new file/folder in, in this priority:
//   1. explicit `targetDir` (from context menu / sidebar header)
//   2. first selected directory (if any selected paths are dirs)
//   3. parent of the first selected file
//   4. workspace root
function resolveCreateDir(targetDir) {
  if (targetDir) return targetDir;
  for (const p of state.treeSelection) {
    const row = document.querySelector(`.node-row[data-path="${cssEscape(p)}"]`);
    if (row && row.dataset.type === "dir") return p;
  }
  const first = state.treeSelection.values().next().value;
  if (first) {
    const i = first.lastIndexOf("/");
    return i === -1 ? "." : first.slice(0, i);
  }
  return ".";
}

function cssEscape(s) {
  return (window.CSS && CSS.escape) ? CSS.escape(s) : s.replace(/"/g, '\\"');
}

function newFile(targetDir) {
  const dir = resolveCreateDir(targetDir);
  const prefix = dir === "." ? "in /" : `in ${dir}/`;
  showModal({
    title: "New file",
    placeholder: "filename.opc",
    okLabel: "Create",
    prefix,
    onOk: async (name) => {
      const fullPath = dir === "." ? name : `${dir}/${name}`;
      await jsonPost("/api/create", { path: fullPath, type: "file" });
      await loadTree();
      openFile(fullPath);
      toast("Created " + name);
    },
  });
}

function newFolder(targetDir) {
  const dir = resolveCreateDir(targetDir);
  const prefix = dir === "." ? "in /" : `in ${dir}/`;
  showModal({
    title: "New folder",
    placeholder: "folder-name",
    okLabel: "Create",
    prefix,
    onOk: async (name) => {
      const fullPath = dir === "." ? name : `${dir}/${name}`;
      await jsonPost("/api/create", { path: fullPath, type: "dir" });
      await loadTree();
      state.expanded.add(fullPath);
      await loadTree();
      toast("Created " + name);
    },
  });
}

// Remove open tabs whose path is in `paths`, then ask the backend to delete.
async function deleteMany(paths) {
  if (!paths.length) return;
  const message = paths.length === 1
    ? `Delete "${paths[0].split("/").pop()}"? This cannot be undone.`
    : `Delete ${paths.length} items? This cannot be undone.`;
  const confirmed = await showConfirm({
    title: paths.length === 1 ? "Delete" : `Delete ${paths.length} items`,
    message,
    okLabel: paths.length === 1 ? "Delete" : "Delete all",
  });
  if (!confirmed) return;
  try {
    const data = await jsonPost("/api/delete_many", { paths });
    for (const p of paths) {
      if (state.openFiles.has(p)) {
        state.openFiles.delete(p);
        if (state.active === p) {
          state.active = null;
          const next = [...state.openFiles.keys()].pop();
          if (next) activate(next);
          else showEmptyEditor();
        }
      }
    }
    state.treeSelection.clear();
    applySelectionToDom();
    updateSidebarHeader();
    await loadTree();
    if (data.errors && data.errors.length) {
      const n = data.errors.length;
      toast(`${data.deleted.length} deleted, ${n} failed`, true);
    } else {
      toast(`Deleted ${data.deleted.length} item${data.deleted.length === 1 ? "" : "s"}`);
    }
  } catch (e) {
    toast(e.message, true);
  }
}

async function deleteSelected() {
  await deleteMany(selectedPaths());
}

async function moveInto(sources, destDir) {
  if (!sources.length) return;
  // Filter out the destination itself and anything already inside it.
  const filtered = sources.filter((s) => s !== destDir && !s.startsWith(destDir + "/"));
  if (!filtered.length) return;
  try {
    const data = await jsonPost("/api/move", { sources: filtered, dest_dir: destDir });
    // Remap open tabs and expanded folders to the new paths.
    for (const { old_path, new_path } of data.moves || []) {
      if (state.openFiles.has(old_path)) {
        const f = state.openFiles.get(old_path);
        state.openFiles.delete(old_path);
        state.openFiles.set(new_path, f);
      }
      if (state.active === old_path) {
        state.active = new_path;
        $("#active-path").textContent = new_path;
      }
      if (state.expanded.has(old_path)) {
        state.expanded.delete(old_path);
        state.expanded.add(new_path);
      }
    }
    await loadTree();
    const moved = (data.moves || []).length;
    const failed = (data.errors || []).length;
    if (failed && moved) toast(`${moved} moved, ${failed} failed`, true);
    else if (failed) toast(`${failed} move(s) failed`, true);
    else if (moved) toast(`Moved ${moved} item${moved === 1 ? "" : "s"} → ${destDir}`);
    clearSelection();
  } catch (e) {
    toast(e.message, true);
  }
}

// ── right-click context menu ────────────────────────────────────────────────
let ctxTarget = null; // { type: "file"|"dir"|null, path: string|null }

function openContextMenu(x, y, target) {
  ctxTarget = target;
  const menu = $("#ctx-menu");
  const items = buildContextItems(target);
  menu.innerHTML = items
    .map((it) => {
      if (it === "-") return `<div class="ctx-sep"></div>`;
      const cls = ["ctx-item"];
      if (it.disabled) cls.push("disabled");
      if (it.danger) cls.push("danger");
      return `<div class="${cls.join(" ")}" data-action="${it.action}">
        <span class="ctx-icon">${it.icon}</span>
        <span>${it.label}</span>
        ${it.kbd ? `<span class="ctx-kbd">${it.kbd}</span>` : ""}
      </div>`;
    })
    .join("");
  menu.hidden = false;
  // clamp to viewport
  const w = menu.offsetWidth || 200;
  const h = menu.offsetHeight || 200;
  const left = Math.min(x, window.innerWidth - w - 4);
  const top = Math.min(y, window.innerHeight - h - 4);
  menu.style.left = left + "px";
  menu.style.top = top + "px";

  // delegate click
  menu.onclick = async (e) => {
    const el = e.target.closest(".ctx-item");
    if (!el || el.classList.contains("disabled")) return;
    closeContextMenu();
    const action = el.dataset.action;
    await runContextAction(action, target);
  };
}

function closeContextMenu() {
  const menu = $("#ctx-menu");
  menu.hidden = true;
  menu.onclick = null;
  ctxTarget = null;
}

function buildContextItems(t) {
  // t.type: "file" | "dir" | null   (null = background click in tree)
  if (t.type === "file") {
    return [
      { icon: "📄", label: "Open", action: "open" },
      "-",
      { icon: "✏", label: "Rename", action: "rename", kbd: "F2" },
      { icon: "🗑", label: "Delete", action: "delete", kbd: "Del", danger: true },
      "-",
      { icon: "📄", label: "New file in this folder", action: "new-file" },
      { icon: "📁", label: "New folder in this folder", action: "new-folder" },
    ];
  }
  if (t.type === "dir") {
    return [
      { icon: "📄", label: "New file", action: "new-file" },
      { icon: "📁", label: "New folder", action: "new-folder" },
      "-",
      { icon: "✏", label: "Rename", action: "rename", kbd: "F2" },
      { icon: "🗑", label: "Delete", action: "delete", kbd: "Del", danger: true },
    ];
  }
  // empty space
  return [
    { icon: "📄", label: "New file", action: "new-file" },
    { icon: "📁", label: "New folder", action: "new-folder" },
  ];
}

async function runContextAction(action, t) {
  if (action === "open") openFile(t.path);
  else if (action === "rename") startRename(t.path);
  else if (action === "delete") {
    if (state.treeSelection.size > 1) await deleteSelected();
    else if (t.path) await deleteMany([t.path]);
  } else if (action === "new-file") {
    const dir = t.type === "dir" ? t.path : (t.type === "file" ? dirname(t.path) : ".");
    newFile(dir);
  } else if (action === "new-folder") {
    const dir = t.type === "dir" ? t.path : (t.type === "file" ? dirname(t.path) : ".");
    newFolder(dir);
  }
}

function dirname(p) {
  const i = p.lastIndexOf("/");
  return i === -1 ? "." : p.slice(0, i);
}

// ── inline rename ──────────────────────────────────────────────────────────
function startRename(path) {
  const row = document.querySelector(`.node-row[data-path="${cssEscape(path)}"]`);
  if (!row) return;
  const label = row.querySelector(".node-label");
  if (!label || label.querySelector(".node-rename")) return; // already renaming
  const oldName = label.textContent;
  const input = document.createElement("input");
  input.type = "text";
  input.className = "node-rename";
  input.value = oldName;
  label.replaceWith(input);
  // select basename up to the last dot (or whole name if no dot)
  const dot = oldName.lastIndexOf(".");
  input.setSelectionRange(0, dot > 0 ? dot : oldName.length);
  setTimeout(() => input.focus(), 0);

  let done = false;
  const finish = async (commit) => {
    if (done) return;
    done = true;
    const newName = input.value.trim();
    input.replaceWith(label);
    label.textContent = oldName;
    if (!commit || !newName || newName === oldName) return;
    try {
      const data = await jsonPost("/api/rename", { path, new_name: newName });
      // patch tabs and active path
      if (state.openFiles.has(path)) {
        const f = state.openFiles.get(path);
        state.openFiles.delete(path);
        state.openFiles.set(data.new_path, f);
      }
      if (state.active === path) state.active = data.new_path;
      if (state.treeSelection.has(path)) {
        state.treeSelection.delete(path);
        state.treeSelection.add(data.new_path);
      }
      if (state.expanded.has(path)) {
        state.expanded.delete(path);
        state.expanded.add(data.new_path);
      }
      await loadTree();
      if (state.active === data.new_path) $("#active-path").textContent = data.new_path;
      toast("Renamed → " + newName);
    } catch (e) {
      toast(e.message, true);
      await loadTree();
    }
  };
  input.addEventListener("keydown", (e) => {
    if (e.key === "Enter") { e.preventDefault(); finish(true); }
    else if (e.key === "Escape") { e.preventDefault(); finish(false); }
    e.stopPropagation();
  });
  input.addEventListener("blur", () => finish(true));
  input.addEventListener("click", (e) => e.stopPropagation());
  input.addEventListener("mousedown", (e) => e.stopPropagation());
}

// ── folder picker ────────────────────────────────────────────────────────────
const picker = { current: null };

async function openPicker(startPath) {
  $("#picker-message").textContent = "";
  $("#picker-overlay").hidden = false;
  await loadPickerDir(startPath || "");
}

async function loadPickerDir(path) {
  try {
    const data = await api("/api/listdirs" + (path ? "?path=" + encodeURIComponent(path) : ""));
    picker.current = data.path;
    $("#picker-path").textContent = data.path;
    const list = $("#picker-list");
    list.innerHTML = "";

    if (data.parent) {
      list.appendChild(makePickerItem("⬆", "..", data.parent));
    }
    if (!data.dirs.length && !data.parent) {
      const empty = document.createElement("div");
      empty.className = "picker-empty";
      empty.textContent = "No subfolders here.";
      list.appendChild(empty);
    }
    data.dirs.forEach((d) => list.appendChild(makePickerItem("📁", d.name, d.path)));
  } catch (e) {
    $("#picker-message").textContent = e.message;
  }
}

function makePickerItem(icon, label, path) {
  const el = document.createElement("div");
  el.className = "picker-item";
  el.innerHTML = `<span class="pi-icon">${icon}</span><span>${label}</span>`;
  el.addEventListener("click", () => loadPickerDir(path));
  return el;
}

async function confirmPicker() {
  if (!picker.current) return;
  try {
    const data = await jsonPost("/api/open", { path: picker.current });
    $("#picker-overlay").hidden = true;
    state.workspace = data.path;
    // reset open editors from any previous workspace
    state.openFiles.clear();
    state.active = null;
    state.expanded.clear();
    state.treeSelection.clear();
    state.treeAnchor = null;
    setWorkspaceUI(true);
    await loadTree();
    showEmptyEditor();
    toast("Opened " + data.name);
  } catch (e) {
    $("#picker-message").textContent = e.message;
  }
}

// ── build & run console ──────────────────────────────────────────────────────
function openConsole() {
  $("#console-pane").classList.add("open");
  document.body.classList.add("console-open");
  setTimeout(() => editor.refresh(), 0);
}
function closeConsole() {
  $("#console-pane").classList.remove("open");
  document.body.classList.remove("console-open");
  setTimeout(() => editor.refresh(), 0);
}
function toggleConsole() {
  if ($("#console-pane").classList.contains("open")) closeConsole();
  else openConsole();
}

function clog(text, cls = "c-out") {
  const out = $("#console-output");
  const span = document.createElement("span");
  span.className = "c-line " + cls;
  span.textContent = text;
  out.appendChild(span);
  out.scrollTop = out.scrollHeight;
}
function clearConsole() { $("#console-output").innerHTML = ""; }

function flags() { return $("#compile-flags").value; }

async function compileActive(silent = false) {
  if (!state.active) return false;
  const f = state.openFiles.get(state.active);
  if (f.dirty) await saveActive();
  openConsole();
  clog(`$ compile ${state.active}  [${flags()}]`, "c-cmd");
  try {
    const data = await jsonPost("/api/compile", {
      path: state.active, flags: flags(),
    });
    clog(data.command, "c-muted");
    if (data.stdout) clog(data.stdout.replace(/\n$/, ""), "c-out");
    if (data.stderr) clog(data.stderr.replace(/\n$/, ""), data.ok ? "c-muted" : "c-err");
    if (data.ok) {
      clog(`✓ compiled → ${data.binary}`, "c-ok");
      if (!silent) toast("Compiled ✓");
      await loadTree();
      return true;
    }
    clog(`✗ compilation failed (exit ${data.returncode})`, "c-err");
    toast("Compilation failed", true);
    return false;
  } catch (e) {
    clog(e.message, "c-err");
    toast(e.message, true);
    return false;
  }
}

async function runActive() {
  if (!state.active) return;
  openConsole();
  clog(`$ run ${state.active}`, "c-cmd");
  try {
    const data = await jsonPost("/api/run", { path: state.active });
    if (data.stdout) clog(data.stdout.replace(/\n$/, ""), "c-out");
    if (data.stderr) clog(data.stderr.replace(/\n$/, ""), "c-err");
    clog(
      data.returncode === 0
        ? "✓ process exited 0"
        : `✗ process exited ${data.returncode}`,
      data.returncode === 0 ? "c-ok" : "c-err"
    );
  } catch (e) {
    clog(e.message, "c-err");
    toast(e.message, true);
  }
}

async function buildAndRun() {
  if (!state.active) return;
  const btn = $("#btn-buildrun");
  btn.disabled = true;
  const label = btn.textContent;
  btn.textContent = "…";
  try {
    const transpiled = await transpileActive();
    if (!transpiled) return;
    const compiled = await compileActive(true);
    if (!compiled) return;
    await runActive();
  } finally {
    btn.disabled = false;
    btn.textContent = label;
  }
}

// remember flags between sessions
$("#compile-flags").value = localStorage.getItem("opc-flags") || "-Wall -Wextra -lm";
$("#compile-flags").addEventListener("change", (e) =>
  localStorage.setItem("opc-flags", e.target.value)
);

// ── documentation ────────────────────────────────────────────────────────────
function escapeHtml(s) {
  return s.replace(/[&<>]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;" }[c]));
}

// inline `code` spans within prose
function inlineCode(s) {
  return escapeHtml(s).replace(/`([^`]+)`/g, "<code>$1</code>");
}

// syntax-highlight a code string into HTML using CodeMirror's runMode
function highlightCode(code, lang) {
  const mode = lang === "c" ? "text/x-csrc" : "opc";
  let html = "";
  CodeMirror.runMode(code, mode, (text, style) => {
    const esc = escapeHtml(text);
    html += style ? `<span class="cm-${style.replace(/ /g, " cm-")}">${esc}</span>` : esc;
  });
  return html;
}

function renderDocSection(topic) {
  const sec = document.createElement("section");
  sec.className = "docs-section";
  sec.id = "doc-" + topic.id;

  const h2 = document.createElement("h2");
  h2.textContent = topic.title;
  sec.appendChild(h2);

  for (const block of topic.blocks) {
    if (block.h) {
      const h3 = document.createElement("h3");
      h3.textContent = block.h;
      sec.appendChild(h3);
    } else if (block.p) {
      const p = document.createElement("p");
      p.innerHTML = inlineCode(block.p);
      sec.appendChild(p);
    } else if (block.note) {
      const n = document.createElement("div");
      n.className = "docs-note";
      n.innerHTML = "<span>💡</span><span>" + inlineCode(block.note) + "</span>";
      sec.appendChild(n);
    } else if (block.opc || block.c) {
      const lang = block.c ? "c" : "opc";
      const pre = document.createElement("pre");
      pre.className = "docs-code lang-" + lang;
      pre.innerHTML =
        `<span class="code-tag">${lang === "c" ? "C output" : "SimplC"}</span>` +
        highlightCode(block.opc || block.c, lang);
      sec.appendChild(pre);
    } else if (block.table) {
      const tbl = document.createElement("table");
      tbl.className = "docs-table";
      const thead = "<tr>" + block.table.head.map((h) => `<th>${escapeHtml(h)}</th>`).join("") + "</tr>";
      const rows = block.table.rows
        .map((r) => "<tr>" + r.map((c) => `<td>${escapeHtml(c)}</td>`).join("") + "</tr>")
        .join("");
      tbl.innerHTML = "<thead>" + thead + "</thead><tbody>" + rows + "</tbody>";
      sec.appendChild(tbl);
    }
  }
  return sec;
}

let docsBuilt = false;
function buildDocs() {
  if (docsBuilt) return;
  const nav = $("#docs-nav");
  const content = $("#docs-content");
  nav.innerHTML = "";
  content.innerHTML = "";
  for (const topic of window.DOCS) {
    const btn = document.createElement("button");
    btn.className = "docs-nav-item";
    btn.textContent = topic.title;
    btn.dataset.target = "doc-" + topic.id;
    btn.onclick = () => {
      document.getElementById("doc-" + topic.id)
        .scrollIntoView({ behavior: "smooth", block: "start" });
    };
    nav.appendChild(btn);
    content.appendChild(renderDocSection(topic));
  }
  // highlight the nav item of the section currently in view
  content.onscroll = () => {
    const sections = [...content.querySelectorAll(".docs-section")];
    const top = content.scrollTop + 80;
    let current = sections[0];
    for (const s of sections) if (s.offsetTop <= top) current = s;
    nav.querySelectorAll(".docs-nav-item").forEach((b) =>
      b.classList.toggle("active", b.dataset.target === current.id)
    );
  };
  docsBuilt = true;
}

function openDocs() {
  buildDocs();
  $("#docs-overlay").hidden = false;
  setTimeout(() => $("#docs-search").focus(), 0);
}
function closeDocs() { $("#docs-overlay").hidden = true; }

function filterDocs(query) {
  const q = query.trim().toLowerCase();
  window.DOCS.forEach((topic) => {
    const navItem = document.querySelector(`.docs-nav-item[data-target="doc-${topic.id}"]`);
    const section = document.getElementById("doc-" + topic.id);
    const hay = (topic.title + " " + JSON.stringify(topic.blocks)).toLowerCase();
    const hit = !q || hay.includes(q);
    if (navItem) navItem.hidden = !hit;
    if (section) section.style.display = hit ? "" : "none";
  });
}

// ── theme ────────────────────────────────────────────────────────────────────
function setTheme(theme) {
  document.documentElement.classList.toggle("dark", theme === "dark");
  document.documentElement.classList.toggle("light", theme === "light");
  localStorage.setItem("opc-theme", theme);
}
function toggleTheme() {
  setTheme(document.documentElement.classList.contains("dark") ? "light" : "dark");
}

// ── pane resizing ────────────────────────────────────────────────────────────
function makeResizable(gutter, target, opts) {
  gutter.addEventListener("mousedown", (e) => {
    e.preventDefault();
    gutter.classList.add("dragging");
    const startX = e.clientX;
    const startW = target.getBoundingClientRect().width;
    const move = (ev) => {
      let w = opts.fromRight ? startW - (ev.clientX - startX) : startW + (ev.clientX - startX);
      w = Math.max(opts.min, Math.min(opts.max(), w));
      target.style.width = w + "px";
      editor.refresh();
      output.refresh();
    };
    const up = () => {
      gutter.classList.remove("dragging");
      document.removeEventListener("mousemove", move);
      document.removeEventListener("mouseup", up);
    };
    document.addEventListener("mousemove", move);
    document.addEventListener("mouseup", up);
  });
}

// ── wiring ───────────────────────────────────────────────────────────────────
$("#btn-save").onclick = saveActive;
$("#btn-transpile").onclick = transpileActive;
$("#btn-theme").onclick = toggleTheme;
$("#btn-refresh").onclick = () => loadTree().then(() => toast("Refreshed"));
$("#btn-side-new").onclick = () => newFile();
$("#btn-side-new-folder").onclick = () => newFolder();
$("#btn-sel-delete").onclick = deleteSelected;
$("#btn-sel-clear").onclick = clearSelection;
$("#btn-close-output").onclick = closeOutput;
$("#btn-copy-c").onclick = () =>
  navigator.clipboard.writeText(output.getValue()).then(() => toast("Copied C output"));

// build & run
$("#btn-buildrun").onclick = buildAndRun;
$("#btn-console").onclick = toggleConsole;
$("#btn-compile").onclick = () => compileActive();
$("#btn-run").onclick = runActive;
$("#btn-clear-console").onclick = clearConsole;
$("#btn-close-console").onclick = closeConsole;

// docs
$("#btn-docs").onclick = openDocs;
$("#docs-close").onclick = closeDocs;
$("#docs-search").addEventListener("input", (e) => filterDocs(e.target.value));
$("#docs-overlay").addEventListener("click", (e) => {
  if (e.target.id === "docs-overlay") closeDocs();
});

// open-folder buttons (top bar + two empty states)
$("#btn-open-folder").onclick = () => openPicker(state.workspace);
$("#btn-open-folder-2").onclick = () => openPicker(state.workspace);
$("#btn-open-folder-3").onclick = () => openPicker(state.workspace);
$("#picker-open").onclick = confirmPicker;
$("#picker-cancel").onclick = () => ($("#picker-overlay").hidden = true);

// right-click on the explorer's empty area shows the same New File / New Folder menu
$("#tree").addEventListener("contextmenu", (e) => {
  if (e.target.closest(".node-row")) return; // row handlers take care of it
  e.preventDefault();
  clearSelection();
  openContextMenu(e.clientX, e.clientY, { type: null, path: null });
});

// close the context menu on outside click, scroll, or window blur
document.addEventListener("mousedown", (e) => {
  const menu = $("#ctx-menu");
  if (!menu.hidden && !menu.contains(e.target)) closeContextMenu();
});
window.addEventListener("scroll", () => {
  if (!$("#ctx-menu").hidden) closeContextMenu();
}, true);
window.addEventListener("blur", closeContextMenu);

makeResizable($("#gutter-left"), $(".sidebar"), { min: 160, max: () => 480, fromRight: false });
makeResizable($("#gutter-right"), $("#output-pane"), { min: 240, max: () => window.innerWidth * 0.7, fromRight: true });

// vertical resize for the console (drag up grows it)
$("#gutter-console").addEventListener("mousedown", (e) => {
  e.preventDefault();
  const gutter = $("#gutter-console");
  const pane = $("#console-pane");
  gutter.classList.add("dragging");
  const startY = e.clientY;
  const startH = pane.getBoundingClientRect().height;
  const move = (ev) => {
    let h = startH - (ev.clientY - startY);
    h = Math.max(90, Math.min(window.innerHeight * 0.7, h));
    pane.style.height = h + "px";
    editor.refresh();
  };
  const up = () => {
    gutter.classList.remove("dragging");
    document.removeEventListener("mousemove", move);
    document.removeEventListener("mouseup", up);
  };
  document.addEventListener("mousemove", move);
  document.addEventListener("mouseup", up);
});

document.addEventListener("keydown", (e) => {
  if ((e.ctrlKey || e.metaKey) && e.key === "s") { e.preventDefault(); saveActive(); }
  if ((e.ctrlKey || e.metaKey) && e.key === "Enter") { e.preventDefault(); transpileActive(); }
  if ((e.ctrlKey || e.metaKey) && (e.key === "b" || e.key === "B")) { e.preventDefault(); buildAndRun(); }
  if (e.key === "Escape" && !$("#docs-overlay").hidden) { closeDocs(); return; }
  // Tree keyboard shortcuts (only when the focus is in the page, not in an input/textarea).
  const t = e.target;
  const inField = t && (t.tagName === "INPUT" || t.tagName === "TEXTAREA" || t.isContentEditable);
  if (inField) return;
  if (!$("#ctx-menu").hidden && e.key === "Escape") { closeContextMenu(); return; }
  if (e.key === "Escape" && state.treeSelection.size > 0) { clearSelection(); return; }
  if (e.key === "Delete" || e.key === "Backspace") {
    if (state.treeSelection.size > 0) { e.preventDefault(); deleteSelected(); return; }
  }
  if (e.key === "F2" && state.treeSelection.size > 0) {
    e.preventDefault();
    const first = state.treeSelection.values().next().value;
    startRename(first);
  }
});

window.addEventListener("beforeunload", (e) => {
  if (state.active) state.openFiles.get(state.active).content = editor.getValue();
  if ([...state.openFiles.values()].some((f) => f.dirty)) {
    e.preventDefault();
    e.returnValue = "";
  }
});

// ── init ─────────────────────────────────────────────────────────────────────
setTheme(localStorage.getItem("opc-theme") || "dark");
refreshState();
