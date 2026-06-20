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
# Pin the toolchain so codegen doesn't drift between rebuilds.
ARG RUST_VERSION=1.79.0      # TODO: pin to your standard
RUN curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs \
      | sh -s -- -y --default-toolchain ${RUST_VERSION} --profile minimal

# rimage / oxipng (pin exact versions — see tools.lock.md)
ARG RIMAGE_VERSION=0.11.0    # TODO
ARG OXIPNG_VERSION=9.1.2     # TODO
RUN cargo install rimage --version ${RIMAGE_VERSION} \
 && cargo install oxipng --version ${OXIPNG_VERSION}

# --- sharp-cli (ecosystem baseline) ---------------------------------------
ARG SHARP_CLI_VERSION=4.2.0  # TODO
RUN npm install -g sharp-cli@${SHARP_CLI_VERSION}

# --- MozJPEG (the JPEG lane) -----------------------------------------------
# Build MozJPEG's `cjpeg` from a pinned tag with PNG input enabled. Installed
# under /opt/mozjpeg; its bin goes FIRST on PATH so this cjpeg wins over any
# libjpeg-turbo cjpeg (they differ in output size — MozJPEG is the competitor).
ARG MOZJPEG_VERSION=v4.1.5
RUN git clone --depth 1 --branch ${MOZJPEG_VERSION} \
        https://github.com/mozilla/mozjpeg /tmp/mozjpeg \
 && cmake -S /tmp/mozjpeg -B /tmp/mozjpeg/build -G Ninja \
        -DCMAKE_BUILD_TYPE=Release -DCMAKE_INSTALL_PREFIX=/opt/mozjpeg \
        -DPNG_SUPPORTED=TRUE -DENABLE_SHARED=FALSE -DENABLE_STATIC=TRUE \
 && cmake --build /tmp/mozjpeg/build \
 && cmake --install /tmp/mozjpeg/build \
 && rm -rf /tmp/mozjpeg
ENV PATH=/opt/mozjpeg/bin:$PATH

# --- SSIMULACRA2: the INDEPENDENT C reference (primary grader) -------------
# The canonical SSIMULACRA2 C implementation lives in libjxl (Jon Sneyers'
# tools/ssimulacra2 → the `ssimulacra2` binary). This is the grader the
# benchmark trusts — NOT ssimulacra2_rs, which crustyimg optimises against.
# Pin a released tag; --recursive vendors the third_party submodules.
ARG LIBJXL_VERSION=v0.11.1
RUN git clone --depth 1 --recursive --branch ${LIBJXL_VERSION} \
        https://github.com/libjxl/libjxl /tmp/libjxl \
 && cmake -S /tmp/libjxl -B /tmp/libjxl/build -G Ninja \
        -DCMAKE_BUILD_TYPE=Release \
        -DBUILD_TESTING=OFF \
        -DJPEGXL_ENABLE_BENCHMARK=OFF \
        -DJPEGXL_ENABLE_EXAMPLES=OFF \
        -DJPEGXL_ENABLE_DOXYGEN=OFF \
        -DJPEGXL_ENABLE_MANPAGES=OFF \
 && cmake --build /tmp/libjxl/build --target ssimulacra2 \
 && install -m755 /tmp/libjxl/build/tools/ssimulacra2 /usr/local/bin/ssimulacra2 \
 && rm -rf /tmp/libjxl

# Second SSIMULACRA2 impl (Rust) — used ONLY for the agreement cross-check,
# never to grade crustyimg numbers.
ARG SSIMULACRA2_RS_VERSION=0.5.0
RUN cargo install ssimulacra2_rs --version ${SSIMULACRA2_RS_VERSION} || \
    cargo install ssimulacra2_rs

# Sanity: list what resolved (handy when validating a fresh build).
RUN cjpeg -version 2>&1 | head -1 || true; \
    ssimulacra2 2>&1 | head -1 || true

WORKDIR /work
COPY . /work
ENTRYPOINT ["python3", "-m", "bench"]
CMD ["check"]
