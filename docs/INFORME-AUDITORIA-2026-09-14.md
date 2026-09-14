# STRhub Verified: auditoría exhaustiva y plan de próximos pasos

Fecha: 14 de septiembre de 2026. Alcance: los dos repos (`strhub-verified`, motor en Python + GitHub Actions; `strhub-web`, sitio Next.js), la carpeta raíz `Verified/`, el estado publicado en `gh-pages` y el sitio en producción `strhub.app/verified`. Solo lectura: no se modificó ningún archivo.

---

## 1. Resumen ejecutivo

STRhub Verified es una atestación automática, fechada y anclada a un commit de que una herramienta forense de STR instala, corre de punta a punta y produce salida plausible en un entorno limpio. El motor es GitHub Actions + Docker; el registro es el repo; la evidencia es el log de CI; el catálogo es estático en `gh-pages` y lo renderiza la web.

Estado real hoy:

| Indicador | Valor |
|---|---|
| Sitio | vivo (HTTP 200), oculto (`VERIFIED_PUBLIC = false`, sin menú, `noindex`) |
| Herramientas reales | 5 (HipSTR, STRaitRazor, STRsearch, GangSTR, STRspy) |
| Slugs publicados en gh-pages | 16 (más 2 directorios locales sin publicar) |
| Commits en el motor | 234, de los cuales 131 son automáticos del formulario |
| Actividad pico | 47 commits el 14 de agosto: 16 reenvíos del mismo STRsearch en un día |
| Tests web | 93 pasan, `tsc` limpio |
| Tests del motor | ninguno en `main` (solo el selftest de `pick_tools.py`) |
| Cron mensual | corrió el 1 de septiembre, 5 herramientas, verde |
| Peso del motor | `.git` de 331 MB; 229 MB de BAM sin Git LFS |

Veredicto en una frase: el núcleo del motor es sólido y su honestidad al reportar es poco común, pero el producto falla en el borde donde el autor tiene que configurar su herramienta, y ese borde es justamente lo que tenía que ser automático.

Tres conclusiones que ordenan todo lo demás:

1. **No existe un ciclo de prueba sin publicar.** Cada intento de configuración es un commit a `main`, una corrida de CI de varios minutos y una atestación pública. Depurar equivale a ensuciar el registro. La evidencia está en el catálogo: 6 de los 16 slugs publicados son iteraciones de depuración de STRaitRazor (`straitrazor-v1-0` a `-5`) con un comando mal concatenado, y quedaron en línea como si fueran veredictos sobre la herramienta.
2. **El formulario pide al autor resolver tres problemas a ciegas**: el entorno (Dockerfile), el contrato de ejecución (comando, tipo de dato, referencia, BED) y el contrato de salida (qué archivo, qué columnas). Son 53 controles en un componente de 3.377 líneas. Cada herramienta es un mundo porque el formulario intenta describir ese mundo completo antes de haber corrido nada.
3. **Hay un agujero de seguridad que impide hacerlo público tal cual.** La aprobación de un repo es por URL y la URL es entrada no autenticada: cualquiera puede enviar un Dockerfile arbitrario diciendo que es HipSTR, ejecutarlo en el runner y publicar una atestación falsa con el nombre del mantenedor real.

La sección 4 responde a la pregunta de fondo ("cada tool es un mundo, ¿cómo lo hago viable?") con un rediseño concreto para los tres públicos: dueños, revisores de papers y usuarios que no logran correr la tool. La sección 5 lo convierte en fases.

---

## 2. Lo que está bien

