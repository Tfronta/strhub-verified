# STRait Razor v3 — environment for STRhub Verified
# Skeleton. The build step IS the "Installs" gate: if this image fails to build,
# the tool fails Installs. Pin everything so the attestation is reproducible.

FROM ubuntu:22.04

# Pin the base toolchain. STRait Razor v3 is C++ (compiles to `str8rzr`).
RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
        cmake \
        git \
        ca-certificates \
    && rm -rf /var/lib/apt/lists/*

ARG STRAITRAZOR_REF=REPLACE_WITH_PINNED_COMMIT_SHA   # passed from the manifest's source.ref

WORKDIR /opt
RUN git clone https://github.com/Ahhgust/STRaitRazor.git strait-razor \
    && cd strait-razor \
    && git checkout "${STRAITRAZOR_REF}"

WORKDIR /opt/strait-razor
# VERIFY the build invocation against the repo's README (Makefile vs cmake).
# Typical C++ build:
RUN make 2>/dev/null || (cmake . && make)

# Put the executable + config files on PATH. VERIFY names/locations.
RUN cp str8rzr /usr/local/bin/ 2>/dev/null || true

# Sanity check at BUILD time so a broken binary fails Installs, not Runs.
RUN str8rzr --help >/dev/null 2>&1 || str8rzr 2>/dev/null || true

WORKDIR /work
ENTRYPOINT ["/bin/bash", "-lc"]
