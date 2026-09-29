# STRhub Verified: auditoría del 24 de septiembre de 2026

Alcance: motor `strhub-verified` en `main` (9300cf5), estado publicado en `gh-pages`, historial de CI y la ruta `/api/verify/trial` de `strhub-web`. No se modificó ni se despachó nada: todo lo que se ejecutó (pruebas de concepto, detección de recetas, `docker build`) corrió en el scratchpad de la sesión.

Pregunta de la auditoría: ¿el motor puede tomar el link de GitHub de una herramienta de genotipado de STR y decir si, tal como está en su repositorio, corre de principio a fin? No se evalúa exactitud.

---

## 1. Resumen

| Indicador | Valor |
|---|---|
| Tests del motor | 192 pasan, 1 saltado (la mitad PDF: CI no tiene `reportlab`) |
| Herramientas en el catálogo | 5 (8 slugs) |
| Corren "tal como está en el repositorio" | 3 de 5: HipSTR, STRaitRazor y GangSTR (este último solo con el plan B, ver P1-3) |
| Ensayos históricos con herramientas fuera de esas 5 | 1 (LongTR, 16/09): falló en Installs |
| Prueba de generalización: 18 herramientas de STR nuevas | 0 scripts caídos; 7 con un Dockerfile plausible; **0 con un comando de ejecución viable** |
| Hallazgos P0 (atestación falsa o seguridad) | 4, tres demostrados con prueba de concepto |

En una frase: **el motor es honesto y está bien construido, pero la detección de recetas está sobreajustada a las 5 herramientas con las que se desarrolló, y el cuello de botella de "cada herramienta es un mundo" no se resuelve agregando heurísticas una por una.** Antes de abrir el ensayo desde URL al público hay que cerrar cuatro agujeros que hoy permiten publicar una atestación falsa.

---

## 2. Cómo le va al motor con el catálogo actual

| Herramienta | Resultado tal como está | Qué pasó realmente | ¿Culpa de la herramienta? |
|---|---|---|---|
| HipSTR | Runs | Build con `make` desde el commit, comando del README | Sí corre |
| STRaitRazor | Runs | Build con `make`, config del kit resuelta por el dataset | Sí corre |
| GangSTR | Runs (verde) | **El commit fijado no compiló**; corrió la imagen `gymreklab/str-toolkit` (plan B) | Parcial: la etiqueta verde no lo dice (P1-3) |
| STRsearch | Fails: install | Se construyó el Dockerfile del repo con el clon como contexto; ese Dockerfile hace `COPY ./STRsearch` y espera la carpeta padre. El README documenta `docker pull anjing123/strsearch` | **No**: falso rojo del motor (P1-4) |
| STRspy | Fails: run | El wrapper sale con "please make sure you are in the same directory of STRspy"; el README muestra argumentos posicionales y el script espera `-i/-t`; además la config nunca se llena con los datos de STRhub | Mayormente sí (el README se contradice), pero expone un tipo de herramienta que el motor no maneja: las que se configuran por archivo y no por línea de comandos |

**LongTR, el único ensayo real con una herramienta nueva** (run 35126268475):
- Installs falló porque el Makefile clona `spoa` con `git@github.com:`, y la imagen no tiene ssh ni claves.
- Aunque hubiera compilado, la receta estaba mal en tres puntos:
  - dejó `--bams /data/in/input.bam,...` con los `,...` literales;
  - eligió el BAM de Illumina para una herramienta de lecturas largas, porque "initially designed for Illumina" ganó a "tailored for long reads";
  - dejó `--phased-bam`, que exige un BAM haplotipado.
- El informe publicó, entre los errores de la corrida, "The base image could not be pulled". Ese error viene del `docker run` de una imagen que nunca se construyó, no de la herramienta.
- El chequeo del README dio 5/5.

---

## 3. La prueba de generalización (18 herramientas nuevas)

Se corrió `detect_recipe.py` + `propose_manifest.py` sobre ExpansionHunter, TRGT, STRling, lobSTR, TRTools, LongTR, STRetch, straglr, tandem-genotypes, FDSTools, NanoRepeat, RepeatHMM, ExpansionHunterDenovo, lusSTR, STRique, strkit, vamos y MPSproto. Los resultados están en el scratchpad de la sesión (`generalization/`).