- **La honestidad del reporte es el activo principal.** Escalera contigua de niveles, alcance explícito en cada artefacto, badge que baja a amarillo cuando el log reporta errores aunque las compuertas pasen (`report.py:845-853`). El caso STRspy es un ejemplo público y reproducible de una herramienta que "corre" pero falla en 9 loci CODIS, con los loci nombrados en la página.
- **Modelo formal de "de quién es la culpa".** `diagnose_log.py` separa `AUTHOR_FIXABLE` de `HARNESS_INCOMPATIBLE` con un `assert` de disjunción; `manual_eligibility()` es una política mecánica y explícita; los pre-flights abortan sin publicar badge cuando la falla es del pipeline y no del autor (`verify.yml:159-171`).
- **Defensa contra inyección en CI bien pensada.** Todo valor del manifiesto llega a `run:` por `env:` y nunca por `${{ }}`; el comando del autor viaja como un único argumento al `ENTRYPOINT bash -lc`; el deploy solo desde `main` y nunca desde PR; `set -o pipefail` con `tee` para que un build fallido no se registre como éxito.
- **Selección inteligente de qué verificar.** `pick_tools.py` verifica lo que el PR toca, limita los barridos, refresca por antigüedad en el cron y trae su propio selftest que corre antes de decidir.
- **Panel de loci derivado de evidencia.** `build_panel.py` genera `loci.bed` desde la cobertura real del BAM con piso de profundidad, con `--check` para detectar drift, y documenta la exclusión razonada de DYS385a.
- **Web: validación estricta y privacidad.** Zod `.strict()` en todo el payload, slug derivado y saneado, IP nunca persistida (hash salado), secreto JWT sin valor por defecto (falla cerrado), cabeceras de seguridad, paridad i18n en/es/pt garantizada por test (349 claves usadas, 0 faltantes), elegibilidad del nivel 2 recalculada del lado del servidor.
- **Comentarios de diseño de calidad excepcional** en ambos repos: cada decisión explica el fallo que la motivó. Esto vale mucho para auditoría externa y para quien herede el código.
- **Autoconfig con modelo** (`/api/verify/autoconfig`): la intuición correcta de que la configuración debe inferirse del repo, con `confidence` y `evidence` por campo. Hoy está detrás de un flag y desconectada del ciclo de prueba; en la sección 4 se propone dónde encaja.

---

## 3. Lo que está mal

### P0. Seguridad y credibilidad (resolver antes de hacer público)

| # | Hallazgo | Dónde | Evidencia |
|---|---|---|---|
| S1 | **Aprobación por URL de repo, sin prueba de control.** Si el slug es nuevo y el repo ya fue aprobado una vez, el envío se commitea y despacha sin humano. Con `docker.mode: provided` el Dockerfile es arbitrario. Resultado: ejecución de código en el runner y atestación falsificable para HipSTR, STRaitRazor o STRsearch en cualquier ref. | `strhub-web/app/api/verify/submit/route.ts:224-246` | `isRepoApproved(sub.source.repo)` es la única barrera; `approvedRepos` tiene 3 repos. |
| S2 | **`docker run` sin aislamiento.** Sin `--network none`, `--memory`, `--cpus`, `--pids-limit`, `--cap-drop`, corre como root. La "detección de red en runtime" es un regex post-mortem. El job tiene `contents: write` a nivel workflow. | `strhub-verified/.github/workflows/verify.yml:40-42, 317-322, 353-358` | confirmado por grep: ningún flag de aislamiento. |
| S3 | **El glob de `outputs[].path` no está confinado a `/data/out`.** `path: "../in_own/*"` hace pasar IO y Content sin que la herramienta produzca nada. | `harness/check_io.py:52`, `harness/check_content.py:197`, esquema sin `pattern` | PoC ejecutada por el auditor: `passed: true`. |
| S4 | **`\|\| true` y `\| head` enmascaran fallos de build** en 5 líneas de 4 Dockerfiles. El build es la compuerta Installs: un binario ausente pasa en verde. | `tools/gangstr-v2-5`, `strait-razor-PowerSeqv2.31` (×2), `strait-razor-ForenSeqv1.27` (×2), `gangstr-2-5` | |
| S5 | **6 atestaciones de depuración publicadas** como veredictos: `straitrazor-v1-0-2/3/4` en `installs` por un comando sin espacio (`…config/data/in/sample.fastq>`), `-5` en `io`, más `gangstr-2-5` con `ref: v2.5` (tag móvil, viola el esquema). | gh-pages `index.json`, `tools/straitrazor-v1-0*/manifest.yml` | 18 directorios para 5 herramientas. |
| S6 | **Nivel "Plausible output" otorgado sin comprobar loci.** `hipstr-b2033bf` y `-y` declaran solo `dna_column`; el único check es "REF es ACGTN", trivialmente cierto en cualquier VCF. El texto del nivel promete "loci forenses reconocibles". | `harness/check_content.py:179`, `report.py:43-45` | ambos publicados en `content`. |

### P1. Corrección y robustez

