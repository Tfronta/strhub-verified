# RUNBOOK — Correr la verificación de STRspy de cero

Objetivo: pasar de "tengo el zip" a "veo las compuertas corriendo en GitHub
Actions y obtengo un badge". La única parte nueva es el paso 2 (el BAM de
prueba); el resto es git + la pestaña Actions.

Prerrequisitos: una cuenta de GitHub, `git`, y `samtools` instalado localmente.
(Opcional pero cómodo: la GitHub CLI `gh`.)

---

## Paso 1 — Subir el scaffold a un repo de GitHub (PÚBLICO)

El repo TIENE que ser público: ahí los runners de GitHub Actions son gratis e
ilimitados. (En privado pagarías minutos.)

```bash
unzip strhub-verified.zip
cd strhub-verified
git init -b main
git add .
git commit -m "STRhub Verified v0 scaffold + STRspy 2.0"
```

Crear el repo y pushear. Con la CLI de GitHub:

```bash
gh repo create strhub-verified --public --source=. --push
```

O por la web: New repository → nombre `strhub-verified` → **Public** → Create →
y seguí las instrucciones "push an existing repository":

```bash
git remote add origin https://github.com/<TU-USUARIO>/strhub-verified.git
git push -u origin main
```

---

## Paso 2 — Armar el BAM de prueba (el fixture)

STRspy con input BAM necesita reads alineados a **hg38** sobre los loci de su
base de datos. No bajamos nada gigante: tomamos UN BAM que ya tengas (de tu
benchmark 1KGP-ONT) y le recortamos solo las regiones de los STRs.

**2a.** Traer la lista de regiones de STRspy (congelada al commit que estamos verificando):

```bash
curl -sL https://raw.githubusercontent.com/unique379r/strspy/dafdee7e7e5672c8dc732e8577dbe153f53a12f5/db-v2/STRspy_v2.DB.sort.bed -o region.bed
```

**2b.** CHEQUEO IMPORTANTE — los nombres de cromosoma del BAM deben coincidir
con el bed (`chr3`, no `3`). Si no coinciden, el recorte sale vacío y STRspy
"corre" pero no produce nada (falla silenciosa — justo lo que queremos atrapar,
pero acá lo evitamos a propósito):

```bash
samtools view -H TU_BAM_GRANDE.bam | grep '@SQ' | head -3
# Debe mostrar SN:chr3, SN:chr12, etc. Si muestra SN:3, tu BAM usa otra
# convención y habría que renombrar contigs (avisame y lo resolvemos).
```

**2c.** Recortar a las regiones de los STRs, ordenar e indexar:

```bash
mkdir -p strhub-verified/fixtures/strspy-bam
samtools view -b -L region.bed TU_BAM_GRANDE.bam \
  | samtools sort -o strhub-verified/fixtures/strspy-bam/sample.bam -
samtools index strhub-verified/fixtures/strspy-bam/sample.bam
```

**2d.** Verificar que quedó chico y con reads (si pesa de más, down-sampleá con
`samtools view -s 0.2 -b`):

```bash
ls -lh strhub-verified/fixtures/strspy-bam/sample.bam
samtools view -c strhub-verified/fixtures/strspy-bam/sample.bam   # nº de reads, > 0
```

**2e.** Commitear el fixture. Si es < ~5 MB, directo; si es más, usá Git LFS
(`git lfs track "*.bam"`):

```bash
cd strhub-verified
git add fixtures/strspy-bam/
git commit -m "Add tiny hg38 ONT BAM fixture for STRspy"
git push
```

---

## Paso 3 — Disparar las compuertas

En la web del repo → pestaña **Actions**. La primera vez GitHub pide habilitar
los workflows: "I understand my workflows, go ahead and enable them".

Luego: workflow **STRhub Verified** (panel izquierdo) → botón **Run workflow** →
en el campo `tool` escribí **`strspy`** → **Run workflow**.

(Esto es el modo `workflow_dispatch`. También se dispara solo cuando abrís un PR
que toca `tools/**`.)

---

## Paso 4 — Leer el resultado

Entrá al run que apareció. Vas a ver los pasos = las compuertas:

| Paso en Actions | Compuerta |
|---|---|
| `Gate · Available` | el ref público existe |
| `Gate · Installs` | **`docker build`** — ¿resuelve el env viejo de STRspy? |
| `Gate · Runs` | **`docker run`** sobre tu BAM |
| `Gate · Expected IO` | ¿produjo una tabla no vacía? |
| `Build attestation + badge` | arma `reports/strspy.json` + el badge |