| Métrica | Valor |
|---|---|
| Scripts que se cayeron | 0 / 18 |
| Dockerfile plausible | 7 / 18 (de esos, 2 sin binarios de runtime: samtools, minimap2, LAST) |
| Comando de ejecución viable contra `/data/in`, `/data/ref/hg38.fa`, `/data/in/regions.bed` | **0 / 18** (10 sin comando, `true`; 8 con un comando equivocado) |
| Tipo de entrada bien inferido | ~9 / 18; 3 claramente mal (TRGT, LongTR, lusSTR) |
| Disponibles en Bioconda a la versión exacta probada | **10 / 17** |
| Veredicto probable | 14 "Could not be determined", 1 "Fails" por ssh (LongTR), 3 con riesgo de falso rojo |

Los huecos, por impacto (con referencias al código):

1. **Solo lee el README** (`detect_recipe.py:146-151`, `:836`). En 10 de 18 casos el uso está en `docs/`, la wiki, readthedocs o una web externa.
2. **El ranking de comandos premia "tiene entrada y salida" por encima de "invoca a la herramienta"** (`:418-419`). Así straglr recibió un pipeline de bedtools, tandem-genotypes su helper de merge, strkit su subcomando `convert` y FDSTools un `--help`. Además, un `\` seguido de `# comentario` rompe la unión de líneas (`:306`), y la prosa indentada se toma como comando.
3. **Archivos de build solo en la raíz** (`:46-60`, `:217-219`). No detecta `source/CMakeLists.txt`, `src/Makefile`, `configure.ac`, `*.nimble`, `DESCRIPTION` de R ni `install.sh`.
4. **Plantillas de toolchain finas** (`generate_dockerfile`, `:704-764`):
   - Rust 1.80, sin make, cmake ni clang (TRGT no compila; confirmado);
   - sin reescritura `git@github.com:` → `https://` (LongTR; confirmado);
   - `cmake .` en el árbol fuente, con el binario fuera del PATH;
   - pip no instala los binarios de runtime;
   - conda crea el entorno pero nunca construye la herramienta (STRling, STRetch).
5. **Sin consulta a Bioconda/BioContainers.** Solo se usa si el README trae `conda install -c bioconda`. `BIOCONDA_RE` además toma `requirements.txt` como nombre de paquete (vamos).
6. **Plataforma:** gana la primera mencionada (`:461`, `:555-559`); todo lo que no es ONT pasa a ser Illumina (PacBio HiFi incluido). No hay tipo de entrada VCF, fast5, MAF ni tabla de alelos.
7. **Reescritura a los mounts** (`propose_manifest.py:79-110`):
   - no colapsa `a.bam,b.bam,...`;
   - las rutas de BED solo se reescriben para BAM de Illumina, y `ont-bam-hg38` no tiene biblioteca de regiones;
   - deja placeholders `path/to/…`;
   - la búsqueda de configs llega a profundidad ≤1 (no encuentra el `.ini` de FDSTools ni el catálogo JSON de ExpansionHunter).
8. **Entradas propias de cada herramienta** que nadie describe de forma legible por máquina: catálogo de variantes (ExpansionHunter), definiciones de repeticiones (TRGT), índice de STR (STRling), motivos en Zenodo (vamos), referencia con señuelos (STRetch), manifiesto de cohorte (EHDN).

Los huecos 2, 3, 5, 7 y parte de 1 y 6 se arreglan con heurísticas. Los huecos 8 y el resto de 1 no: ahí hace falta otra cosa (sección 5).

---

## 4. Hallazgos de corrección y seguridad

### P0: se puede publicar una atestación falsa