Motor:
- **Conteo TSV/CSV incorrecto** (`check_io.py:38-41`): siempre resta 1 asumiendo cabecera y no ignora líneas vacías. Un archivo con dos saltos de línea pasa `min_records: 1`; un TSV de una fila sin cabecera falla.
- **Reintentos de push que fallan en silencio** (`verify.yml:235-237, 541-543`): tras 3 fallos el bucle termina con `sleep 3` (rc 0) y el step queda verde. Con 5 legs en paralelo (cron) el `index.json` se regenera en cada uno y el rebase conflictúa; no hay `concurrency:`.
- **Aviso de rechazo obsoleto persiste**: `state/rejections/strsearch-c70179b.json` sigue en `main` aunque una corrida posterior publicó el slug en `content`. Nada lo borra.
- **Falsos positivos en `diagnose_log.py`** que degradan el badge: `usage: … --bams: not found` → `cmd_not_found`; `An invalid option --x will be rejected` → `bad_option`; `WARNING: file … does not exist (optional)` → error.
- **Pierna "own" con datos de STRhub cuenta como fixture del autor** (`gangstr-v2-5`): la escalera usa esa pierna y el reporte no añade la nota "no sample from the repository was used".
- **PDF**: afirma incondicionalmente "This tool does not include its own demo or test data" (`generate_pdf.py:621-622`) incluso para STRaitRazor con fixture propio; genera un PDF "0/5, Not run" sin error si falta el JSON; `.title()` sobre nombres ("hipstr" → "Hipstr").
- **Esquema laxo**: acepta `ref: main`, `repo: "not a uri"` (sin `FormatChecker`), `timeout_minutes: 100000`; `reproduces_own_example` está en esquema y README pero nadie lo implementa.
- **Inyección en `$GITHUB_OUTPUT`** (`prepare.py:301-321`): solo `cmd` se sanea; un `\n` en `repo` o `dataset_name` inyecta claves. `git ls-remote "$TOOL_REPO"` sin `--` y sin comprobar el `ref`.
- **Stash sin resolver** en `strhub-verified` con un fan-out de `assets/` en `prepare.py` y un arreglo del Dockerfile de `hipstr-v0-7` (zlib, PATH). Decidir si aplica o se descarta.

Web:
- **Polling sin tope** (`verified-submit-form.tsx:1392-1409`): cada 6 s para siempre; `findRunByDispatchId` mira solo 40 runs, y el cron mensual los desplaza.
- **`/api/verify/status` y `/repo-context` sin rate-limit**: hasta 7 llamadas a GitHub por request con el token de instalación compartido (5.000/h). Un bucle trivial deja a todos en 502. `lib/rate-limit.ts` existe y no se usa ahí.
- **`store.save()` traga el 409** de conflicto de sha (`store.ts:143-146`): dos envíos concurrentes pierden un registro y el límite por IP/repo no cuenta. `updateSubmissionStatus` devuelve `true` siempre: el 404 de `reject` es código muerto.
- **Admin**: JWT de 30 días en `localStorage` sin revocación; usuario por defecto `admin`; rate-limit de login en memoria de proceso (decorativo en serverless); `test-email` devuelve 8 caracteres de la clave de Resend.
- **HTML sin escapar en el mail al admin** (`lib/email.ts:36,47,51`): `toolName` libre permite un botón "Aprobar" falso.
- **`.env.local.save`** en disco con todos los secretos (no commiteado, pero es una copia con otro `JWT_SECRET`): borrar y rotar.
- **Tipos vs motor**: `gates` incluye `"none"` que el motor no emite; `report.regions` existe en el JSON y no en el tipo.
- `newDispatchId` usa `Math.random` y ese id es la única credencial para consultar `/status`.

### P2. Deuda y mantenibilidad

