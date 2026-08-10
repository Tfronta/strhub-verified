FROM ubuntu:22.04
RUN apt-get update && apt-get install -y --no-install-recommends \
        git ca-certificates python3 python3-numpy \
        samtools bedtools seqtk \
    && rm -rf /var/lib/apt/lists/*

ARG STRSEARCH_REF=c70179b3b175adc82a7314409af06900b3861d61
WORKDIR /opt
RUN git clone https://github.com/AnJingwd/STRsearch.git STRsearch \
    && cd STRsearch && git checkout "${STRSEARCH_REF}"

# conf.py se publica con marcadores "YOUR PATH/...". command -v en vez de which
# a proposito: con set -e, un binario ausente aborta el build en vez de escribir
# una ruta vacia que solo fallaria a mitad de la corrida.
RUN set -eux; \
    S="$(command -v samtools)"; B="$(command -v bamToFastq)"; Q="$(command -v seqtk)"; \
    printf '[softwares]\nmybwa="bwa"\nmysamtools="%s"\nmybamToFastq="%s"\nmyseqtk="%s"\nmyusearch="usearch"\n' \
      "$S" "$B" "$Q" > /opt/STRsearch/conf.py; \
    cat /opt/STRsearch/conf.py

# Import smoke test: convierte una dependencia que falte en un fallo de Installs,
# que es donde pertenece, y no en un fallo de Runs.
RUN python3 -c "import sys; sys.path.insert(0,'/opt/STRsearch'); import scripts.STR_search, scripts.STR_parse"

ENTRYPOINT ["/bin/bash", "-lc"]