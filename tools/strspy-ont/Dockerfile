# Proposed by STRhub Verified detect_recipe. The build IS the Installs gate.
FROM mambaorg/micromamba:1.5.8
USER root
RUN apt-get update && apt-get install -y --no-install-recommends \
        git ca-certificates build-essential \
    && rm -rf /var/lib/apt/lists/*
RUN git config --global url."https://github.com/".insteadOf "git@github.com:" && git config --global url."https://".insteadOf "git://"
ARG TOOL_REF=dafdee7e7e5672c8dc732e8577dbe153f53a12f5
WORKDIR /opt
RUN git clone https://github.com/unique379r/strspy.git tool \
    && cd tool && git checkout "${TOOL_REF}" \
    && (git submodule update --init --recursive || true)
WORKDIR /opt/tool
RUN touch /tmp/.strhub_built
RUN micromamba create -y -n tool -f setup/STRspy_2.0_env.yml && micromamba clean -a -y
ENV ENV_NAME=tool
ENV PATH="/opt/conda/envs/tool/bin:/opt/tool:$PATH"
RUN echo 'export PATH=/opt/conda/envs/tool/bin:/opt/tool:$PATH; export CONDA_PREFIX=/opt/conda/envs/tool' > /etc/profile.d/zz-strhub-path.sh
WORKDIR /work
ENTRYPOINT ["micromamba", "run", "-n", "tool", "/bin/bash", "-lc"]
