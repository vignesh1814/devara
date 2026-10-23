/*!
 * <devara-playground> -- run Devara in any web page. No server, no build step, no dependencies.
 *
 *   <script src="https://YOUR-HOST/devara-playground.js"></script>
 *   <devara-playground code='"Hello, Devara!" ni chupi'></devara-playground>
 *
 * The compiler is the real Python implementation running in WebAssembly (Pyodide); it is downloaded
 * once, in a Web Worker, the first time a program is run.  See docs/PLAYGROUND.md for every attribute.
 */
(function () {
  "use strict";

  var SCRIPT_URL = (document.currentScript && document.currentScript.src) || "";
  var DEFAULT_BASE = SCRIPT_URL ? SCRIPT_URL.replace(/[^/]*([?#].*)?$/, "") : "./";
  var DEFAULT_PYODIDE = "https://cdn.jsdelivr.net/pyodide/v0.26.4/full/";

  /* ------------------------------------------------------------------ worker (stringified into a Blob) */
  function workerMain() {
    var W = null;
    self.onmessage = async function (e) {
      var m = e.data;
      if (m.type === "init") {
        try {
          importScripts(m.pyodide + "pyodide.js");
          var py = await self.loadPyodide({ indexURL: m.pyodide });
          var resp = await fetch(m.zip);
          if (!resp.ok) throw new Error("could not download " + m.zip + " (HTTP " + resp.status + ")");
          py.unpackArchive(await resp.arrayBuffer(), "zip", { extractDir: "/devara" });
          py.runPython("import sys; sys.path.insert(0, '/devara'); import compiler.web as W");
          W = py.globals.get("W");
          self.postMessage({ type: "ready" });
        } catch (err) {
          self.postMessage({ type: "fatal", error: String((err && err.message) || err) });
        }
      } else if (m.type === "call") {
        var out;
        try { out = JSON.parse(W.dispatch(m.fn, JSON.stringify(m.args))); }
        catch (err) { out = { fatal: String((err && err.message) || err) }; }
        self.postMessage({ type: "result", id: m.id, result: out });
      }
    };
  }

  /* ------------------------------------------------------------------ shared runtime (one worker per page) */
  var Runtime = {
    worker: null, ready: null, pending: {}, seq: 0, cfg: null,
    configure: function (cfg) { if (!this.cfg) this.cfg = cfg; },
    start: function () {
      var self = this;
      if (this.ready) return this.ready;
      var url = URL.createObjectURL(new Blob(["(" + workerMain.toString() + ")()"], { type: "text/javascript" }));
      var w = (this.worker = new Worker(url));
      this.ready = new Promise(function (resolve, reject) {
        w.onmessage = function (e) {
          var m = e.data;
          if (m.type === "ready") resolve();
          else if (m.type === "fatal") { self.ready = null; self.worker = null; w.terminate(); reject(new Error(m.error)); }
          else if (m.type === "result" && self.pending[m.id]) {
            var p = self.pending[m.id]; delete self.pending[m.id]; clearTimeout(p.timer); p.resolve(m.result);
          }
        };
        w.onerror = function (ev) { self.ready = null; self.worker = null; reject(new Error(ev.message || "worker failed")); };
      });
      w.postMessage({ type: "init", pyodide: this.cfg.pyodide, zip: this.cfg.zip });
      return this.ready;
    },
    call: function (fn, args, timeoutMs) {
      var self = this;
      return this.start().then(function () {
        return new Promise(function (resolve) {
          var id = ++self.seq;
          var timer = timeoutMs ? setTimeout(function () { self.kill("timeout"); }, timeoutMs) : 0;
          self.pending[id] = { resolve: resolve, timer: timer };
          self.worker.postMessage({ type: "call", id: id, fn: fn, args: args });
        });
      });
    },
    /* Stop button / timeout: the only way to interrupt a running interpreter is to drop the worker. */
    kill: function (reason) {
      var pend = this.pending; this.pending = {};
      if (this.worker) this.worker.terminate();
      this.worker = null; this.ready = null;
      Object.keys(pend).forEach(function (k) { clearTimeout(pend[k].timer); pend[k].resolve({ killed: reason }); });
    },
  };

  /* ------------------------------------------------------------------ syntax highlighting */
  var KEYWORDS = ("int float bool char padham void nijam abaddham ayite lekunte unnanta varaku prati pratisari nundi " +
    "modhalu lo pettu ni tho chaduvu chupi charya ivvu aapu saagu").split(" ");
  var KW = {}; KEYWORDS.forEach(function (k) { KW[k] = 1; });
  var TOKEN = /(#[^\n]*)|("(?:[^"\\\n]|\\.)*"?)|('(?:[^'\\\n]|\\.)*'?)|(0[xX][0-9a-fA-F]+|\d+\.\d+|\d+)|([A-Za-z_][A-Za-z0-9_]*)/g;

  function esc(s) { return s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;"); }
  function highlight(src) {
    var out = "", last = 0, m;
    TOKEN.lastIndex = 0;
    while ((m = TOKEN.exec(src))) {
      out += esc(src.slice(last, m.index));
      var cls = m[1] ? "c" : m[2] || m[3] ? "s" : m[4] ? "n" : KW[m[5].toLowerCase()] ? "k" : "";
      out += cls ? '<span class="' + cls + '">' + esc(m[0]) + "</span>" : esc(m[0]);
      last = TOKEN.lastIndex;
    }
    return out + esc(src.slice(last)) + "\n";
  }

  /* ------------------------------------------------------------------ helpers */
  function b64enc(s) { var b = new TextEncoder().encode(s), t = ""; b.forEach(function (c) { t += String.fromCharCode(c); }); return btoa(t).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, ""); }
  function b64dec(s) { s = s.replace(/-/g, "+").replace(/_/g, "/"); while (s.length % 4) s += "="; var t = atob(s), b = new Uint8Array(t.length); for (var i = 0; i < t.length; i++) b[i] = t.charCodeAt(i); return new TextDecoder().decode(b); }
  function dedent(s) {
    var lines = s.replace(/^\n+|\s+$/g, "").split("\n"), min = Infinity;
    lines.forEach(function (l) { if (l.trim()) min = Math.min(min, l.match(/^[ \t]*/)[0].length); });
    return lines.map(function (l) { return l.slice(min === Infinity ? 0 : min); }).join("\n");
  }

  var TABS = { output: "Output", input: "Input", tokens: "Tokens", ast: "AST", ir: "IR", opt: "Optimized IR" };

  var CSS = [
    ":host{display:block;--bg:#fff;--fg:#1f2328;--mut:#656d76;--line:#d0d7de;--panel:#f6f8fa;--acc:#0b6bcb;--accfg:#fff;--err:#cf222e;--k:#8250df;--s:#0a7d3e;--n:#b35900;--c:#6e7781;--r:8px;" +
      "font:14px/1.5 system-ui,-apple-system,'Segoe UI',Roboto,sans-serif;color:var(--fg);min-width:260px}",
    ":host([hidden]){display:none}",
    ":host([theme=dark]){--bg:#0d1117;--fg:#e6edf3;--mut:#8b949e;--line:#30363d;--panel:#161b22;--acc:#2f81f7;--err:#ff7b72;--k:#d2a8ff;--s:#7ee787;--n:#ffa657;--c:#8b949e}",
    "@media (prefers-color-scheme:dark){:host(:not([theme=light]):not([theme=dark])){--bg:#0d1117;--fg:#e6edf3;--mut:#8b949e;--line:#30363d;--panel:#161b22;--acc:#2f81f7;--err:#ff7b72;--k:#d2a8ff;--s:#7ee787;--n:#ffa657;--c:#8b949e}}",
    "*{box-sizing:border-box}",
    ".box{container-type:inline-size;display:flex;flex-direction:column;height:var(--h,460px);border:1px solid var(--line);border-radius:var(--r);background:var(--bg);overflow:hidden}",
    ".bar{display:flex;gap:6px;align-items:center;padding:6px 8px;border-bottom:1px solid var(--line);background:var(--panel);flex-wrap:wrap}",
    ".brand{font-weight:600;margin-right:auto;letter-spacing:.2px}",
    "button{font:inherit;cursor:pointer;border:1px solid var(--line);background:var(--bg);color:var(--fg);border-radius:6px;padding:3px 10px;line-height:1.5}",
    "button:hover{border-color:var(--mut)}button:focus-visible,textarea:focus-visible,[role=tab]:focus-visible{outline:2px solid var(--acc);outline-offset:1px}",
    "button.run{background:var(--acc);color:var(--accfg);border-color:var(--acc);font-weight:600}",
    "button[disabled]{opacity:.5;cursor:default}",
    ".main{flex:1;min-height:0;display:flex;flex-direction:column}",
    "@container (min-width:720px){.main{flex-direction:row}.main>.ed{border-bottom:0;border-right:1px solid var(--line)}}",
    ".ed{flex:1 1 55%;min-height:0;min-width:0;position:relative;display:flex;border-bottom:1px solid var(--line)}",
    ".gut{padding:8px 6px 8px 10px;text-align:right;color:var(--mut);user-select:none;font:13px/1.55 ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;background:var(--panel);overflow:hidden;white-space:pre}",
    ".gut b{font-weight:400;display:block}.gut b.bad{color:var(--err);font-weight:700}",
    ".code{position:relative;flex:1;min-width:0}",
    ".code pre,.code textarea{margin:0;padding:8px 10px;position:absolute;inset:0;border:0;font:13px/1.55 ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;tab-size:4;white-space:pre;overflow:auto;letter-spacing:0}",
    ".code pre{pointer-events:none;color:var(--fg);overflow:hidden}",
    ".code textarea{background:transparent;color:transparent;caret-color:var(--fg);resize:none;outline:none}",
    ".code textarea::selection{background:color-mix(in srgb,var(--acc) 30%,transparent);color:transparent}",
    ".k{color:var(--k);font-weight:600}.s{color:var(--s)}.n{color:var(--n)}.c{color:var(--c);font-style:italic}",
    ".out{flex:1 1 45%;min-height:0;min-width:0;display:flex;flex-direction:column}",
    "[role=tablist]{display:flex;gap:2px;padding:0 6px;border-bottom:1px solid var(--line);background:var(--panel);overflow-x:auto}",
    "[role=tab]{border:0;border-bottom:2px solid transparent;border-radius:0;background:none;padding:5px 9px;color:var(--mut);white-space:nowrap}",
    "[role=tab][aria-selected=true]{color:var(--fg);border-bottom-color:var(--acc)}",
    ".pane{flex:1;min-height:0;overflow:auto;padding:8px 10px;font:13px/1.5 ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;white-space:pre-wrap;word-break:break-word;margin:0}",
    ".pane textarea{width:100%;height:100%;min-height:80px;border:1px solid var(--line);border-radius:6px;background:var(--bg);color:var(--fg);font:inherit;padding:6px;resize:none}",
    ".err{color:var(--err)}.dim{color:var(--mut)}",
    "a.d{display:block;color:var(--err);cursor:pointer;text-decoration:none}a.d:hover{text-decoration:underline}",
    ".status{padding:3px 10px;border-top:1px solid var(--line);background:var(--panel);color:var(--mut);font-size:12px;display:flex;gap:10px;justify-content:space-between}",
    ".status a{color:var(--mut)}",
    ".toast{position:absolute;right:10px;bottom:34px;background:var(--fg);color:var(--bg);padding:4px 10px;border-radius:6px;font-size:12px;opacity:0;transition:opacity .2s;pointer-events:none}.toast.on{opacity:.92}",
    ".sr{position:absolute;left:-9999px}",
  ].join("\n");

  /* ------------------------------------------------------------------ the element */
  class DevaraPlayground extends HTMLElement {
    static get observedAttributes() { return ["code", "stdin", "theme", "height", "readonly", "autorun"]; }

    constructor() {
      super();
      this._root = this.attachShadow({ mode: "open" });
      this._cache = {};
      this._tab = "output";
      this._built = false;
    }

    connectedCallback() {
      if (this._built || this._waiting) return;
      // A parser-created element is upgraded when its start tag is seen, before its children (the inline
      // <script type="text/devara"> source) exist. Wait for the document to finish parsing.
      if (document.readyState === "loading") {
        var self0 = this; this._waiting = true;
        document.addEventListener("DOMContentLoaded", function () { self0._waiting = false; self0.connectedCallback(); }, { once: true });
        return;
      }
      this._built = true;
      var self = this;
      this._code = this._initialCode();
      this._stdin = this.getAttribute("stdin") || "";
      this._build();
      var src = this.getAttribute("src");
      if (src) fetch(src).then(function (r) { return r.text(); }).then(function (t) { self.code = t; });
      if (this.hasAttribute("autorun")) { this._ranOnce = true; this._whenVisible(function () { self.run(); }); }
    }

    attributeChangedCallback(name, _old, val) {
      var self = this;
      if (!this._built) return;
      if (name === "code") this.code = val || "";
      else if (name === "stdin") { this._stdin = val || ""; this._ta2.value = this._stdin; }
      else if (name === "height") this.style.setProperty("--h", this._height());
      else if (name === "readonly") this._ta.readOnly = this.hasAttribute("readonly");
      else if (name === "autorun" && val !== null && !this._ranOnce) { this._ranOnce = true; this._whenVisible(function () { self.run(); }); }
    }

    get code() { return this._code; }
    set code(v) { this._code = String(v == null ? "" : v); if (this._ta) { this._ta.value = this._code; this._sync(); } this._cache = {}; }
    get stdin() { return this._stdin; }
    set stdin(v) { this._stdin = String(v == null ? "" : v); if (this._ta2) this._ta2.value = this._stdin; }

    _initialCode() {
      var attr = this.getAttribute("code");
      if (attr != null) return attr;
      var child = this.querySelector('script[type="text/devara"],textarea,pre');
      return child ? dedent(child.textContent) : "";
    }
    _height() { var h = this.getAttribute("height") || "460"; return /^\d+$/.test(h) ? h + "px" : h; }
    _config() {
      var base = this.getAttribute("base") || DEFAULT_BASE;
      if (!/\/$/.test(base)) base += "/";
      Runtime.configure({ pyodide: this.getAttribute("pyodide") || DEFAULT_PYODIDE, zip: base + "devara.zip" });
      return base;
    }
    _whenVisible(fn) {
      if (!("IntersectionObserver" in window)) return fn();
      var io = new IntersectionObserver(function (es) { if (es[0].isIntersecting) { io.disconnect(); fn(); } });
      io.observe(this);
    }

    _build() {
      var self = this, tabs = (this.getAttribute("tabs") || "output,input,ast,ir,opt").split(",").map(function (s) { return s.trim(); }).filter(function (t) { return TABS[t]; });
      if (tabs.indexOf("output") < 0) tabs.unshift("output");
      this._tabs = tabs;
      this.style.setProperty("--h", this._height());
      var ro = this.hasAttribute("readonly");
      this._root.innerHTML =
        "<style>" + CSS + "</style>" +
        '<div class="box" part="box">' +
        '<div class="bar"><span class="brand">Devara</span>' +
        '<button class="run" title="Run (Ctrl/Cmd+Enter)">&#9654; Run</button>' +
        '<button class="stop" hidden title="Stop the program">&#9632; Stop</button>' +
        '<button class="reset" title="Restore the original code"' + (ro ? " hidden" : "") + ">Reset</button>" +
        '<button class="share" title="Copy a link to this program">Share</button>' +
        '<button class="embed" title="Copy an HTML snippet to embed this program">Embed</button></div>' +
        '<div class="main"><div class="ed"><div class="gut" aria-hidden="true"></div><div class="code">' +
        '<pre aria-hidden="true"></pre><textarea spellcheck="false" autocapitalize="off" autocomplete="off" autocorrect="off" aria-label="Devara source code"></textarea></div></div>' +
        '<div class="out"><div role="tablist" aria-label="Results">' +
        tabs.map(function (t) { return '<button role="tab" data-tab="' + t + '" aria-selected="' + (t === "output") + '">' + TABS[t] + "</button>"; }).join("") +
        '</div><pre class="pane" role="tabpanel" aria-live="polite" tabindex="0"></pre></div></div>' +
        '<div class="status"><span class="st">Ready</span><span class="dim">Devara &middot; runs in your browser</span></div>' +
        '<div class="toast" role="status"></div></div>';
      var $ = function (s) { return self._root.querySelector(s); };
      this._ta = $("textarea"); this._pre = $(".code pre"); this._gut = $(".gut"); this._pane = $(".pane");
      this._st = $(".st"); this._toast = $(".toast"); this._runBtn = $(".run"); this._stopBtn = $(".stop");
      this._ta.value = this._code; this._ta.readOnly = ro; this._orig = this._code;
      this._ta2 = document.createElement("textarea");
      this._ta2.value = this._stdin; this._ta2.placeholder = "Text the program reads with  x ni chaduvu"; this._ta2.setAttribute("aria-label", "Program input");
      this._ta2.addEventListener("input", function () { self._stdin = self._ta2.value; });

      this._ta.addEventListener("input", function () { self._code = self._ta.value; self._cache = {}; self._bad = {}; self._sync(); });
      this._ta.addEventListener("scroll", function () { self._pre.scrollTop = self._ta.scrollTop; self._pre.scrollLeft = self._ta.scrollLeft; self._gut.scrollTop = self._ta.scrollTop; });
      this._ta.addEventListener("keydown", function (e) {
        if (e.key === "Enter" && (e.ctrlKey || e.metaKey)) { e.preventDefault(); self.run(); }
        else if (e.key === "Tab" && !e.shiftKey && !self._ta.readOnly) { e.preventDefault(); document.execCommand && document.execCommand("insertText", false, "    "); }
      });
      this._runBtn.addEventListener("click", function () { self.run(); });
      this._stopBtn.addEventListener("click", function () { Runtime.kill("stopped"); });
      $(".reset").addEventListener("click", function () { self.code = self._orig; self._last = null; self._bad = {}; self._show("output"); self._renderOutput(); self._sync(); self._status("Ready"); });
      $(".share").addEventListener("click", function () { self._copy(self._link(), "Link copied"); });
      $(".embed").addEventListener("click", function () { self._copy(self._snippet(), "Embed code copied"); });
      this._root.querySelectorAll("[role=tab]").forEach(function (b) { b.addEventListener("click", function () { self._show(b.dataset.tab); }); });
      this._root.querySelector("[role=tablist]").addEventListener("keydown", function (e) {
        var i = self._tabs.indexOf(self._tab), d = e.key === "ArrowRight" ? 1 : e.key === "ArrowLeft" ? -1 : 0;
        if (d) { e.preventDefault(); var t = self._tabs[(i + d + self._tabs.length) % self._tabs.length]; self._show(t); self._root.querySelector('[data-tab="' + t + '"]').focus(); }
      });
      this._bad = {};
      this._last = null;
      this._sync();
      this._renderOutput();
    }

    _sync() {
      var v = this._ta.value, n = v.split("\n").length, g = "";
      for (var i = 1; i <= n; i++) g += '<b class="' + (this._bad && this._bad[i] ? "bad" : "") + '">' + i + "</b>";
      this._gut.innerHTML = g;
      this._pre.innerHTML = highlight(v);
    }

    _status(t) { this._st.textContent = t; }
    _copy(text, msg) {
      var self = this, done = function () { self._toast.textContent = msg; self._toast.classList.add("on"); setTimeout(function () { self._toast.classList.remove("on"); }, 1400); };
      if (navigator.clipboard && navigator.clipboard.writeText) navigator.clipboard.writeText(text).then(done, function () { window.prompt("Copy:", text); });
      else window.prompt("Copy:", text);
    }
    _link() {
      var base = this._config();
      return base + "index.html#code=" + b64enc(this._code) + (this._stdin ? "&stdin=" + b64enc(this._stdin) : "");
    }
    _snippet() {
      var base = this._config();
      var url = base + "embed.html#code=" + b64enc(this._code) + (this._stdin ? "&stdin=" + b64enc(this._stdin) : "");
      return '<iframe src="' + url + '" title="Devara playground" width="100%" height="460" style="border:0" loading="lazy" allow="clipboard-write"></iframe>';
    }

    _show(tab) {
      var self = this;
      this._tab = tab;
      this._root.querySelectorAll("[role=tab]").forEach(function (b) { b.setAttribute("aria-selected", String(b.dataset.tab === tab)); });
      if (tab === "output") return this._renderOutput();
      if (tab === "input") { this._pane.textContent = ""; this._pane.appendChild(this._ta2); return; }
      var key = tab + "\u0000" + this._code;
      if (this._cache[key]) return this._renderStage(this._cache[key]);
      this._pane.innerHTML = '<span class="dim">Loading&hellip;</span>';
      this._config();
      Runtime.call("stage", [this._code, tab], 20000).then(function (r) {
        if (r.killed || r.fatal) return self._pane.innerHTML = '<span class="err">' + esc(r.fatal || "interrupted") + "</span>";
        self._cache[key] = r;
        if (self._tab === tab) self._renderStage(r);
      }, function (e) { self._pane.innerHTML = '<span class="err">' + esc(e.message) + "</span>"; });
    }
    _renderStage(r) {
      if (r.diagnostics && r.diagnostics.length) return this._renderDiags(r.diagnostics);
      this._pane.textContent = r.text || "(empty)";
    }

    _setOut(output, error, diags) { this._last = { output: output, error: error, diags: diags || [] }; this._renderOutput(); }
    _renderOutput() {
      if (this._tab !== "output") return;
      var l = this._last;
      this._pane.textContent = "";
      if (!l) { var h = document.createElement("span"); h.className = "dim"; h.textContent = "Press Run (Ctrl/Cmd+Enter) to see the output here."; this._pane.appendChild(h); return; }
      if (l.diags.length) return this._renderDiags(l.diags);
      if (!l.output && !l.error && !l.msg) { var d = document.createElement("span"); d.className = "dim"; d.textContent = "(the program printed nothing)"; this._pane.appendChild(d); return; }
      this._pane.appendChild(document.createTextNode(l.output));
      if (l.error) { var e = document.createElement("div"); e.className = "err"; e.textContent = "devara: runtime error: " + l.error; this._pane.appendChild(e); }
      if (l.msg) { var m = document.createElement("div"); m.className = "dim"; m.textContent = l.msg; this._pane.appendChild(m); }
    }
    _renderDiags(diags) {
      var self = this;
      this._pane.textContent = "";
      diags.forEach(function (d) {
        var a = document.createElement("a"); a.className = "d"; a.textContent = d.text.replace(/^[^:]*:(?=\d+:\d+)/, "");
        if (d.line) a.addEventListener("click", function () { self._goto(d.line, d.column); });
        self._pane.appendChild(a);
      });
    }
    _goto(line, col) {
      var lines = this._ta.value.split("\n"), pos = 0;
      for (var i = 0; i < line - 1 && i < lines.length; i++) pos += lines[i].length + 1;
      pos += Math.max(0, (col || 1) - 1);
      this._ta.focus(); this._ta.setSelectionRange(pos, pos);
      var lh = parseFloat(getComputedStyle(this._ta).lineHeight) || 20;
      this._ta.scrollTop = Math.max(0, (line - 3) * lh);
    }

    /** Compile and run the current code. Resolves with the result object; also fires a `devara-run` event. */
    run() {
      var self = this;
      if (this._running) return this._running;
      this._config();
      this._show("output");
      this._runBtn.disabled = true; this._stopBtn.hidden = false;
      this._status(Runtime.ready ? "Running…" : "Loading the compiler (first run only, about 5 MB)…");
      this._last = null;
      this._pane.innerHTML = '<span class="dim">' + (Runtime.ready ? "Running&hellip;" : "Loading the compiler&hellip;") + "</span>";
      var timeout = parseInt(this.getAttribute("timeout") || "15000", 10);
      var steps = parseInt(this.getAttribute("max-steps") || "5000000", 10);
      var frames = parseInt(this.getAttribute("max-depth") || "120000", 10);
      var done = function () { self._running = null; self._runBtn.disabled = false; self._stopBtn.hidden = true; };
      this._running = Runtime.call("run", [this._code, this._stdin, steps, "main.tel", frames], timeout).then(function (r) {
        done();
        var bad = {};
        if (r.killed) {
          self._setOut("", "", []); self._last.msg = r.killed === "timeout" ? "Stopped: the program ran longer than " + timeout / 1000 + " s." : "Stopped.";
          self._renderOutput(); self._status(r.killed === "timeout" ? "Timed out" : "Stopped");
        } else if (r.fatal) {
          self._setOut("", r.fatal); self._status("Internal error");
        } else {
          (r.diagnostics || []).forEach(function (d) { if (d.line) bad[d.line] = 1; });
          self._setOut(r.output, r.error, r.diagnostics);
          self._status(r.diagnostics.length ? r.diagnostics.length + " error" + (r.diagnostics.length > 1 ? "s" : "") :
            (r.ok ? "Finished" : "Stopped with an error") + " in " + r.ms + " ms");
        }
        self._bad = bad; self._sync();
        self.dispatchEvent(new CustomEvent("devara-run", { detail: r, bubbles: true, composed: true }));
        return r;
      }, function (err) {
        done();
        self._setOut("", "Could not load the compiler: " + err.message + "\nCheck your connection (it is fetched from a CDN) and try again.");
        self._status("Load failed");
      });
      return this._running;
    }
  }

  if (!customElements.get("devara-playground")) customElements.define("devara-playground", DevaraPlayground);
  window.DevaraPlayground = { Element: DevaraPlayground, encode: b64enc, decode: b64dec, runtime: Runtime };
})();