- **Espejos motor ↔ web declarados "keep in sync" sin test cruzado**: `validate-regions.ts` ↔ `validate_bed.py`; `diagnostics.ts` ↔ `diagnose_log.py`; `detect-output.ts` ↔ `check_content.py`; `INPUT_TYPES.supportedLoci` ↔ `datasets/*/loci.bed`; flags de compatibilidad en tres lugares; `verified-pdf.tsx` reimplementa el PDF del motor; `bed-cases.json` solo existe en la web.
- **Duplicación dentro del motor**: `_summary_md` y `_summary_html` (~200 líneas cada uno); `LABELS/COLOR/MEANING` triplicados en `report.py`, `build_index.py`, `generate_pdf.py`; `PANEL_MAP` duplica `datasets/index.json`; `dataset.yml` duplica `index.json` y nadie lo lee; la lógica de `matrix.json` vive en un heredoc dentro del YAML.
- **Sin tests del motor** para las compuertas que sostienen la atestación. La rama remota `fix/bed-header-and-shared-cases` trae `test_validate_bed.py` y no está mergeada.
- **Tests web solo de lógica pura**: nada cubre `manifest.ts` (YAML propio, Dockerfile), `submission.ts`, `store.ts`, `github.ts` ni ninguna ruta. S1 no lo habría detectado nada.
- **Componentes enormes**: formulario 3.377 líneas, detalle 1.070, PDF 788. `generate_pdf.py` 1.220 líneas con un logo base64 de 52 KB en una línea.
- **Código muerto**: `hasPriorSubmission`, `pathExists`, `remoteFixtureSchema`, `isCommitSha`, `contentStats`, `/api/admin/content*` (store en memoria "para preview").
- **Documentación desactualizada**: README del motor dice "v0 scaffold" y anuncia una compuerta que no existe; `datasets/README.md` atribuye `illumina-bam-hg38` a "1000 Genomes 30x" cuando es GIAB NA12878 300x (error de procedencia en un proyecto de atestación); README del dataset Y dice 15 loci, son 14; `download.sh` apunta a `Validacion-Softwares-NGS/` (ruta vieja) y a un `regions.bed` inexistente; ni README ni RUNBOOK mencionan que `state/` y `autoconfig/` son estado de runtime escrito por CI y por la web.
- **Peso**: 229 MB de BAM como blobs planos, sin `.gitattributes`; `lfs: true` en el workflow no hace nada; 329 MiB de objetos sueltos sin empaquetar. `sample.fastq` de ForenSeq es md5-idéntico al del dataset (3,8 MB duplicados).
- **`package.json`**: `name: "my-v0-project"`; `next 14` con `@next/third-parties ^16` y `@types/react 18` con `react 19`.
- **Ramas**: 9 locales ya mergeadas en el motor y 9 en la web sin borrar; `TEMP-strpop/`, `plan.md`, `docs/next-15-upgrade-plan.md` trackeados; `docs/foundations/` sin trackear.

### P3. Higiene de la carpeta raíz (no es repo git)

| Archivo | Tamaño | Qué hacer |
|---|---|---|
| `hg38.hipstr_reference.bed` | 78 MB | borrar o mover a `~/genomes/` |
| `HG001.…300x.bam.bai`, `NA12878.final.cram.crai` | 11 MB + 1,3 MB | borrar (índices de BAM que no están acá) |
| `strhub-verified.zip` | 21 KB | borrar (snapshot del 14 de junio) |
| `strhub-web-BACKUP-pre-ip-purge.bundle` | 860 KB | **conservar** en `archive/` (respaldo pre-purga de IP) |
| `regionH.bed`, `REGIONSY.bed`, `STRsearchY.bed` | <1 KB | borrar (md5-idénticos a los `assets/regions.bed` ya commiteados) |
| `strsearch-regions-hg38.bed` | 2 KB | borrar (borrador anterior) |
| `build_strsearch_bed.py` | 7 KB | mover a `strhub-verified/harness/` y parametrizar las rutas absolutas |
| `datasets/` (raíz) | 56 KB | borrar (generación anterior, superada por `str_candidates.bed`) |
| `node_modules/`, `package-lock.json` | vacíos | borrar |
| `manifest.yml`, `README.md` (raíz) | 4 KB | mover a `strhub-verified/` como ejemplo, o borrar (duplicados) |
| `PLAN-ISFG-Nomenclature-Compliance.md` | 14 KB | mover a `strhub-web/docs/` (es del módulo mix-profiles, no de Verified) |
| `PLAN-STRhub-Verified.md`, `PLAN-Owner-Provided-BED.md`, `SESION-…handoff.md` | 65 KB | mover a `strhub-verified/docs/` |

---

## 4. El problema de fondo: "cada tool es un mundo"

### 4.1 Diagnóstico

El objetivo original era "pegar el link del repo, marcar unas opciones y que GitHub Actions diga si la herramienta funciona de punta a punta". Lo que hay es un formulario de 53 controles que pide, antes de correr nada:

1. **Entorno**: cómo se construye (Dockerfile propio o generado desde lenguaje + comando de build).
2. **Contrato de ejecución**: tipo de dato, dónde está el fixture, comando exacto con `/data/in` y `/data/out`, referencia hg38, BED de regiones, timeout.
3. **Contrato de salida**: qué archivo, qué formato, qué columna es locus, cuál es ADN, cuáles son conteos, cuántos loci esperar.

Y lo pide a ciegas. No hay forma de probar sin publicar. El costo de cada iteración es: commit a `main` del motor, corrida de CI de 1 a 7 minutos, atestación pública, y un slug nuevo si cambió la versión. Por eso STRsearch necesitó 16 envíos en una tarde y STRaitRazor dejó 6 cadáveres publicados. Si a la autora del sistema le cuesta, a un mantenedor externo le va a costar más y no va a insistir 16 veces.