Descargá el artifact **`attestation-strspy`** (sección Artifacts del run):
adentro está `reports/strspy.json` (la atestación) y `reports/strspy.badge.json`.

---

## Paso 5 — Interpretar (y qué esperar)

- Este primer run es, en parte, de **descubrimiento**: confirma los nombres
  exactos de los archivos de salida de STRspy y si algún flag necesita ajuste.
  El glob de salida en el manifest (`**/*.txt`) es a propósito conservador.
- Si **Installs** falla, casi seguro es el env sin versiones fijadas + Python
  3.7.7 (EOL): el solver de conda no arma el entorno hoy. **Eso es un hallazgo,
  no un error tuyo.** No tocás STRspy; lo registrás (y, como sugirió Jonathan,
  se reporta por GitHub Issues del repo original).
- Si **Runs** falla con salida vacía, revisá el chequeo 2b (nombres de contig).
- El badge refleja honestamente hasta dónde llegó: p. ej. "Available ✅;
  Installs requiere ajustes no documentados". Constructivo, no humillante.

---

## Atajo para validar el motor primero (opcional)

Si querés ver el pipeline entero en verde ANTES de pelear con el env real de
STRspy, corré el workflow con `tool = strait-razor-PowerSeqv2.31`. Te confirma
que Actions, las compuertas y el reporte funcionan; después vas por el caso difícil.

---

## StraitRazor sobre datos reales del NIST (Illumina, mds2-2157)

StraitRazor es MPS/Illumina, así que se valida con los datos del NIST
`mds2-2157` (no con los BAM ONT de STRspy). Ya hay **dos variantes** listas, con
fixtures reales chiquitos (5.000 reads, mismo donante NTD01) commiteados:

| `tool` en Actions (directorio) | Kit (Illumina) | Config |
|---|---|---|
| `strait-razor-PowerSeqv2.31` | Promega PowerSeq 46GY | `PowerSeqv2.31.config` |
| `strait-razor-ForenSeqv1.27` | Verogen ForenSeq      | `ForenSeqv1.27.config` |

Disparalas igual que STRspy: pestaña **Actions** → workflow **STRhub Verified** →
**Run workflow** → en `tool` elegí la variante en el desplegable (el nombre ya
incluye el kit y la versión del config). Cada corrida produce su atestación en
`reports/<slug>.json` y su badge `reports/<slug>.badge.json`.

La procedencia exacta de cada fixture (archivo dentro del zip + cómo se regenera
con `remotezip`, sin bajar los 5-8 GB) está en el `SOURCE.txt` de cada carpeta
`tools/<variante>/fixtures/nist-mds2-2157/` y en `fixtures/nist-mds2-2157/README.md`.

Qué esperar en este primer run real:
- **Available / Installs**: deberían pasar (repo público + build C++ del binario).
- **Runs**: primer contacto del binario con reads reales; si algún flag o ruta de
  config necesita ajuste, el log lo muestra (el manifest marca esos puntos).
- **Expected IO**: confirma que `*.allsequences.txt` salió no vacío (atrapa el
  exit-0-pero-vacío).
- **Content**: el peldaño más alto. Confirma que el output *parece genotipos*:
  5 columnas, columna de secuencia solo ADN, conteos enteros, y suficientes loci
  forenses reconocibles (loci core obligatorios + mínimo de loci distintos). Lo
  declarás en el bloque `outputs[].content` del manifest. NO afirma que los
  genotipos sean correctos (eso es concordancia, fuera de alcance).

## La escalera de niveles (qué dice el badge)

| Nivel | Badge | Significa |
|---|---|---|
| `available` / `installs` | amarillo | el repo existe / la imagen compila |
| `runs` | verde | ejecuta sin romperse |
| `io` | verde | produjo un archivo no vacío del formato declarado |
| `content` | **brightgreen** | el output parece datos de genotipos plausibles |

Cada run genera también `reports/<slug>.summary.md`: un resumen legible para
humanos (qué pasó, qué loci salieron, profundidad, y qué NO se afirma).

---

## Fase 2 — Submission self-service (GitHub App)

La web (`strhub-web`) puede commitear el `manifest.yml` + `Dockerfile` a este repo
y disparar el workflow en nombre del autor, vía una **GitHub App central**. El
autor nunca toca este repo; su código nunca se guarda (el Dockerfile lo clona en
build time).

### Crear la GitHub App (una vez, acción del mantenedor)