| # | Hallazgo | Dónde | Evidencia |
|---|---|---|---|
| P0-1 | **Un ensayo desde la web publica en el catálogo y commitea a `main`, sin aprobación, y puede pisar la tarjeta de una herramienta real.** La web despacha `mode=trial` sin `publish`, que vale `'true'` por defecto; un ensayo desde URL es publicable. El slug sale del *nombre* del repo (`catalogue_slug`) y el alias va al commit más nuevo por la fecha que declara el propio commit. Un `evil-user/HipSTR` con un commit fechado en 2030 se vuelve el titular de la tarjeta `hipstr`. El rate-limit es en memoria por instancia serverless. El comentario de la ruta ("a trial publishes nothing") es falso hoy | `strhub-web/lib/verified/trial.ts:147-153`, `verify.yml:775-776, 838-842, 961`, `propose_manifest.py:129-143`, `publish_layout.py:197-212` | PoC sobre copia de gh-pages (`index.json` resultante con el repo ajeno como titular) |
| P0-2 | **La compuerta del ejemplo propio ignora el código de salida.** `--example-runs` se parsea y no se usa; `check_example` pasa con cualquier archivo no vacío que el wrapper copió; `verdict.py` cuenta `gates.example` como "Runs". Un comando que cae con rc 1 y deja un `.pyc` da "Runs as documented", verde. Con un Dockerfile del repo cuyo WORKDIR es `/`, un comando inexistente copia 497 archivos de `/sys` a `/data/out` y pasa | `report.py:859`, `check_example.py:44-63`, `verdict.py:203`, `prepare.py:297-299`, `propose_manifest.py:235` | PoC B y PoC W (Docker con los flags del motor) |
| P0-3 | **El veredicto dice "Runs" aunque la compuerta Runs falló**, si la salida pasa IO. `str8rzr` imprime una línea de uso a stdout, que va a `allsequences.txt`, y sale con 1: nivel `installs`, veredicto `runs`, badge verde y publicable. Un TSV con solo cabecera con dígitos o un JSON `{"error": …}` cuentan como un registro | `verdict.py:203`, `check_io.py:70-71` | PoC A con la receta commiteada de `tools/straitrazor` |
| P0-4 | **Si falla el checkout del SHA fijado, se construye la rama por defecto** y el informe atesta el SHA pedido. `clone && checkout && …` dentro de una lista `&&` no dispara `bash -e`. La web resuelve SHAs por la API, que acepta commits de forks que un `git clone` no trae | `verify.yml:511-513` | PoC en bash |

### P1: veredicto equivocado o frágil

1. **Las fallas de STRhub se publican como fallas de la herramienta.** Si falla la descarga de hg38 o el `apt`, se publica "stops: source not available". Un `toomanyrequests` de Docker Hub publica "stops at install" aunque `faults == ['strhub']`; `verdict.py:266-277` nunca mira `STRHUB_FIXABLE`. Lo mismo el "base image could not be pulled" de LongTR.
2. **Un timeout deja el contenedor corriendo**: bash es PID 1 y no hay `--init` ni `docker kill`. El contenedor sigue escribiendo en `/data/out` y compite con la pierna siguiente, y el timeout se informa como "exited with an error" (PoC en Docker).
3. **GangSTR dice "Runs as documented" en verde para 6ea9b2b, que no compiló.** La etiqueta ignora `fallback_used` (`certificate_text.py:161-165`) y la imagen del plan B probablemente no está fijada por digest.
4. **STRsearch es un falso rojo**: el contexto de build es el equivocado (debería ser la carpeta padre, o la imagen publicada que el README documenta), y se culpa al autor (`build_file_missing`). El comando propuesto, además, le pasa un BAM como `--fq1/--fq2` a `from_fastq`.
5. **El patrón de salida por defecto `**/*` falla con cualquier herramienta que escriba en un subdirectorio**: el primer match es el directorio (`propose_manifest.py:315`, `check_io.py:108`). PoC C.
6. **El chequeo de regresión del PR compara contra la corrida equivocada** (la curada del PR contra el alias, que ahora es el documentado): una regresión de STRsearch hasta `available` pasa (`verify.yml:908-917`).
7. **`set -e` se anula dentro de `publish()` llamado desde `if`** (`verify.yml:970-998`): si se cae `publish_layout.py` o `build_index.py`, se commitea y pushea igual. PoC en bash.
8. **Los comandos se aplanan a una línea** (`prepare.py:295, 323`): un `#` se come el resto, y en `tool | gzip` se pierde el código de salida de la herramienta.
9. **`diagnose_log`**: "WARNING: … does not exist (optional)" sigue siendo culpa del autor, y un OOM por nuestro tope de 6 GB no deja rastro en el log y queda como "Fails".
10. **Commits del bot directo a `main`**, sin checks: así se puso rojo `main` el 19/09 (run 35460507687). Sigue sin haber `concurrency:`; los push del commit de receta y de la limpieza de avisos solo emiten un warning si fallan.

