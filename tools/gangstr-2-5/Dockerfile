FROM continuumio/miniconda3:24.11.1-0
RUN conda install -c bioconda -c conda-forge gangstr=2.5.0 --yes && \
    conda clean -afy && \
    GangSTR --help 2>&1 | head -2
ENV PATH="/opt/conda/bin:$PATH"
WORKDIR /work