Hay un segundo factor: **la población es chica**. Herramientas de genotipado de STR con uso forense hay unas decenas en el mundo, no miles. Un formulario universal de autoservicio está optimizado para un problema (escala) que este proyecto no tiene. Y el tercer factor es el decisivo: dos de los tres públicos a los que apunta (revisores de papers y usuarios a los que no les sale) no manejan código. A ellos no se les puede pedir una receta. Ver 4.2.

### 4.2 Tres públicos, una sola regla

| Público | Qué sabe | Qué necesita | Qué puede aportar |
|---|---|---|---|
| **1. Dueño de la tool** | su herramienta | un badge citable para el paper, que siga vigente | receta, datos de ejemplo, tiempo para iterar |
| **2. Revisor de un paper** | el paper y la URL del repo, no maneja código | saber si instala y corre como dice el paper, antes de aprobar, sin escribir nada y sin esperar aprobación de nadie | URL y el tag que cita el paper |
| **3. Usuario al que no le sale** | su error, no sabe si es la tool o su entorno | un punto de comparación: "en un entorno limpio esto corre así" o "esto falla también acá" | URL y su log |

La regla que sale de la tabla: **la receta la produce STRhub, no quien envía.** Para los públicos 2 y 3 no hay alternativa, no manejan código. Para el dueño es opcional refinarla. Todo lo que hoy pide el formulario (Dockerfile, comando, columnas) pasa a ser algo que el sistema intenta deducir y, si no puede, lo dice como hallazgo.

### 4.3 El modelo: seguir el README como un extraño

Un **ensayo** automático que hace exactamente lo que haría un revisor con tiempo infinito: leer el README, instalar como dice, correr el ejemplo que dice con los datos de ejemplo del repo, y ver si sale lo que dice. Cada hueco es un hallazgo sobre la documentación, no una falla del sistema. Esto es la compuerta `reproduces_own_example`, que está en el esquema desde el inicio y nunca se implementó: es la compuerta correcta para revisores.

Cuatro veredictos posibles, todos legibles por alguien que no programa:

| Veredicto | Significa | Qué entrega |
|---|---|---|
| **Corre** | instala y el ejemplo documentado produce la salida documentada | el Dockerfile y el comando exactos para reproducirlo en cualquier máquina |
| **Falla** | no instala, o instala y el ejemplo falla | el error, clasificado, y quién puede arreglarlo (el autor) |
| **No se pudo determinar** | el README no dice cómo instalar / cuál es el comando / dónde están los datos de ejemplo / qué salida esperar | la lista precisa de huecos; para un revisor esto es un hallazgo de revisión, no un fallo de STRhub |
| **Fuera de alcance** | necesita GPU, interfaz gráfica, licencia, otro sistema operativo | ruta al nivel 2 (ya implementado como `HARNESS_INCOMPATIBLE`) |

Los ensayos son **efímeros y privados**: un link compartible por 30 días que no entra al catálogo. Publicar en el catálogo requiere al dueño (receta en su repo, punto 4.5) o la vía de tercero que ya existe con su atribución. Como un ensayo no publica nada bajo el nombre de nadie, no necesita esperar aprobación de administrador; sí necesita el aislamiento de Docker y el rate-limit de la Fase 0.

La segunda capa, opcional y a cargo del dueño o de un tercero, es la que ya existe: dataset externo de STRhub y compuerta Content.

### 4.4 Tres entradas, un motor

- **"Verificar mi tool"** (dueño): URL + ref, ensayo, y si está verde aparece "Publicar". Receta refinable en un panel avanzado, o versionada en su repo. Resultado: badge citable.
- **"Revisar para un paper"** (revisor): URL + tag del paper. Ensayo, informe privado con link para compartir con el editor. Opción de congelarlo como atestación de tercero, que ya existe.
- **"¿Es mi entorno o la tool?"** (usuario): primero busca en el catálogo. Si la tool ya está verificada, muestra el entorno exacto, el comando y el log para comparar. Si no está, ensayo. Además: "pegá tu error", que pasa el log del usuario por las mismas reglas de `diagnose_log` y le dice a qué categoría pertenece y si STRhub vio lo mismo.

El formulario queda en un campo obligatorio (URL), un ref opcional (por defecto el último release) y "quién sos". Todo lo demás es avanzado y solo para dueños.

### 4.5 Cómo STRhub arma la receta sola

