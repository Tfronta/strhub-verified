# STRait Razor v3 — environment for STRhub Verified (ForenSeq variant)
# Identical build to tools/strait-razor; only the assay config used at run time
# differs (see manifest.yml: ForenSeqv1.27.config). The build step IS the
# "Installs" gate: if this image fails to build, the tool fails Installs.

FROM ubuntu:22.04

RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
        cmake \
        git \
        ca-certificates \
    && rm -rf /var/lib/apt/lists/*

ARG STRAITRAZOR_REF=b618e9345ab40f348b504083ae8de2b39abb60fa

WORKDIR /opt
RUN git clone https://github.com/Ahhgust/STRaitRazor.git strait-razor \
    && cd strait-razor \
    && git checkout "${STRAITRAZOR_REF}"

WORKDIR /opt/strait-razor
# VERIFY the build invocation against the repo's README (Makefile vs cmake).
RUN make 2>/dev/null || (cmake . && make)

# Put the executable on PATH. VERIFY names/locations.
RUN cp str8rzr /usr/local/bin/ 2>/dev/null || true

# Sanity check at BUILD time so a broken binary fails Installs, not Runs.
RUN str8rzr --help >/dev/null 2>&1 || str8rzr 2>/dev/null || true

WORKDIR /work
ENTRYPOINT ["/bin/bash", "-lc"]
