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

# --- system encoders (single-format lane) --------------------------------
# webp -> cwebp ; libavif-bin -> avifenc ; pngquant ; build tools for the rest
# (python3 comes from the base image — do NOT apt-install it or you'd shadow
# 3.14 with Debian's system python).
RUN apt-get update && apt-get install -y --no-install-recommends \
        ca-certificates curl git build-essential pkg-config cmake nasm \
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
# The JPEG competitor must be MozJPEG's `cjpeg`, NOT libjpeg-turbo's (they
# differ in output size). Build it from source at a pinned tag, or install a
# package that provides MozJPEG's cjpeg, and ensure it wins on PATH.
ARG MOZJPEG_VERSION=v4.1.5    # TODO: pin
RUN echo "TODO: build github.com/mozilla/mozjpeg@${MOZJPEG_VERSION} and install cjpeg to /usr/local/bin"

# --- SSIMULACRA2: the INDEPENDENT C reference (primary grader) -------------
# Build the Cloudinary C reference at a pinned commit; this is the grader the
# benchmark trusts (NOT ssimulacra2_rs, which crustyimg optimises against).
ARG SSIMULACRA2_COMMIT=main  # TODO: pin to an exact commit SHA
RUN git clone https://github.com/cloudinary/ssimulacra2 /tmp/ss2 \
 && cd /tmp/ss2 && git checkout ${SSIMULACRA2_COMMIT} \
 && echo "TODO: build per upstream README (libjxl dep) and install as /usr/local/bin/ssimulacra2"

# Optional second SSIMULACRA2 impl for the agreement cross-check only.
# RUN cargo install ssimulacra2_rs --version <pin>

WORKDIR /work
COPY . /work
ENTRYPOINT ["python3", "-m", "bench"]
CMD ["check"]
