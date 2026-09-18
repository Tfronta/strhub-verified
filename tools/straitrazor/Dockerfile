# Proposed by STRhub Verified detect_recipe. The build IS the Installs gate.
FROM ubuntu:22.04
RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential cmake git ca-certificates autoconf automake libtool pkg-config zlib1g-dev libbz2-dev liblzma-dev libcurl4-openssl-dev libssl-dev libncurses-dev \
    && rm -rf /var/lib/apt/lists/*
ARG TOOL_REF=b618e9345ab40f348b504083ae8de2b39abb60fa
WORKDIR /opt
RUN git clone https://github.com/Ahhgust/STRaitRazor.git tool \
    && cd tool && git checkout "${TOOL_REF}" \
    && (git submodule update --init --recursive || true)
WORKDIR /opt/tool
RUN make
ENV PATH="/opt/tool:/opt/tool/bin:$PATH"
WORKDIR /work
ENTRYPOINT ["/bin/bash", "-lc"]