1. **Detección determinista** en el repo al ref: Dockerfile, `environment.yml`, `requirements.txt`, `pyproject.toml`, `Makefile` o `CMakeLists.txt`, paquete en Bioconda con ese nombre, binarios en releases. Datos de ejemplo: carpetas `example/`, `test/`, `data/` con `.fastq`, `.bam` o `.vcf`. Comando: bloques de código del README que invocan el binario.
2. **El modelo** (el autoconfig que ya existe) rellena lo que la detección no resolvió, citando la evidencia, como hace hoy.
3. **Bucle**: ensayo, log, `diagnose_log`, corrección de la receta, hasta 5 veces. Solo se tocan archivos de receta, nunca el código de la tool. La computación es gratis; el humano ve solo la receta que funcionó.
4. Si tras los intentos no corre por falta de información, el veredicto es "no se pudo determinar" con la lista de huecos. Si no corre por un error de la tool, es "Falla" con el error.

Lo que se conserva de la propuesta anterior, ahora acotado al dueño: receta en el repo de la tool (`strhub-verified.yml`, que además prueba control y cierra S1 para publicaciones) y runner local para iterar en minutos. Ninguno de los dos se le pide a un revisor ni a un usuario.

### 4.6 Los datos: la biblioteca de STRhub es la pieza central

Los repos casi nunca traen datos de prueba, y con razón: un BAM de ejemplo pesa, y el autor no tiene un dato open-access a mano. Por eso hoy el formulario pregunta "¿qué tipo de dato toma tu tool?" y STRhub pone el dato. Eso es correcto y se mantiene. Lo que cambia es **quién elige el tipo** y **qué más viaja con el dato**.

**Quién elige.** El tipo de entrada se infiere del repo, como el resto de la receta: extensiones y flags en el README y en el código (`.bam`, `--fastq`, `pysam`, `samtools`, `minimap2`, `hg38`, `nanopore`), el lenguaje de los ejemplos, y el modelo cuando la señal es débil. Si la inferencia queda entre dos tipos, el ensayo prueba los dos: correr es gratis, y una tool que espera FASTQ y recibe un BAM falla en segundos con un error inconfundible. Si aun así no se resuelve, se hace **una** pregunta al que envía, "¿tu tool toma FASTQ o BAM?", que un revisor puede contestar leyendo el paper. Una pregunta, no 53.

**Qué viaja con el dato.** Hoy un dataset es un archivo. Tiene que ser un archivo más su contrato: referencia y nomenclatura de cromosomas (`chr1` vs `1`), longitud de lectura, y sobre todo el panel de loci que cubre (`loci.bed`, que ya existe para los BAM Illumina). Con eso el motor sabe, sin que nadie lo declare, qué nombres de loci pueden aparecer en la salida y cuántos. Eso cierra S6 sin pedirle nada al autor: "salida plausible" pasa a significar "menciona loci que el dato de entrada contiene". No es exactitud, sigue siendo ejecución.

**El BED de regiones lo genera STRhub.** Es el punto donde más duele "cada tool es un mundo": HipSTR quiere 5 columnas, GangSTR 5 con motivo, STRsearch 11 con flancos de secuencia. Hoy el autor lo sube. Pasa a generarse desde `str_candidates.bed` con un conversor por familia de formato; `harness/build_strsearch_bed.py` ya es el primero. El autor, si quiere, sube el suyo como opción avanzada.

**Ampliar la biblioteca.** Los cuatro tipos de hoy (FASTQ Illumina NIST, BAM ONT 1KGP, BAM Illumina autosómico y Y de GIAB) cubren la mayoría. Falta ONT FASTQ crudo, que es viable porque el runner ya descarga y cachea hg38 para los BAM. SNP y electroforesis capilar no tienen dato open-access razonable: ahí el veredicto honesto es "necesita datos del autor", y se dice así.

**La recomendación de incluir datos de prueba se mantiene**, pero como lo que es: un consejo al autor sobre reproducibilidad de su repo, no una condición del ensayo. Y cuando corre sobre datos de STRhub el reporte lo dice en el idioma del revisor: "corrió sobre una muestra de referencia pública; el repo no trae muestra propia".

### 4.7 Cómo se vería el lanzamiento

Tres páginas de entrada con un campo cada una, un catálogo curado con 5 herramientas consolidadas, y el caso STRspy como demostración: corre, pero falla en 9 loci, y la página lo dice. El mensaje para revisores es "pegá el link y en diez minutos sabés si el Quick Start del paper funciona". El mensaje para el usuario perdido es "compará con un entorno limpio". El mensaje para el dueño es "un badge que se re-verifica solo cada mes".

---

## 5. Plan de próximos pasos

### Fase 0. Cerrar el agujero y limpiar (1 semana)

