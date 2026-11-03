# Panel de STRs médicos

> **ESTADO (2026-11-03):** completo en `main` en los dos repos para las tres
> plataformas: Illumina (`NA12878`), PacBio HiFi (`HG002`) y ONT (`HG00113`).

**Objetivo:** que una herramienta que no genotipa STRs forenses (ExpansionHunter,
TRGT, STRipy, LongTR, Straglr...) pueda verificarse corriendo el catálogo que trae,
tal como lo documenta. Hasta ahora su catálogo caía fuera de los slices forenses y
la propuesta terminaba en `loci_outside_panel`.

## Qué loci (criterio de literatura)

Un locus entra si STRchive lo lista **y** al menos 3 de los 4 catálogos por defecto
de herramientas médicas lo traen. "Más comunes" quiere decir "lo que las
herramientas genotipan de fábrica", que es justo lo que una corrida sin enmiendas
necesita encontrar con lecturas.

| Fuente | Commit |
|---|---|
| STRchive `data/STRchive-loci.json` (coordenadas, motivo, copias) | `e964fa8` |
| ExpansionHunter `variant_catalog/hg38/variant_catalog.json` | `7ff9aa5` |
| TRGT `repeats/pathogenic_repeats.hg38.bed` | `3d10c75` |
| STRipy pipeline `catalog.json` (GitLab) | `e8265c5` |
| str-analysis `variant_catalog_without_offtargets.GRCh38.json` | `57a6ac8` |

Resultado: **51 loci**. Los 31 que están en los cuatro catálogos son exactamente el
catálogo de ExpansionHunter; los otros 20 están en TRGT, STRipy y str-analysis.
Cubre el 100% de EH y el 91% de TRGT. Todo lo genera
`harness/build_medical_candidates.py`; el cruce completo de los 82 loci de STRchive
queda en `datasets/illumina-bam-hg38-med/catalog_crosswalk.tsv`.

## Regla de solapamiento (opción B)

Antes, un BED con **cualquier** intervalo fuera del panel se rechazaba. Un catálogo
médico trae decenas de loci y el slice no los tiene todos, así que habría que
recortarlo: eso es enmendar el procedimiento documentado.

Ahora el BED se rechaza solo si alcanza menos de `min_loci` loci del panel. Los
intervalos fuera del panel se listan (`out_of_panel`) y el reporte dice cuántos
quedaron sin evaluar. Cambió en `harness/validate_bed.py` y en su espejo web
`lib/verified/validate-regions.ts`; el contrato de parseo (`bed_cases.json`) no
cambia.

## Datasets

| Tipo | Datos | Panel |
|---|---|---|
| `illumina-bam-hg38-med` | `illumina_slices/NA12878.medical.bam` (±1 kb) | medido con `build_panel.py` |
| `pacbio-hifi-bam-hg38-med` | `pacbio_slices/HG002.hifi.medical.bam` (±10 kb) | derivado del de Illumina |
| `ont-bam-hg38-med` | `ont_slices/HG00113.medical.bam` (±1 kb) | derivado del de Illumina |

Mismas muestras y fuentes que los slices forenses: nada nuevo que licenciar. Tipos
aparte, no BAM ampliados, para que los reportes ya publicados sigan apuntando a los
mismos datos. `download_medical.sh` los reconstruye.

## Ruteo automático y fallback en ejecución

1. **En la propuesta (`propose_manifest.medical_panel_for`):** si los loci del archivo
   que el comando documentado lee (del repositorio) no tocan el panel forense pero sí el
   médico, la propuesta usa directamente el slice `-med` de la misma plataforma.
2. **En la corrida (`prepare.py` + `verify.yml`):** si una herramienta no expone un
   archivo de catálogo legible estáticamente y entra con un BAM forense
   (`illumina-bam-hg38`, `pacbio-hifi-bam-hg38` u `ont-bam-hg38`), `prepare.py` prepara
   también `work/in_external_med`. Si el comando documentado falla o devuelve 0 registros
   sobre el BAM forense, `verify.yml` reintenta exactamente el mismo comando sobre el
   slice `-med` y lo promueve si produce salida válida. Una herramienta forense nunca se
   mueve.

## Qué no se hace

- Los loci médicos no entran al catálogo forense de STRhub: sin páginas de marcador,
  sin frecuencias, sin rangos patogénicos.
- Correr en estos slices prueba ejecución reproducible, **no** validación clínica ni
  diagnóstica. NA12878 y HG002 no tienen expansiones patogénicas conocidas.

## Espacio

El repo pesaba ~0,40 GB en GitHub antes de esto; el piloto suma unos 60 MB. Cada
regeneración de un slice queda en la historia para siempre. Para ONT (archivo >50 MiB)
conviene evaluar assets de un GitHub Release antes de sumarlo.
