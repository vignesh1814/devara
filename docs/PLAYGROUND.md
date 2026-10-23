# Devara Playground

Run Devara in a web page, with no server. The real compiler front end (lexer, parser, semantic analysis) and the
reference interpreter run in your browser through [Pyodide](https://pyodide.org) (Python in WebAssembly), inside a Web
Worker, so a runaway program can never freeze the page.

## Build and host

```text
python scripts/build_playground.py            # writes build/playground/
```

Upload that folder to any static host (GitHub Pages, Netlify, S3, your own nginx). The repository's
`.github/workflows/pages.yml` does this on every push to `main`. For local use:

```text
python -m http.server 8000 -d build/playground     # then open http://localhost:8000
```

The bundle is five files: `index.html` (full page), `embed.html` (iframe page), `devara-playground.js` (the web
component), `devara.zip` (the compiler, 70 KB) and `examples.json`. Pyodide itself (about 5 MB) is downloaded from the
jsDelivr CDN the first time someone presses Run, then cached by the browser.

> Hosts other than your own must send `Access-Control-Allow-Origin: *` for `devara.zip` if pages from *other* sites
> embed your copy. GitHub Pages, Netlify, Cloudflare Pages and every CDN already do.

## Embed it anywhere

### 1. A web component (recommended)

```html
<script src="https://YOUR-HOST/devara-playground.js"></script>

<devara-playground code='"Hello, Devara!" ni chupi'></devara-playground>
```

Longer programs read better as inline source (it is dedented for you, and nothing needs escaping):

```html
<devara-playground height="320" tabs="output,input">
  <script type="text/devara">
    int i
    prati i 1 nundi 6 varaku {
        i * i ni chupi
    }
  </script>
</devara-playground>
```

Any number of players can share one page; they share one compiler download and one worker.

### 2. An iframe

Press **Embed** in the playground to copy a snippet containing your current program, or write it by hand:

```html
<iframe src="https://YOUR-HOST/embed.html#code=BASE64URL&autorun=1&theme=dark"
        width="100%" height="460" style="border:0" loading="lazy" title="Devara playground"></iframe>
```

`embed.html` reads these from the URL hash: `code` and `stdin` (base64url of UTF-8 text; `DevaraPlayground.encode(text)`
produces it), `theme`, `tabs`, `timeout`, and the flags `autorun=1` and `readonly=1`.

### 3. A shareable link

**Share** copies `https://YOUR-HOST/index.html#code=BASE64URL`. Add `&run=1` to run it on load.

## Attributes

| Attribute | Default | Meaning |
|---|---|---|
| `code` | child text | Source code. If absent, the text of a child `<script type="text/devara">`, `<textarea>` or `<pre>`. |
| `src` | – | URL of a `.tel` file to load into the editor. |
| `stdin` | empty | Text the program reads with `x ni chaduvu`. |
| `height` | `460` | Pixels, or any CSS length (`100%`, `70vh`). |
| `theme` | `auto` | `light`, `dark`, or follow the system. |
| `tabs` | `output,input,ast,ir,opt` | Result tabs to show. Also available: `tokens`. `output` is always present. |
| `readonly` | off | Present = the code cannot be edited (good for tutorials). |
| `autorun` | off | Present = run once the player scrolls into view. |
| `timeout` | `15000` | Wall-clock milliseconds before a program is stopped. |
| `max-steps` | `5000000` | Interpreter step budget (stops infinite loops quickly, with a clear message). |
| `max-depth` | `120000` | Python frame limit; about 6 frames per Devara call, so roughly 20,000 nested calls. |
| `base` | folder of the script | Where `devara.zip`, `embed.html` and `index.html` live, if you host them apart from the script. |
| `pyodide` | jsDelivr, v0.26.4 | Base URL of a Pyodide distribution, to self-host the runtime. |

## JavaScript API

```js
const pg = document.querySelector("devara-playground");
pg.code = '5 ni chupi';           // get / set the source
pg.stdin = "3 4";                 // get / set the input
const result = await pg.run();    // { ok, status, output, error, diagnostics, ms, steps }
pg.addEventListener("devara-run", e => console.log(e.detail));
```

`status` is `0` for success, `1` for a compile or runtime error, `124` for the step limit and `125` for the recursion
limit. Style the player from outside with CSS custom properties on the element (`--bg`, `--fg`, `--line`, `--panel`,
`--acc`, `--r`) or the `box` part (`devara-playground::part(box)`).

## What it is, and is not

- **Same language, different engine.** The browser runs your program with the reference interpreter, not the native
  x86-64 code generator. The two are cross-checked on a 128-program corpus (`tests/unit/test_web.py`), so output is
  identical for all but one program: `tests/corpus/recursion/073_deep_and_misc_recursion` recurses deeper than the
  playground allows by default.
- **Limits.** Programs are bounded by `timeout`, `max-steps` and `max-depth` (above). The interpreter is a few orders of
  magnitude slower than compiled code, so heavy benchmarks belong in the real compiler.
- **Input is not interactive.** Programs read from the *Input* tab, supplied before they run.
- **Privacy.** Nothing is uploaded: the compiler runs locally and the only network requests are for the page's own
  files and the Pyodide runtime.
- **Security.** Program text and output are only ever inserted as text, never HTML, so a program cannot script the page.
  Code runs inside Pyodide's WebAssembly sandbox in a Web Worker.

## Troubleshooting

| Symptom | Cause |
|---|---|
| "Could not load the compiler" | No network access to the CDN, or `devara.zip` is not reachable (wrong `base`, or missing CORS header on a cross-site embed). |
| Nothing happens on a file:// page | Browsers block Web Workers and `fetch` from `file://`. Serve the folder over HTTP. |
| Strict Content-Security-Policy | The page needs `worker-src blob:`, `script-src` for the host and `cdn.jsdelivr.net`, and `connect-src` for both. |
