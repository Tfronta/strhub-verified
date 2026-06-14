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
STRspy, corré el workflow con `tool = strait-razor` usando el fixture sintético
que ya viene incluido. Te confirma que Actions, las compuertas y el reporte
funcionan; después vas por el caso difícil.
