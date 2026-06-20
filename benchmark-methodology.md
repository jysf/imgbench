<!--
  This is the methodology this repo implements (lightly adapted from the
  original competitive-research report). The equal-quality protocol (§3.4) is
  the non-negotiable gate enforced throughout the code:
    * "build the search around them / interpolate bytes at the target score"
      -> bench/sweep.py
    * grader independence (§3.3/§3.6), default to the Cloudinary C reference
      -> bench/grade/
    * fairness controls (§3.5: threads, AVIF effort, metadata strip)
      -> bench/adapters/base.py:EncodeConfig
    * crustyimg --features webp-lossy,avif gate (§3.6)
      -> bench/adapters/crustyimg.py:feature_check
  See README.md for the full rule->code mapping.
-->

# crustyimg — Competitive Research & Benchmark Design

**Scope:** How image-optimization tools integrate into CI/CD pipelines for web image prep, and which 1–3 tools make the fairest head-to-head comparison for benchmarking crustyimg.
**Date:** 2026-06-18 · **rev. 2** (crustyimg repo now accessed — see *Repo reality check*; Cloudinary positioning added; grader-collusion control added)
**Confidence convention:** each external/competitive claim is marked **[H]** high / **[M]** medium / **[L]** low. Folklore (community practice, not vendor-documented) is flagged inline.

---

## Executive summary (read this first)

- **Closest apples-to-apples comparison target: `rimage`** (Rust, MIT OR Apache-2.0, single binary, WebP/AVIF/MozJPEG/OxiPNG/JXL). It is the only mainstream tool that shares crustyimg's *exact* shape — a permissively-licensed Rust CLI that prepares web images in a build/CI step — so size/speed numbers are directly attributable to the tool, not to a runtime. **[H]**
- **Best "ecosystem baseline" target: `sharp`** (Node/libvips, Apache-2.0). It is the de-facto engine under nearly every build-tool image pipeline (vite-imagetools, vite-plugin-image-optimizer, Astro/Nuxt image services), so beating or matching it is the commercially meaningful bar — but it's a *different shape* (Node runtime + native libvips), which must be handled carefully in the methodology. **[H]**
- **Best CI-integration exemplar: `calibreapp/image-actions`** — the canonical "optimize the images in this PR" GitHub Action. Useful as a *CI-pattern* reference rather than a raw encoder benchmark, because it wraps libvips/mozjpeg and commits bytes back to the PR. **[H]**
- **Sharpest CI insight:** the entire mainstream toolchain optimizes images at **fixed quality numbers** and gates (when it gates at all) on **page-level byte budgets** (Lighthouse CI `resource-summary`), *not* on **per-image perceptual quality**. crustyimg's `diff --fail-under <SSIMULACRA2>` occupies near-empty space: a built-in, per-asset, perceptual visual-regression gate. The closest existing "target-driven" encodes are `cwebp -size/-psnr` (byte/PSNR target, not perceptual) and the now-unmaintained Squoosh CLI auto-optimizer (Butteraugli target). **[H]**
- **Recommendation:** benchmark crustyimg against **rimage (1:1 tool)** and **sharp (ecosystem baseline)** as the two core contenders, with **image-actions** documented as the CI-integration pattern crustyimg should slot into. Gate *every* size/speed claim on **equal SSIMULACRA2**, never equal quality-number. **Build crustyimg `--features webp-lossy,avif`** for web-prep runs (see reality check) or you'll benchmark a lossless-only default.

---

## Repo reality check (from the live `jysf/crustyimg` repo)

The original brief said to treat crustyimg's headline features as "fixed and shipped." The public repo (README + `Cargo.toml`, accessed 2026-06-18) shows an **MVP still in flight** — which is exactly why benchmarking the *existing* tools first is the right sequencing. Concretely:

- **Pre-1.0, spec-driven, no releases yet.** Version `0.1.0`; MVP scope is `view / info / resize / shrink / thumbnail / strip`. The perceptual-target compression is wired in as a dependency for "auto-quality (SPEC-016)" — **in progress, not confirmed shipped**. No `diff --fail-under` or `responsive` command is visible in the public tree yet; treat those brief features as **roadmap**. **[H]**
- **Default build is lossless-WebP only.** Per `Cargo.toml`, lossy WebP encode sits behind an **off-by-default `webp-lossy` feature** (vendored libwebp via `cc` — described in-file as "the project's FIRST C dependency, strictly opt-in"). **To benchmark real web-prep output you must build `--features webp-lossy`.** This is the single most important operational correction. **[H]**
- **AVIF is genuinely pure-Rust** (off-by-default `avif` feature → `image/avif` → `ravif` → `rav1e`, no nasm/system libs). This *strengthens* the differentiation vs rimage, whose AVIF goes through the C `libavif` crate. **[H]**
- **Shares `fast_image_resize` and `kamadak-exif` with rimage.** Resize and EXIF handling will be near-identical between the two tools, so a crustyimg-vs-rimage benchmark isolates the **encoder** almost cleanly — tightening the comparison. **[H]**
- **Grades on the same metric it optimizes against.** crustyimg's auto-quality uses the pure-Rust `ssimulacra2` crate (BSD-2-Clause). If the benchmark *also* grades with that crate, crustyimg is teaching-to-the-test. **Grade with an independent SSIMULACRA2 build** (Cloudinary's C reference) + a second metric — now a control in §3.3/§3.6. **[H]**
- **License:** `Cargo.toml` declares `MIT OR Apache-2.0`; the README sidebar shows Apache-2.0 only. Minor internal inconsistency; the dual-license profile in the table stands. **[M]**
Source: <https://github.com/jysf/crustyimg> (README, `Cargo.toml`).

---

## Q1 — How teams actually optimize images in CI/CD (patterns catalog)

The landscape splits into five mechanisms. crustyimg targets the first three; the SaaS/CDN layer is a deliberately different shape.

### 1. PR-bot "optimize images in this PR" Actions

The dominant documented pattern. **`calibreapp/image-actions`** runs on `pull_request` filtered to image paths, recompresses changed images, **commits the optimized files back into the PR**, and posts a summary comment with per-file savings. It exposes fixed per-format quality knobs (`jpegQuality`, `pngQuality`, `webpQuality`, `avifQuality`) and a `compressOnly` mode for forks. Internally it uses **mozjpeg + libvips**. **[H]**
Sources: <https://github.com/calibreapp/image-actions>, <https://github.com/marketplace/actions/image-actions>, <https://calibreapp.com/blog/compress-images-in-prs>

This is the single most relevant prior art to crustyimg's intended CI slot. Note the shape difference: it's a Docker-based Action that *mutates the PR*, whereas crustyimg is a binary you call in a step (and which can also *fail* the build via `diff`).

### 2. pre-commit / git hooks