1. **Aprobación manual de todo envío** hasta que exista el ensayo efímero (Fase 1) y la receta en repo (Fase 2): un `if` en `submit/route.ts:246`. Cierra S1.
2. `docker run` con `--network none --memory 6g --cpus 2 --pids-limit 512 --cap-drop ALL --security-opt no-new-privileges`; `maximum` en `timeout_minutes`; `permissions: contents: read` en el job `verify` y un job aparte para deploy y rechazo; `persist-credentials: false` en checkout.
3. Confinar `outputs[].path`: `pattern` en el esquema y `is_relative_to(out)` en `check_io.py` y `check_content.py`.
4. Quitar los `|| true` y el `| head -2` de los 4 Dockerfiles.
5. Retirar de `gh-pages` los 6 slugs de depuración; decidir `gangstr-2-5` vs `gangstr-v2-5` y pinear a SHA; unificar `strspy` y `strspy-v2-0-ont`.
6. Hacer que el bucle de push falle si no pushea; `concurrency` o un job único de deploy.
7. Borrar `.env.local.save`, rotar `JWT_SECRET`; JWT a 12 h con `algorithms: ["HS256"]`; escapar HTML en `lib/email.ts`; rate-limit en `/status` y `/repo-context`.
8. Limpiar la raíz según la tabla de P3; borrar ramas mergeadas; resolver o descartar el stash; `git gc`.

### Fase 1. El ensayo (3 a 4 semanas)

9. Modo ensayo en `verify.yml` (`publish: false`): receta como inputs del dispatch, sin commit a `main`, sin deploy, resultado como artifact con link privado de 30 días.
10. Detección determinista de receta (`harness/detect_recipe.py`): método de instalación, datos de ejemplo, comando del README, Bioconda. Con tests sobre los 5 repos reales del catálogo.
11. Inferencia del tipo de entrada desde el repo, con ensayo de dos tipos cuando hay duda y una sola pregunta al que envía como último recurso; cada `dataset.yml` lleva su contrato (referencia, nomenclatura de cromosomas, panel de loci) y el motor deriva de ahí el vocabulario de loci esperado; conversores de BED por familia de formato desde `str_candidates.bed` (el de STRsearch ya existe).
12. Compuerta `reproduces_own_example` implementada: correr el ejemplo documentado con los datos del repo y comparar con la salida documentada si existe.
13. Los cuatro veredictos en `report.py` y en la web, con la lista de huecos del README cuando el veredicto es "no se pudo determinar" (reemplaza el checklist por palabras clave, que hoy da 5/5 a una línea de texto).
14. **Re-verificar cuando la tool cambia**: `upstream.py` ya detecta "N commits desde el ref"; falta que un release o tag nuevo en el repo dispare un ensayo con el ref nuevo y avise al dueño (así se atrapa el caso STRspy: la v2 publicada seguía llamando código de la v1). Publicar solo si el dueño confirma.
15. Tests del motor: mergear `fix/bed-header-and-shared-cases`; pytest para `check_io`, `check_content`, `diagnose_log`, `prepare`, `report`; correrlos en el job `resolve`. Arreglar conteo TSV, falsos positivos, aviso obsoleto, `$GITHUB_OUTPUT`, `git ls-remote --`, `ref` como SHA.

### Fase 2. Las tres entradas (3 a 4 semanas)

16. Página "Revisar para un paper": URL + tag, sin aprobación, informe privado compartible.
17. Página "¿Es mi entorno o la tool?": búsqueda en catálogo, entorno y comando exactos, "pegá tu error" con `diagnose_log` (la web ya tiene el espejo `diagnostics.ts`).
18. "Verificar mi tool" reducido a URL + ref + panel avanzado; "Publicar" solo tras ensayo verde; soporte de `strhub-verified.yml` en el repo del dueño como prueba de control (reemplaza la aprobación manual).
19. Runner local `harness/run_local.py` para dueños.

### Fase 3. El bucle con el modelo y la deuda (2 a 3 semanas)

20. Bucle autoconfig → ensayo → diagnóstico → corrección, hasta 5 intentos, solo sobre la receta; el humano ve la que funcionó.
21. Un solo origen para las constantes espejo motor ↔ web, con test de igualdad.
22. Partir `verified-submit-form.tsx`; polling con tope; borrar código muerto; consolidar renders y etiquetas del motor; README, RUNBOOK, `datasets/README.md` y `download.sh` al día.

### Fase 4. Lanzamiento público