### P2: deuda
- El golden-file del ejemplo nunca se compara: nadie trae `out/_expected/`.
- El esquema acepta `ref: main` y `repo: "not a uri"`; `git ls-remote` sin `--`.
- hg38 sin checksum, con el nombre de archivo como clave de caché.
- `reportlab` falta en el job `resolve`, así que la mitad PDF del test del certificado nunca corre en CI.
- `hipstr-y`, `strait-razor-forenseq` y `strait-razor-powerseq` nunca tendrán corrida documentada, porque `documented_refresh.py:48-57` deduplica por (repo, ref).
- Documentación desactualizada: el README dice "v0 scaffold", `datasets/README.md:28` atribuye el BAM a 1000 Genomes y `download.sh` apunta a rutas viejas. El `.git` pesa 330 MB y no hay LFS.

### Estado de la auditoría del 14/09
Arreglados: S3 (glob confinado), S4 (`|| true`), S5 (slugs de depuración), `$GITHUB_OUTPUT`, aviso de rechazo obsoleto, tests del motor en CI.
Parciales: S2 (flags de aislamiento sí; sigue como root, sin `--read-only` ni `--init`, y con token `contents: write` en el mismo job), S6 (bien en el catálogo; una tabla del formulario con solo `dna_column` sigue pasando), conteo TSV, reintentos de push, `diagnose_log`, PDF, esquema, polling y rate-limit web (en memoria).
**Reabierto: S1**, cerrado en `/submit` y reabierto por `/trial` (P0-1).
Abiertos: duplicación en `report.py`/`build_index.py`/`generate_pdf.py`, heredoc de `matrix.json`, documentación, LFS.

---

## 5. El problema de fondo: "cada herramienta es un mundo"

### Diagnóstico
Una herramienta necesita tres contratos para correr, y cada uno falla de una manera distinta:

| Contrato | Qué falla hoy | Naturaleza |
|---|---|---|
| **Entorno** (cómo se instala) | Plantillas por lenguaje que crecen de a una herramienta; build solo desde la raíz | Resoluble casi siempre **sin heurísticas propias**: el ecosistema bioinformático ya resolvió la instalación (Bioconda/BioContainers en 10 de 17) |
| **Invocación** (qué comando) | El README es la única fuente; el ranking y el parseo son frágiles | Es lectura de documentación en lenguaje natural: **no escala con regex** |
| **Entradas** (qué datos y archivos auxiliares) | 4 datasets; sin HiFi, VCF, fast5 ni catálogos propios de cada herramienta | Es un **límite de datos**, no de código: ninguna detección lo arregla |

Seguir sumando heurísticas a `detect_recipe.py` da rendimientos decrecientes: cada una que se agregó para las 5 herramientas del catálogo no generalizó a ninguna de las 18.

### Recomendación: separar lo que se infiere de lo que se lee y de lo que se provee

**1. Entorno: primero el paquete publicado, y la instalación como hecho separado.**
- Consultar Bioconda por nombre y versión del tag (api.anaconda.org) y usar la imagen de BioContainers (`quay.io/biocontainers/<tool>:<version>`), fijada por digest. Es lo que la mayoría de los usuarios realmente instala, y saca la instalación del camino en la mitad de los casos.
- Reportar dos hechos distintos en lugar de uno: "el commit fijado compila desde el código" y "el paquete publicado de esa versión corre". Hoy el plan B mezcla los dos en una sola etiqueta (P1-3).
- Definir una lista corta y explícita de **normalizaciones de entorno que no cuentan como parche** y registrarlas en el informe:
  - reescribir `git@github.com:` a `https://`;
  - fijar `--platform linux/amd64`;
  - construir desde el contexto padre cuando el Dockerfile del repo lo exige.

