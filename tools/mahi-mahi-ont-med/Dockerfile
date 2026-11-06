# Proposed by STRhub Verified detect_recipe. The build IS the Installs gate.
FROM python:3.11-slim
RUN apt-get update && apt-get install -y --no-install-recommends \
        git ca-certificates build-essential zlib1g-dev libbz2-dev liblzma-dev libcurl4-openssl-dev \
    && rm -rf /var/lib/apt/lists/*
RUN git config --global url."https://github.com/".insteadOf "git@github.com:" && git config --global url."https://".insteadOf "git://"
ARG TOOL_REF=861ea09ab44e88424c45b04d8018f3948a8fefbb
WORKDIR /opt
RUN git clone https://github.com/nanoporetech/mahi-mahi.git tool \
    && cd tool && git checkout "${TOOL_REF}" \
    && (git submodule update --init --recursive || true)
WORKDIR /opt/tool
RUN touch /tmp/.strhub_built
RUN pip install --no-cache-dir .
ENV PATH="/opt/tool:/opt/tool/bin:$PATH"
RUN echo 'export PATH=/opt/tool:/opt/tool/bin:$PATH' > /etc/profile.d/zz-strhub-path.sh
WORKDIR /work
ENTRYPOINT ["/bin/bash", "-lc"]
