// ── OPC IDE frontend ────────────────────────────────────────────────────────
const $ = (sel) => document.querySelector(sel);

const state = {
  openFiles: new Map(), // path -> { content, ext, dirty }
  active: null,
  expanded: new Set(),
  workspace: null, // absolute path of open folder, or null
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
    row.className = "node-row";
    const isOpen = state.expanded.has(node.path);
    row.innerHTML = `
      <span class="node-caret ${isOpen ? "open" : ""}">▶</span>
      <span class="node-icon">${isOpen ? "📂" : "📁"}</span>
      <span class="node-label">${node.name}</span>
      <span class="node-del" title="Delete">🗑</span>`;
    const children = document.createElement("div");
    children.className = "node-children";
    children.hidden = !isOpen;
    node.children.forEach((c) => children.appendChild(renderNode(c, depth + 1)));

    row.addEventListener("click", (e) => {
      if (e.target.classList.contains("node-del")) {
        e.stopPropagation();
        return deleteEntry(node.path, node.name);
      }
      const nowOpen = children.hidden;
      children.hidden = !nowOpen;
      row.querySelector(".node-caret").classList.toggle("open", nowOpen);
      row.querySelector(".node-icon").textContent = nowOpen ? "📂" : "📁";
      if (nowOpen) state.expanded.add(node.path);
      else state.expanded.delete(node.path);
    });
    wrap.appendChild(row);
    wrap.appendChild(children);
    return wrap;
  }

  const row = document.createElement("div");
  row.className = "node-row file-node";
  row.dataset.path = node.path;
  if (node.path === state.active) row.classList.add("active");
  row.innerHTML = `
    <span class="node-caret"></span>
    <span class="node-icon ${extClass(node.ext)}">${fileIcon(node.ext)}</span>
    <span class="node-label">${node.name}</span>
    <span class="node-del" title="Delete">🗑</span>`;
  row.addEventListener("click", (e) => {
    if (e.target.classList.contains("node-del")) {
      e.stopPropagation();
      return deleteEntry(node.path, node.name);
    }
    openFile(node.path);
  });
  return row;
}

function highlightActiveInTree() {
  document.querySelectorAll(".file-node").forEach((el) => {
    el.classList.toggle("active", el.dataset.path === state.active);
  });
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

function closeFile(path) {
  const f = state.openFiles.get(path);
  if (f && f.dirty && !confirm(`Discard unsaved changes to ${path}?`)) return;
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
function showModal(title, placeholder, okLabel, onOk) {
  const overlay = $("#modal-overlay");
  $("#modal-title").textContent = title;
  $("#modal-message").textContent = "";
  const input = $("#modal-input");
  input.value = "";
  input.placeholder = placeholder;
  $("#modal-ok").textContent = okLabel;
  overlay.hidden = false;
  setTimeout(() => input.focus(), 0);

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

function newFile() {
  showModal("New file", "path/to/file.opc", "Create", async (name) => {
    await jsonPost("/api/create", { path: name, type: "file" });
    await loadTree();
    openFile(name);
    toast("Created " + name);
  });
}

function newFolder() {
  showModal("New folder", "path/to/folder", "Create", async (name) => {
    await jsonPost("/api/create", { path: name, type: "dir" });
    await loadTree();
    toast("Created " + name);
  });
}

async function deleteEntry(path, name) {
  if (!confirm(`Delete "${name}"? This cannot be undone.`)) return;
  try {
    await jsonPost("/api/delete", { path });
    if (state.openFiles.has(path)) {
      state.openFiles.delete(path);
      if (state.active === path) {
        const next = [...state.openFiles.keys()].pop();
        if (next) activate(next);
        else showEmptyEditor();
      } else {
        renderTabs();
      }
    }
    await loadTree();
    toast("Deleted " + name);
  } catch (e) {
    toast(e.message, true);
  }
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
$("#btn-side-new").onclick = newFile;
$("#btn-side-new-folder").onclick = newFolder;
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
  if (e.key === "Escape" && !$("#docs-overlay").hidden) closeDocs();
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