1. GitHub → Settings → Developer settings → **GitHub Apps** → New GitHub App.
2. Permisos (mínimos):
   - **Repository → Contents: Read and write** (commitear `tools/<slug>/`).
   - **Repository → Actions: Read and write** (`workflow_dispatch` + leer runs).
   - **Repository → Metadata: Read-only** (obligatorio).
3. Instalar la App **solo en el repo `strhub-verified`**.
4. Generar una **private key** (PEM) y anotar el **App ID** y el **Installation ID**.

### Cargar los secrets en la web (Vercel/host de `strhub-web`)

| Variable | Valor |
|---|---|
| `GITHUB_APP_ID` | el App ID numérico |
| `GITHUB_APP_PRIVATE_KEY` | el PEM (raw o base64; el helper acepta ambos) |
| `GITHUB_APP_INSTALLATION_ID` | el Installation ID |
| `VERIFIED_ENGINE_REPO` | `Tfronta/strhub-verified` (default) |
| `VERIFIED_ENGINE_BRANCH` | `main` (default) |
| `VERIFIED_WORKFLOW_FILE` | `verify.yml` (default) |
| `JWT_SECRET` | el mismo secreto admin (para `/api/verify/approve`) |

### Flujo

1. Autor completa `/verified/submit` (validación `zod` espejo del schema).
2. `POST /api/verify/submit`: valida, rate-limit, chequea slug libre y que el
   fixture BYOR sea público; si el repo es nuevo, queda **pendiente de aprobación**.
3. Admin aprueba el repo nuevo: `POST /api/verify/approve` con `Authorization:
   Bearer <jwt>` y `{ "repo": "https://github.com/owner/tool" }`. El autor reenvía.
4. Repos aprobados: la web commitea `tools/<slug>/{manifest.yml,Dockerfile}` y
   dispara `verify.yml` con un `dispatch_id` único.
5. `run-name` del workflow incluye el `dispatch_id`; `GET /api/verify/status?
   dispatchId=` lo encuentra filtrando los runs y muestra el progreso en vivo.

> Rate-limit por defecto: 5 envíos/hora por IP, 3/hora por repo
> (`lib/verified/store.ts`).

---

## Fase 3 — Matriz own/external, datasets tipados y README-check

### Librería de datasets (`datasets/`)

Datasets de referencia tipados por assay. `datasets/index.json` mapea
`inputs.type` → archivo de datos:

```
datasets/
  README.md                   # disclaimer + catalogue (STRhub is not data custodian)
  index.json                  # type → { data, bam_index?, name, source, license, … }
  illumina-str-fastq/
    dataset.yml               # metadata
    sample.fastq              # datos (NIST mds2-2157)
    SOURCE.txt                # procedencia
  ont-bam-hg38/
    dataset.yml               # metadata (data lives in ont_slices/)
    SOURCE.txt                # 1000 Genomes ONT, R10 SUP, open access on AWS

ont_slices/                   # pre-built hg38 CODIS BAM slices (shared by ont-bam-hg38)
  codis_pm10kb.bed
  HG00113.codis.bam (+ .bai)  # default external test file (~30 MB)
  …                           # HG00154, GM19038, HG00097, HG00263 also available
```

Agregar un dataset: crear `datasets/<type>/` con metadata + `SOURCE.txt`, apuntar
`data` (y `bam_index` si aplica) en `datasets/index.json`. Los BAM ONT ya
commiteados viven en `ont_slices/` — no hace falta duplicarlos. Si un
`inputs.type` no tiene match, la pierna externa se reporta **N/A** (nunca falla).

### Matriz de verificación (en `verify.yml`)

Cada run corre dos piernas (cuando aplican):

| Pierna | Input | Origen |
|---|---|---|
| **own** | `work/in_own` | fixture del autor (path local o BYOR remoto `repo+ref+path`) |
| **external** | `work/in_external` | dataset tipado de `datasets/` por `inputs.type` |

`harness/prepare.py` resuelve el dataset y stagea ambas piernas (descarga el BYOR
remoto desde `raw.githubusercontent.com`). El badge/escalera usa la pierna
**own**; la matriz completa va a `matrix.json` → `report.py` → `<slug>.json`,
HTML y `index.json` (`own_state` / `external_state`).

### README-check (advisory)

`harness/check_readme.py` baja el README del repo del autor (al ref fijado) y
corre un checklist de presencia de 5 ítems (install, comando, input, output,
dependencias). Es **siempre informativo**: nunca cambia el badge de ejecución.
Determinista (keywords), sin costo de API.

Salida en el reporte: `readme_check.score` / `readme_check.max` + cada ítem.