Well-documented, common for repos that keep optimized assets in-tree. Examples:
- **oxipng via `pre-commit`** — `adamchainz/pre-commit-oxipng` mirror, runs oxipng on every staged PNG before commit. **[H]** (<https://adamj.eu/tech/2022/01/20/optimize-your-pngs-with-oxipng-and-pre-commit/>)
- **imagemin in a pre-commit script** — community gists wire `imagemin` (jpegoptim/optipng/svgo plugins) into a hook. **[H]** (<https://github.com/imagemin/imagemin-cli>; folklore-level glue code, not a maintained product)
- **WordPress core** historically used a `grunt imagemin` task explicitly framed as a *pre-commit* tool. **[H]** (<https://core.trac.wordpress.org/ticket/25169>)

This is exactly where crustyimg's single-binary, zero-dependency story wins: a Rust binary in a `pre-commit` `language: system`/`rust` hook has no Node/`node_modules` or native-libvips bootstrapping.

### 3. Build-tool & static-site-generator image pipelines

The largest install base — and almost entirely **sharp/libvips** under the hood:
- **vite-imagetools** — compile-time transforms, "all image transformations are powered by sharp." **[H]** (<https://www.npmjs.com/package/vite-imagetools>)
- **vite-plugin-image-optimizer** — Sharp.js + SVGO at build time; you must install `sharp` yourself as a peer dep. **[H]** (<https://github.com/FatehAK/vite-plugin-image-optimizer>)
- **Astro** built-in image service uses sharp (`sharp().png()` encoder options, `<Image/>`/`<Picture/>`). **[H]** (<https://docs.astro.build/en/reference/configuration-reference/>)
- **Nuxt-imagetools / Astro ImageTools** — wrappers around sharp + imagetools. **[H]** (<https://github.com/floatingpixels/nuxt-imagetools>)
- **Next.js `<Image>`** automates format negotiation/responsive sizing; the actual optimization runs at build/runtime depending on platform. **[H]** (<https://uploadcare.com/blog/react-image-optimization-techniques/>, <https://vercel.com/docs/image-optimization>)

**Folklore-vs-documented note:** "sharp is the image engine of the JS web ecosystem" is *documented* — the plugins say so explicitly. What's *folklore* is the assumption that these pipelines meaningfully compress: several (e.g. LQIP/`imagetools`) mainly resize/convert and rely on encoder defaults, not perceptual optimization.

### 4. "Fail the build if an image regresses / is too large" gates

Two distinct things get conflated here:
- **Page-level byte budgets (common, documented):** **Lighthouse CI** assertions of the form `resource-summary:image:size` / `budget.json` `resourceType: "image"` fail the build when image bytes for a page exceed a ceiling. This is the mainstream "image too large → red build" gate. **[H]** (<https://googlechrome.github.io/lighthouse-ci/docs/configuration.html>, <https://unlighthouse.dev/learn-lighthouse/lighthouse-ci/budgets>)
  - Caveat teams hit constantly: Lighthouse-style assertions use **bytes**, `budget.json` uses **kilobytes** — a documented footgun. **[H]**
- **Per-image perceptual visual-regression gate (rare):** essentially *not* a packaged feature in the mainstream image-prep toolchain. Visual-regression tooling exists (screenshot diffing à la reg-suit/Percy-style products) but targets *rendered UI*, not *asset re-encode fidelity*. **[M]**

This gap is crustyimg's `diff --fail-under <SSIMULACRA2>`: a built-in, per-asset, perceptual CI gate. I found no equivalent first-class feature in any candidate tool. **[M, flagged: absence of evidence — treat as "no widely-documented equivalent," not proof none exists]**

### 5. SaaS / CDN-side prep (the contrast shape)

Runtime/edge transformation, *not* a CI binary: **Cloudinary**, **imgix**, **Vercel Image Optimization**, **Netlify** (Cloudinary build plugin / Netlify Image CDN). These auto-pick format (WebP/AVIF) by `Accept` header, auto-tune quality, resize via URL params, and cache at the edge. **[H]** (<https://vercel.com/docs/image-optimization>, <https://cloudinary.com/blog/automatically-optimize-images-with-cloudinarys-netlify-build-plugin>)
Notable: Netlify has been **stepping away from its own built-in asset optimization** and steering users to Cloudinary/its Image CDN. **[M]** (<https://cloudinary.com/guides/web-performance/mastering-image-optimization-with-netlify-and-cloudinary>)

These are out of scope for an apples-to-apples benchmark: they bundle storage, CDN, and per-request billing, and they optimize at request time. Use them only as a framing contrast ("crustyimg bakes the bytes at build time; CDNs bill per transform at run time").

---

## Q2 — Comparable tools

### Landscape table

| Tool | What it is | License | Lang / runtime | Install / dep footprint | Formats | Perceptual target? | CI / visual-regression gate? | How it's wired into CI |
|---|---|---|---|---|---|---|---|---|
| **crustyimg** (subject) | Outcome-driven web image CLI (MVP in progress) | MIT OR Apache-2.0 (Cargo.toml) | Rust (`image` crate, pure-Rust codecs) | **Single binary, zero system deps by default**; lossy-WebP feature adds vendored libwebp (C) | WebP: decode + **lossless** encode pure-Rust by default; **lossy WebP = opt-in `webp-lossy` (C)**; **AVIF = opt-in `avif`, pure-Rust** (ravif/rav1e) | **Planned** — SSIMULACRA2 target (SPEC-016, in flight) | **Planned** — `diff --fail-under` (roadmap; not yet in public tree) | Binary in CI/pre-commit; `responsive` snippet is roadmap |
| **rimage** | Rust optimization CLI "inspired by squoosh" | MIT OR Apache-2.0 **[H]** | Rust (codecs via C bindings: mozjpeg, libavif; ravif is pure-Rust) **[H/M]** | `cargo install` single binary **[H]** | JPEG/MozJPEG, PNG/OxiPNG, WebP, AVIF, JXL **[H]** | **No** — fixed `--quality`/quantization only **[H]** | **No** built-in gate **[H]** | CLI step / pre-commit (folklore; no first-party Action) |
| **sharp** | High-perf Node image lib (libvips) | Apache-2.0 **[H]** | Node (N-API); native libvips | npm install; ships **prebuilt native binaries** (~7MB+), no system libvips needed on common platforms; Node runtime required **[H]** | JPEG/PNG/WebP/AVIF/TIFF/GIF **[H]** | **No** — fixed quality/effort **[H]** | **No** built-in gate **[H]** | Library inside build-tool plugins (vite/astro/nuxt/next) **[H]** |
| **calibreapp/image-actions** | GitHub Action: compress PR images | (Action; wraps mozjpeg+libvips) **[H]** | Docker Action (Node) | GitHub-hosted Docker image; no local install **[H]** | JPG/PNG/WebP/AVIF **[H]** | **No** — fixed per-format quality **[H]** | Partial — mutates PR + comments; no perceptual *fail* gate **[H]** | `on: pull_request` paths filter; commits optimized bytes back **[H]** |
| **@squoosh/cli** | WASM codec CLI (Google) | Apache-2.0 **[H]** | Node + WebAssembly | npm/npx; **unmaintained since ~2022**, source/CLI removed upstream (community forks: frostoven, sbcinnovation) **[H]** | MozJPEG/WebP/OxiPNG/AVIF (WASM) **[H]** | **Partial** — experimental auto-optimizer targets a **Butteraugli** distance **[H]** | No | `npx @squoosh/cli` step (now risky due to abandonment) **[H]** |
| **ImageMagick** (`magick`) | General-purpose image Swiss-army | ImageMagick License (Apache-2.0-style) **[M]** | C; system tool | System package; many delegate libs (system deps) **[M]** | Very broad | No (fixed `-quality`) | No | `apt install` + CLI step; broad but heavy **[M]** |
| **libvips** (`vips`) | Fast low-memory image lib/CLI | LGPL-2.1+ **[M]** | C; system tool/lib | System package or vendored; native deps **[H]** | Broad (JPEG/PNG/WebP/AVIF/TIFF…) **[H]** | No | No | CLI/lib step; the engine sharp wraps **[H]** |
| **single-format optimizers** (`oxipng`, `pngquant`, `cwebp`, `avifenc`, `jpegoptim`, `mozjpeg`) | One-format encoders/optimizers | mixed (oxipng MIT; others BSD/own) **[M]** | mixed (oxipng = Rust single binary) **[H]** | per-tool binaries | one format each | **`cwebp -size/-psnr`** binary-searches passes to hit a **byte or PSNR** target (not perceptual) **[H]** | No | Called individually or via `imagemin`/`image_optim` wrappers **[H]** |
| **image_optim / ImageOptim-CLI** | Wrappers that fan out to many optimizers | mixed | Ruby / macOS GUI-driver | requires the underlying binaries (or macOS apps) **[M]** | lossless-ish, multi-format | No | No | dev-machine / CI lossless pass; ImageOptim-CLI is macOS-bound **[H]** | 
| **Cloudinary / imgix / Vercel / Netlify** | SaaS/CDN runtime transform | proprietary | hosted | account + per-transform billing | auto WebP/AVIF | auto-quality (`q_auto`, vendor-internal) **[M]** | n/a (runtime) | URL params / build plugin; **different shape** **[H]** |

### Finalist rationale

I scored each candidate on overlap with crustyimg's actual shape ("permissive CLI/library that prepares web images in a build/CI step, ideally with a perceptual target and a gate"):

**Finalist 1 — `rimage` (the fairest 1:1).** Same dual license (MIT OR Apache-2.0), same language (Rust), same delivery (single `cargo install` binary), same format ambitions (WebP/AVIF + JPEG/PNG/JXL). **It shares two crates with crustyimg — `fast_image_resize` and `kamadak-exif` — so resize and EXIF behavior are near-identical and the benchmark isolates the *encoder* almost cleanly.** A benchmark here isolates *encoder + driver quality*, with no runtime confound. **The honest gaps to surface:** (a) rimage has **no perceptual target** — it optimizes by fixed quality/quantization, so crustyimg's outcome-driven mode has *no direct counterpart* and you must construct an equivalent (see Q3); (b) rimage's "pure Rust" is partial — it binds the C `mozjpeg` and `libavif` crates (ravif/oxipng are Rust), whereas crustyimg's AVIF path is pure-Rust (ravif/rav1e) and its default build has zero C deps — a genuine differentiator worth measuring (binary size, `ldd` output, cold-install on a bare container). **[H]**

**Finalist 2 — `sharp` (the ecosystem baseline).** Not the same shape (Node + native libvips), but it's the encoder almost every JS build pipeline actually runs, so "how do we compare to what teams already ship" = "compare to sharp." It's fast (libvips), Apache-2.0, and widely benchmarked. **Honest gaps:** Node process startup overhead and native-binary install footprint must be measured *and reported separately* from steady-state encode throughput, or the comparison is unfair in *both* directions (unfair to sharp on per-invocation startup; unfair to crustyimg if you hide sharp's batch throughput). sharp has no perceptual target and no gate. **[H]**

**Finalist 3 (pattern, not encoder) — `calibreapp/image-actions`.** Include it to demonstrate *CI integration*, not to race encoders. It's the reference implementation of the PR-bot pattern crustyimg should support, and a great place to show crustyimg's added value (a *fail* gate + perceptual target the Action lacks). **[H]**

**Deliberately cut:** `@squoosh/cli` (abandoned upstream; would benchmark a dead tool — though its Butteraugli auto-optimizer is the best *prior art* for crustyimg's perceptual-target idea and worth citing conceptually); ImageMagick/libvips raw CLI (general-purpose, not web-prep-shaped — keep as sanity baselines only); single-format optimizers (not whole-pipeline comparable, but `cwebp -size`/`-psnr` is the right *byte-budget* prior art to cite); SaaS/CDN (different shape and billing model).

---

## Cloudinary: the incumbent of the idea (positioning)

Worth its own note, because Cloudinary is simultaneously a *contrast-shape competitor* and the *intellectual origin* of crustyimg's core thesis and metric.

- **What it is:** a SaaS image-and-video platform (upload/storage, media library, URL-based transformations, CDN delivery, video transcoding/ABR) used by many large brands. Its signature optimization features are **`f_auto`** (auto-pick format per browser) and **`q_auto`** (auto-pick quality). **[H]** (<https://cloudinary.com/documentation/image_optimization>)
- **`q_auto` *is* crustyimg's thesis, hosted.** Cloudinary's algorithm analyzes an image to find the best quality/encoding for the content and browser, automating the size-vs-quality trade-off on the fly "using perceptual metrics and heuristics." crustyimg is, in effect, "`q_auto` as an offline, build-time, dependency-free binary — no SaaS lock-in, no per-request billing." **[H]** (<https://cloudinary.com/documentation/image_optimization>)
- **They authored the metric crustyimg optimizes against.** Jon Sneyers — Cloudinary's Head of Image Research — **created SSIMULACRA 2** and co-created **JPEG XL** (with Google); he earlier created **FLIF**. **[H]** (<https://cloudinary.com/blog/the-latest-advancements-in-jpeg-xl>, <https://cloudinary.com/blog/innovator-spotlight-jpeg-xl-co-creator-jon-sneyers>)
- **CID22 caution.** Cloudinary's AI-enhanced `q_auto` was trained on **CID22**, their human-annotated compressed-image dataset — which is *also* one of the subjective datasets SSIMULACRA 2's weights were tuned on. It's a tempting corpus, but **keep the benchmark corpus independent of CID22** to avoid metric-circularity. **[M]** (<https://markets.financialcontent.com/dowtheoryletters/article/bizwire-2023-11-15-cloudinary-uses-ai-to-further-improve-image-quality-online-announces-jpeg-xl-support-for-apple-ecosystem>)
- **Positioning takeaway:** the sharpest one-liner for crustyimg is "perceptual auto-quality (the `q_auto` idea) without the service" — local, reproducible, free, CI-gateable. Cloudinary belongs in the report as the *why this matters* anchor, not as a head-to-head encoder target (different shape, request-time, billed).

---

## Q3 — Comparative benchmark design

**Governing rule:** every size and speed number is **gated on equal perceptual quality**. A smaller or faster file at a *different* SSIMULACRA2 score is not a result — it's a confound. We pin the **quality axis** and read off **bytes** and **time**.

### 3.1 Test corpus (license-clean)

Small, fixed, version-controlled set; all images CC0 / public-domain (e.g. from Unsplash-CC0/Wikimedia-PD/own captures — verify each license and record it in `CORPUS.md`):

- 3–4 **photographs** (varied: high-frequency foliage, smooth gradient sky, skin tones, low-light noise) — exercises lossy WebP/AVIF.
- 2 **PNG screenshots / UI** (flat color, text, sharp edges) — exercises lossless/near-lossless and palette paths.
- 1 **EXIF-oriented JPEG** (rotation flag set, GPS + metadata present) — exercises auto-orient + metadata-strip (`optimize` path).
- 1 image with an **alpha channel** (transparency correctness).
- Keep originals large enough (≥ 2–3 MP) that encode time is measurable and not startup-dominated.

### 3.2 Operations to compare

1. **Single-image `optimize`** (auto-orient + strip metadata + perceptual re-encode to a fixed SSIMULACRA2 target).
2. **Format conversion** (→WebP, →AVIF) at matched quality.
3. **Batch** (the whole corpus in one invocation, to expose per-process startup vs steady-state).
4. **Responsive-set generation** (N widths × M formats + the `<picture>`/srcset snippet).

### 3.3 Metrics

- **Output bytes** (the headline, gated on quality).
- **Wall-clock** (best-of-N, warm cache).
- **Peak RSS** (`/usr/bin/time -v` Max RSS, or `cgroup` peak).
- **SSIMULACRA2** of every output vs its original — the gate. Use the reference implementation (`cloudinary/ssimulacra2`) or the Rust binary `ssimulacra2_rs`; pin the exact version/commit, since v2.0→v2.1 retuned weights. **[H]** (<https://github.com/cloudinary/ssimulacra2>)
  - **Grader independence (control):** crustyimg's auto-quality optimizes against the Rust `ssimulacra2` crate, so **grade the benchmark with a *different* implementation — the Cloudinary C reference** — to avoid optimizer/grader collusion. Sanity-check that the two implementations agree within tolerance on a handful of images first. **[H]**
- **Install/footprint (reported, not raced):** cold install time on a bare container, on-disk size, `ldd`/dependency count, whether a language runtime is required.

### 3.4 The equal-quality protocol (the crux)

This is where "fair" is won or lost, because the contenders have *different control surfaces*.

- **crustyimg:** native — ask for the SSIMULACRA2 target directly; it binary-searches quality. Record the quality it lands on. **[native]**
- **rimage / sharp / cwebp / avifenc (fixed-quality tools):** they have *no* perceptual target, so **you build the search around them.** For each tool and each image, **sweep the quality parameter** (e.g. q ∈ {30…95}), measure SSIMULACRA2 at each, and **interpolate the byte count at the exact target score** (or pick the smallest file whose score ≥ target). This gives every tool the *same* quality footing without pretending q=80 means the same thing across encoders. Automate it; it's just a per-image bisection wrapper. **[H — this is the fairness keystone]**
- **Two complementary readouts** (report both; they answer different questions):
  1. **BD-rate / "bytes at equal SSIMULACRA2"** across a quality sweep — the quality-normalized size comparison.
  2. **"Single-shot default" reality check** — run each tool's *recommended default* once and report (bytes, score) as a scatter. This reflects what a team gets if they don't tune — crustyimg's outcome-driven default should land *on* the target by construction, while fixed-quality tools scatter; that scatter *is* the product argument, shown honestly.

### 3.5 Controls

- Pinned tool versions (crustyimg, rimage, sharp + bundled libvips, cwebp/avifenc, ssimulacra2) recorded in a lockfile/manifest; pin OS image and CPU (single fixed machine, document model, core count, RAM; disable turbo/boost variance where possible, or report it).
- **Warm cache, best-of-N** (e.g. N=5, report median + min; discard first run).
- **Single-threaded vs multi-threaded** stated explicitly per run — crustyimg/rimage/sharp all parallelize; either pin threads=1 for a clean per-image comparison *or* report both, but never compare a multi-threaded batch of one tool to a single-threaded run of another.
- Strip-metadata behavior normalized (ensure every tool actually strips, so byte deltas aren't just EXIF).
- Same target SSIMULACRA2 for all (suggest two operating points: **visually-lossless ≈ 90** and **high-but-lossy ≈ 80**, per Cloudinary's scale). **[H]**

### 3.6 Where a fair comparison is hard (and how to handle it honestly)

- **No perceptual target in the competitor** → handled by the quality-sweep + interpolation above. Do **not** compare crustyimg's "hit SSIMULACRA2 90" to rimage's "q=80" directly; that's the most likely way to produce a misleading win. **[H]**
- **Node startup overhead (sharp)** → separate **cold per-invocation** time from **warm batch** throughput. Report a "1 image" number *and* a "whole corpus in one process" number. sharp looks bad at the former, strong at the latter; crustyimg's single-binary cold start should win the former. Show both. **[H]**
- **Install footprint asymmetry** → report it as its own metric, don't fold it into encode time. crustyimg's zero-system-dep single binary vs sharp's prebuilt-native-binary download vs rimage's `cargo build` (or prebuilt release) are legitimately different stories; quantify (MB, install seconds on a clean container, runtime presence). **[H]**
- **Codec parity** → AVIF results depend heavily on encoder *and effort/speed* settings (rav1e/aom/SVT-AV1 differ). Match the *effort* level or report the speed/quality operating point; an AVIF "win" at effort 10 vs effort 4 is meaningless. **[M]**
- **Metric monoculture** → SSIMULACRA2 is the best single perceptual metric for medium/low fidelity, but for *visually-lossless* claims, cross-check with Butteraugli and report DSSIM too, so the headline doesn't hinge on one metric's quirks. **[M]** (<https://wiki.x266.mov/docs/metrics/SSIMULACRA2>)
- **Optimizer/grader collusion (crustyimg)** → crustyimg targets the `ssimulacra2` crate; grading on that same crate flatters it. Grade with the **independent C reference** (and report a Butteraugli/DSSIM cross-check). This is the difference between an honest result and a rigged one. **[H]**
- **`webp-lossy` build flag (crustyimg)** → the default build encodes WebP **losslessly only**; benchmarking it against lossy WebP from rimage/sharp/cwebp would be apples-to-oranges. Build crustyimg `--features webp-lossy,avif` and record the build flags alongside the version. **[H]**
- **image-actions isn't an encoder** → don't put it in the bytes/time race; benchmark it only on the *integration* axis (does the PR get smaller images committed back, with a comment) and use it to motivate crustyimg's missing-gate value-add. **[H]**

### 3.7 Suggested result artifacts

- A `bytes-at-equal-SSIMULACRA2` table (per image, per tool, at target 80 and 90).
- A quality-sweep scatter (x = SSIMULACRA2, y = bytes) per image with one line per tool — the single most honest visual.
- A startup-vs-batch bar chart (cold 1-image time vs warm per-image time in a batch).
- A footprint table (binary/install size, runtime required, system deps, cold-install seconds).
- A one-page "CI integration" matrix: which tool offers PR-bot mode, pre-commit, build-plugin, and a *perceptual fail gate* (only crustyimg in that last column, per current evidence).

---

## Confidence & caveats summary

- **High confidence:** tool identities, licenses, languages, and CI mechanisms for rimage, sharp, calibreapp/image-actions, Lighthouse CI budgets, SSIMULACRA2, cwebp target modes, squoosh-cli abandonment.
- **Medium confidence:** "no mainstream per-image perceptual CI gate exists" (absence of evidence, not evidence of absence); Netlify's retreat from built-in asset optimization; ImageMagick/libvips exact license strings; rimage's precise pure-vs-C codec split per release.
- **Guesses flagged inline** where noted. **The repo at github.com/jysf/crustyimg has now been accessed** (rev. 2); crustyimg capability statements are reconciled against its README and `Cargo.toml`. Net effect: the perceptual-target/`diff`/`responsive` features are **roadmap, not confirmed shipped**, and the default build is lossless-WebP-only (lossy WebP and AVIF are opt-in features). See *Repo reality check*.
- **Folklore vs documented:** "sharp powers the JS build ecosystem" and "pre-commit oxipng/imagemin" are documented; "teams gate image *quality* in CI" is largely folklore — what's documented is *byte-budget* gating (Lighthouse CI), not perceptual gating.