**2. Invocación: un agente acotado que lea la documentación, con cada decisión publicada como evidencia.**
- Lo que resuelve el hueco 1 y el 8 no es otra regex: es un bucle "leer docs, proponer, correr en ensayo, leer el error, corregir la receta", como ya planteaba la Fase 3 de la auditoría anterior (el autoconfig existe en la web, desconectado).
- Encaja con el modelo de instrumentos que ya existe:
  - la corrida **documentada** sigue siendo determinista y estricta, y es la que sostiene el badge;
  - el agente produce **automáticamente** la receta del capítulo "What STRhub had to do", con cada desvío como `recipe.workarounds` (qué, en lugar de qué, por qué).
- Hoy ese capítulo exige que alguien de STRhub escriba la receta a mano. Con el agente se escribe solo, y es exactamente la lista de recomendaciones para el autor.
- Reglas para el agente: solo toca archivos de receta, nunca el código de la herramienta; como máximo N intentos; cada fuente citada con línea y commit (como ya hace `evidence`).

**3. Entradas: un registro de assets por herramienta y más tipos de datos.**
- Extender la biblioteca de regiones (que ya genera formatos HipSTR, GangSTR y STRsearch) a más formatos de catálogo: JSON de ExpansionHunter, BED de TRGT, straglr, y regiones para `ont-bam-hg38`.
- Agregar datasets cuando haya fuente abierta: PacBio HiFi (GIAB HG002), ONT FASTQ y un VCF de ejemplo para herramientas de post-proceso como TRTools.
- Lo que no tenga dato abierto se declara fuera de alcance, con esa razón.

**4. Un peldaño intermedio "Starts".**
- Entre Installs y Runs: el binario arranca (`--help` o `--version` sale con 0).
- Le da al revisor un dato útil aunque el comando no se pueda determinar ("instala y arranca; el README no dice cómo correrlo").
- Separa los fallos de instalación de los de invocación, que hoy se mezclan.

**5. Aceptar la escala real.**
- Herramientas forenses de STR hay decenas, no miles. Con Bioconda + agente + un registro de assets, un catálogo de 20 a 30 herramientas bien cubiertas es alcanzable.
- La receta en el repo del mantenedor (`strhub-verified.yml`) sigue siendo la vía de más calidad, y además resuelve la prueba de control que necesita P0-1.

---

## 6. Orden sugerido

| Fase | Qué | Por qué primero |
|---|---|---|
| **0 (antes de exponer `/trial`)** | P0-1: ensayos de la web con `publish=false`, o publicar solo si el repo coincide con el `source.repo` de la tarjeta existente y el slug no está tomado por otro repo. P0-2 y P0-3: exigir `runs`/`example-runs == success` para contar salida. P0-4: `set -e` real, o comprobar `git rev-parse HEAD == TOOL_REF`. P1-1: fallas de STRhub nunca publicables | Hoy se puede publicar algo falso |
| **1 (1 semana)** | Veredictos: etiqueta del plan B, contexto de build de STRsearch, `--init` + `docker kill` en timeout, `**/*` solo archivos, `set -e` en deploy, `concurrency:`, `reportlab` en CI | Corrige tarjetas que hoy están mal |
| **2 (2 semanas)** | Heurísticas baratas: Bioconda/BioContainers, build files en subdirectorios, normalizaciones de entorno, ranking de comandos, colapso de `a,b,...`, `docs/*.md` enlazados desde el README, plataforma PacBio. Volver a correr las 18 del set de generalización como **benchmark fijo** (snapshots en `harness/testdata/repos/`), con métricas de "Dockerfile construye" y "comando viable" | Mide el progreso con algo que no sea el catálogo sobre el que se ajustó |
| **3 (3 a 4 semanas)** | Agente de invocación que produce la receta y los `workarounds` automáticamente; peldaño "Starts"; registro de assets y datasets HiFi, ONT FASTQ y VCF | Es lo que realmente ataca "cada herramienta es un mundo" |

La métrica que vale la pena seguir no es cuántos tests pasan sino **qué fracción del set de generalización llega a Installs, a Starts y a Runs**. Hoy, de 18: 7 Dockerfiles plausibles (2 confirmados compilando en amd64, 2 confirmados fallando) y 0 comandos viables.
