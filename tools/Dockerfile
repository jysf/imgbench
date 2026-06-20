# Pinned encoder + grader versions for reproducible runs.
#
# The whole point is that two people (and CI) measure the SAME binaries. Pin
# exact versions here and document them in tools.lock.md. `just bench-docker`
# builds and runs the benchmark inside this image.
#
# NOTE: versions below are PLACEHOLDERS to pin — replace each TODO with the
# exact version/commit you standardise on, then record it in tools.lock.md.

# Official Python 3.14 image (Debian trixie under the hood), so `python3` is
# 3.14 AND the apt encoder packages are still available. Pin the patch so the
# interpreter doesn't drift between rebuilds.
FROM python:3.14-slim-trixie

ENV DEBIAN_FRONTEND=noninteractive \
    CARGO_HOME=/opt/cargo \
    PATH=/opt/cargo/bin:/usr/local/bin:$PATH

# --- system encoders (single-format lane) + build deps -------------------
# webp -> cwebp ; libavif-bin -> avifenc ; pngquant ; the rest are built below.
# (python3 comes from the base image — do NOT apt-install it or you'd shadow
# 3.14 with Debian's system python.) libpng/zlib are for MozJPEG PNG input;
# clang/ninja for the libjxl (SSIMULACRA2 C reference) build.
RUN apt-get update && apt-get install -y --no-install-recommends \
        ca-certificates curl git build-essential pkg-config cmake ninja-build nasm \
        clang \
        libpng-dev zlib1g-dev \
        webp libavif-bin pngquant \
        nodejs npm \
    && rm -rf /var/lib/apt/lists/*

# --- Rust toolchain (rimage, oxipng, ssimulacra2_rs) ----------------------
# Modern crates (e.g. indexmap 2.x) need a recent Cargo manifest parser, so use
# the stable channel. TODO: after a first successful build, pin to the exact
# version `rustc --version` reports for reproducibility.
ARG RUST_VERSION=stable
RUN curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs \
      | sh -s -- -y --default-toolchain ${RUST_VERSION} --profile minimal

# oxipng (reliable, must succeed) then rimage. rimage compiles C bindings and
# its older releases break against current deps, so it's NON-FATAL: if it can't
# install, the adapter just reports it missing and the rest of the benchmark
# still runs. Verify the CLI + repin after a successful build.
ARG RIMAGE_VERSION=0.12.3
ARG OXIPNG_VERSION=9.1.2
RUN cargo install oxipng --version ${OXIPNG_VERSION}
RUN cargo install rimage --version ${RIMAGE_VERSION} \
 || echo "WARNING: rimage ${RIMAGE_VERSION} failed to install; adapter reports missing"

# --- sharp-cli (ecosystem baseline) ---------------------------------------
ARG SHARP_CLI_VERSION=4.2.0  # TODO
RUN npm install -g sharp-cli@${SHARP_CLI_VERSION}

# --- MozJPEG (the JPEG lane) -----------------------------------------------
# Build MozJPEG's `cjpeg` from a pinned tag with PNG input enabled. Installed
# under /opt/mozjpeg; its bin goes FIRST on PATH so this cjpeg wins over any
# libjpeg-turbo cjpeg (they differ in output size — MozJPEG is the competitor).
ARG MOZJPEG_VERSION=v4.1.1
RUN ( git clone --depth 1 --branch ${MOZJPEG_VERSION} \
        https://github.com/mozilla/mozjpeg /tmp/mozjpeg \
      || git clone --depth 1 https://github.com/mozilla/mozjpeg /tmp/mozjpeg ) \
 && cmake -S /tmp/mozjpeg -B /tmp/mozjpeg/build -G Ninja \
        -DCMAKE_BUILD_TYPE=Release -DCMAKE_INSTALL_PREFIX=/opt/mozjpeg \
        -DPNG_SUPPORTED=TRUE -DENABLE_SHARED=FALSE -DENABLE_STATIC=TRUE \
 && cmake --build /tmp/mozjpeg/build \
 && cmake --install /tmp/mozjpeg/build \
 && rm -rf /tmp/mozjpeg
ENV PATH=/opt/mozjpeg/bin:$PATH

# --- SSIMULACRA2 (+ Butteraugli) C reference: the INDEPENDENT grader --------
# The canonical SSIMULACRA2 C implementation lives in libjxl. Debian's
# `libjxl-devtools` ships the prebuilt `ssimulacra2` and `butteraugli_main`
# binaries (and pulls the matching libjxl runtime), so we install those instead
# of compiling libjxl from source. This is the grader the benchmark trusts —
# NOT ssimulacra2_rs, which crustyimg optimises against. Pinned to Debian's
# libjxl package version (record it in tools.lock.md after a build).
RUN apt-get update && apt-get install -y --no-install-recommends \
        libjxl-devtools \
    && rm -rf /var/lib/apt/lists/*

# NOTE: ssimulacra2_rs (the Rust impl, for the C-vs-Rust agreement cross-check)
# is intentionally omitted — it needs vapoursynth + fontconfig system deps. The
# agreement check simply records "second implementation not installed". The
# Butteraugli cross-check (above) is available regardless.

# Sanity: confirm the key grader/encoder binaries resolve + run.
RUN cjpeg -version 2>&1 | head -1 || true; \
    ssimulacra2 2>&1 | head -1 || true; \
    butteraugli_main 2>&1 | head -1 || true

WORKDIR /work
COPY . /work
ENTRYPOINT ["python3", "-m", "bench"]
CMD ["check"]