23. Catálogo consolidado: una entrada por herramienta, variantes por kit con `tool.variant`; `maintainer` y `contact` completos.
24. `VERIFIED_PUBLIC = true`; anuncio con las tres entradas y el caso STRspy.
25. Invitar a 5 a 10 mantenedores con la receta ya armada para que solo confirmen, y a 2 o 3 editores de revistas del área para probar la entrada de revisores.

### Después

- Estado en un almacén real (Vercel KV o Postgres) en vez de commits al motor.
- Panel ONT (faltan coordenadas hg38 de DXS8378, DXS7132, AMEL, AMEL_Y).
- Git LFS o release assets para los BAM.
- Nivel 2 (verificación manual), ya implementado; activarlo cuando el catálogo sea público.

---

## Anexo A. Registro de herramientas (18 directorios, 5 herramientas)

| slug | herramienta | ref | tipo de entrada | fixture / regions | Dockerfile | estado publicado | nota |
|---|---|---|---|---|---|---|---|
| `gangstr-2-5` | GangSTR | `v2.5` (tag móvil) | illumina-bam-hg38 | slice NA12878 | miniconda pineado; `\| head -2` enmascara | installs | ref viola el esquema |
| `gangstr-v2-5` | GangSTR | SHA | illumina-bam-hg38 | slice NA12878 | `miniconda3:latest`; `\|\| true` | io | duplicado del anterior |
| `hipstr-v0-7` | HipSTR | SHA b2033bf | illumina-bam-hg38 | slice NA12878 | ubuntu 22.04 | content | mismo commit que los 3 siguientes |
| `hipstr-b2033bf` | HipSTR | SHA b2033bf | illumina-bam-hg38 | BED propio | ubuntu 22.04 | content | content trivial (solo `dna_column`) |
| `hipstr-v0-7-y` | HipSTR | SHA b2033bf | illumina-bam-hg38-y | slice HG002 | ubuntu 22.04 | content | |
| `hipstr-b2033bf-y` | HipSTR | SHA b2033bf | illumina-bam-hg38-y | BED propio | ubuntu 22.04 | content | content trivial |
| `strait-razor-PowerSeqv2.31` | STRaitRazor | SHA b618e93 | illumina-str-fastq | NIST 2,3 MB | `\|\| true` ×2 | content | debería ser `variant` |
| `strait-razor-ForenSeqv1.27` | STRaitRazor | SHA b618e93 | illumina-str-fastq | NIST 3,8 MB (dup del dataset) | `\|\| true` ×2 | content | debería ser `variant` |
| `strait-razor-b618e93` | STRaitRazor | SHA b618e93 | illumina-str-fastq | dataset | `python:3.11-slim`, sin make | content | depende del binario precompilado |
| `straitrazor-v1-0` | STRaitRazor | SHA b618e93 | illumina-str-fastq | fixture de otra tool | `RUN echo Ok` | no publicado | cmd roto (sin espacio) |
| `straitrazor-v1-0-2`, `-3` | STRaitRazor | SHA b618e93 | illumina-str-fastq | idem | idem | installs | cmd roto; **retirar** |
| `straitrazor-v1-0-4`, `-5` | STRaitRazor | SHA b618e93 | sin `inputs.type` | dataset | idem | installs / io | **retirar** |
| `straitrazor-v3-0` | STRaitRazor | SHA b618e93 | illumina-str-fastq | dataset | make o cmake | content | la variante sana |
| `strsearch-c70179b` | STRsearch | SHA | illumina-bam-hg38 | BED propio | `set -eux` + import check | content | mejor Dockerfile del repo |
| `strspy` | STRspy | SHA dafdee7 | ont-bam-hg38 | slice HG00113 | micromamba 1.5.8 | no publicado | sin `report.slug` |
| `strspy-v2-0-ont` | STRspy | SHA dafdee7 | ont-bam-hg38 | dataset | micromamba 1.5.8 | io (errores reportados) | la publicada |

Los 18 manifiestos validan contra el esquema. 10 no declaran `maintainer` ni `contact`. Ninguno usa `tool.variant`, `compatibility` ni `caveats`.

## Anexo B. Números de referencia

| Métrica | Valor |
|---|---|
| Líneas del formulario de envío | 3.377 |
| Controles del formulario | 53 |
| Líneas de `generate_pdf.py` | 1.220 |
| Tests web / motor | 93 / 0 |
| Claves i18n de Verified usadas / faltantes | 349 / 0 |
| PRs mergeados motor / web | 18 / 25+ |
| Ramas locales mergeadas sin borrar | 9 + 9 |
| Tamaño `gh-pages` | 2,2 MB |
| Espacio recuperable en la raíz | ~91 MB |
