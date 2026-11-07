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
RUN cp str8rzr /usr/local/bin/

# Sanity check at BUILD time so a missing binary fails Installs, not Runs.
# No `|| true`: that mask let a build that never produced str8rzr pass Installs.
RUN command -v str8rzr

WORKDIR /work
ENTRYPOINT ["/bin/bash", "-lc"]
