# Proposed by STRhub Verified detect_recipe. The build IS the Installs gate.
FROM ubuntu:22.04
RUN apt-get update && apt-get install -y --no-install-recommends \
        git ca-certificates curl unzip xz-utils bzip2 libgomp1 zlib1g libbz2-1.0 liblzma5 libcurl4 \
    && rm -rf /var/lib/apt/lists/*
ARG TOOL_REF=b21c6217eeaef9a080205932fe29f730dc00e31f
WORKDIR /opt
RUN git clone https://github.com/PacificBiosciences/trgt.git tool \
    && cd tool && git checkout "${TOOL_REF}" \
    && (git submodule update --init --recursive || true)
WORKDIR /opt/tool
RUN touch /tmp/.strhub_built
RUN mkdir -p /opt/release && curl -fsSL -o /tmp/asset "https://github.com/PacificBiosciences/trgt/releases/download/v5.1.0/trgt-v5.1.0-x86_64-unknown-linux-gnu.tar.gz" && echo "2ab9ddb0f52516ea92de66c336c151dc3bd5bb22494e2b9dcb8bffa9eb710f63  /tmp/asset" | sha256sum -c - \
    && tar -xzf /tmp/asset -C /opt/release && rm /tmp/asset
RUN find /opt/release -type f -perm -u+x ! -name '*.so*' -exec ln -sf {} /usr/local/bin/ \;
ENV PATH="/opt/tool:/opt/tool/bin:$PATH"
RUN echo 'export PATH=/opt/tool:/opt/tool/bin:$PATH' > /etc/profile.d/zz-strhub-path.sh
WORKDIR /work
ENTRYPOINT ["/bin/bash", "-lc"]
