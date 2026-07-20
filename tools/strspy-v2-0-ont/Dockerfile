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

RUN micromamba env create -y -n strspy_env -f setup/STRspy_2.0_env.yml \
    && micromamba clean -a -y

RUN unzip -oq db-v2/STRspy2.0-DB.zip -d db \
    && rm -rf db/__MACOSX \
    && find db -name '._*' -delete -o -name '.DS_Store' -delete

SHELL ["micromamba", "run", "-n", "strspy_env", "/bin/bash", "-c"]
RUN { \
      echo "SAMTOOLS=$(which samtools)"; \
      echo "BEDTOOLS=$(which bedtools)"; \
      echo "XATLAS=$(which xatlas)"; \
      echo "PARALLEL=$(which parallel)"; \
      echo "MINIMAP=$(which minimap2)"; \
      echo "SEQKIT=$(which seqkit)"; \
    } > config/ToolsConfig.txt && cat config/ToolsConfig.txt

ENTRYPOINT ["micromamba", "run", "-n", "strspy_env", "/bin/bash", "-lc"]