# Built to the requirements STRsearch DECLARES, not to the versions its own
# Dockerfile freezes. Its README asks for "bwa (v1.7 or higher)", "samtools
# (v1.7 or higher)", "bamToFastq (v2.17.0 or higher)" and "seqtk (v1.2 or
# higher)"; its Dockerfile pins those exact numbers on ubuntu:16.04 and Miniconda
# 4.3.31, a coherent stack for the day it was written that no longer resolves.
# Apt on 22.04 satisfies every stated floor.
FROM ubuntu:22.04

RUN apt-get update && apt-get install -y --no-install-recommends \
        git ca-certificates python3 python3-numpy \
        samtools bedtools seqtk \
    && rm -rf /var/lib/apt/lists/*

ARG TOOL_REF=c70179b3b175adc82a7314409af06900b3861d61
WORKDIR /opt
RUN git clone https://github.com/AnJingwd/STRsearch.git STRsearch \
    && cd STRsearch && git checkout "${TOOL_REF}"

# conf.py ships with "YOUR PATH/..." placeholders and the tool reads it on every
# run. command -v rather than which, so with set -e a missing binary fails the
# build instead of writing an empty path that only breaks mid-run. usearch is
# licensed and unobtainable here; it is reached only by --assemble_pairs, which
# this run does not use, and conf_parse only eval()s the value.
RUN set -eux; \
    S="$(command -v samtools)"; B="$(command -v bamToFastq)"; Q="$(command -v seqtk)"; \
    printf '[softwares]\nmybwa="bwa"\nmysamtools="%s"\nmybamToFastq="%s"\nmyseqtk="%s"\nmyusearch="usearch"\n' \
      "$S" "$B" "$Q" > /opt/STRsearch/conf.py; \
    cat /opt/STRsearch/conf.py

# Import check at build time, so a missing dependency fails Installs — where it
# belongs — rather than Runs.
RUN python3 -c "import sys; sys.path.insert(0,'/opt/STRsearch'); import scripts.STR_search, scripts.STR_parse"

ENTRYPOINT ["/bin/bash", "-lc"]
