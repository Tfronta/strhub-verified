# Proposed by STRhub Verified detect_recipe. The build IS the Installs gate.
FROM ubuntu:22.04
RUN apt-get update && apt-get install -y --no-install-recommends \
        git ca-certificates curl unzip xz-utils bzip2 libgomp1 zlib1g libbz2-1.0 liblzma5 libcurl4 \
    && rm -rf /var/lib/apt/lists/*
ARG TOOL_REF=9f5db1d4ab72016b2d93330b9792842d71582622
WORKDIR /opt
RUN git clone https://github.com/Illumina/ExpansionHunter.git tool \
    && cd tool && git checkout "${TOOL_REF}" \
    && (git submodule update --init --recursive || true)
WORKDIR /opt/tool
RUN touch /tmp/.strhub_built
RUN mkdir -p /opt/release && curl -fsSL -o /tmp/asset "https://github.com/Illumina/ExpansionHunter/releases/download/v5.0.0/ExpansionHunter-v5.0.0-linux_x86_64.tar.gz" \
    && tar -xzf /tmp/asset -C /opt/release && rm /tmp/asset
RUN find /opt/release -type f -perm -u+x ! -name '*.so*' -exec ln -sf {} /usr/local/bin/ \;
ENV PATH="/opt/tool:/opt/tool/bin:$PATH"
RUN echo 'export PATH=/opt/tool:/opt/tool/bin:$PATH' > /etc/profile.d/zz-strhub-path.sh
WORKDIR /work
ENTRYPOINT ["/bin/bash", "-lc"]
