# STRspy 2.0 environment for STRhub Verified.
# This Dockerfile encodes the workarounds for the reproducibility hazards the
# Installs gate would otherwise hit on a naive fresh clone. Each workaround is
# itself a finding the attestation should record.

FROM mambaorg/micromamba:1.5.8

USER root
RUN apt-get update && apt-get install -y --no-install-recommends \
        git ca-certificates unzip \
    && rm -rf /var/lib/apt/lists/*

ARG STRSPY_REF=dafdee7e7e5672c8dc732e8577dbe153f53a12f5

WORKDIR /opt
RUN git clone --branch STRspy2.0 --single-branch https://github.com/unique379r/strspy.git strspy \
    && cd strspy && git checkout "${STRSPY_REF}"

WORKDIR /opt/strspy

# HAZARD 1 workaround: the documented installer (setup/STRspy_2.0.setup.sh) is
# INTERACTIVE (`read ans`) and hangs in CI. We bypass it and create the env directly.
# HAZARD 2 note: env yml pins only python=3.7.7; the bioconda tools are UNPINNED,
# so this build is non-reproducible by construction — recorded as a finding.
RUN micromamba env create -y -n strspy_env -f setup/STRspy_2.0_env.yml \
    && micromamba clean -a -y

# HAZARD 3 workaround: the bundled DB zip carries macOS cruft (__MACOSX, .DS_Store,
# ._* files) that pollutes the per-locus fasta/bed globs. Unzip and strip it.
RUN unzip -oq db-v2/STRspy2.0-DB.zip -d db \
    && rm -rf db/__MACOSX \
    && find db -name '._*' -delete -o -name '.DS_Store' -delete

# HAZARD 4 workaround: generate ToolsConfig.txt non-interactively, INSIDE the env,
# and with the name the run command expects (the repo's GenerateToolConfig writes
# 'UserToolsConfig.txt' and the README renames it by hand — we make it deterministic).
SHELL ["micromamba", "run", "-n", "strspy_env", "/bin/bash", "-c"]
RUN { \
      echo "SAMTOOLS=$(which samtools)"; \
      echo "BEDTOOLS=$(which bedtools)"; \
      echo "XATLAS=$(which xatlas)"; \
      echo "PARALLEL=$(which parallel)"; \
      echo "MINIMAP=$(which minimap2)"; \
      echo "SEQKIT=$(which seqkit)"; \
    } > config/ToolsConfig.txt && cat config/ToolsConfig.txt

# The harness runs the command from the manifest inside this env.
ENTRYPOINT ["micromamba", "run", "-n", "strspy_env", "/bin/bash", "-lc"]
