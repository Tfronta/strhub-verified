# Plan de implementación — BED provisto por el dueño de la tool

> **ESTADO (2026-07-16): Fases A, B, C, D completas y verificadas en CI real.**
> Rama `test/owner-bed` en ambos repos, con PRs abiertos. `main` intacto.
>
> **Orden de merge obligatorio: engine ANTES que web.** El form fetchea el panel desde
> `main` del engine; si la web va primero, da 404.
>
> Tras el merge: borrar `NEXT_PUBLIC_VERIFIED_ENGINE_RAW` de `.env.local` (el default
> ya apunta a main).
>
> **Pendiente:** panel ONT (bloqueado: faltan coords hg38 de DXS8378, DXS7132, AMEL,
> AMEL_Y — AMEL ni siquiera es un STR). Solo `strspy` usa ese dataset.

**Objetivo:** que el dueño de una tool pueda validar su herramienta sin que STRhub
toque código ni prepare BEDs a mano. STRhub publica los **loci soportados por panel**
(los que cubren los slices BAM); el dueño construye su BED sobre esos loci y lo
referencia desde el formulario. El harness lo baja, lo valida contra el panel, y corre.

**Alcance que NO cambia:** sigue siendo "valida que corre" (Runs + Output Structure).
No se agrega ninguna afirmación de exactitud. El BED solo decide *qué regiones* se le
pasan a la tool; la validación del BED es de *cobertura*, no de corrección genética.

**Insight clave que simplifica todo:** las columnas 1-3 de un BED (chrom, start, end)
son estándar en todos los formatos (HipSTR usa 7 columnas, GangSTR otras). El validador
parsea solo esas 3 → es **agnóstico al formato de la tool**.

---

## PRINCIPIO RECTOR: un BED fuera de panel NO es un fallo de la tool

Las muestras de STRhub Verified son **slices**, no genomas enteros. Si el dueño declara
una ventana que el slice no cubre, la tool no va a encontrar reads ahí — pero **eso no
es un error del pipeline ni de la herramienta**. Es un input fuera de contrato.

Consecuencia de diseño (crítica):

- ❌ **NO** modelar esto como un gate del CI. Un gate en rojo publica un reporte que dice
  "esta tool falló", difamando una herramienta sana por un error de input.
- ✅ **SÍ** modelarlo como **rechazo de submission**: se detecta antes de correr nada,
  no se genera reporte ni badge, y el dueño recibe un mensaje accionable.

Por eso la validación va en **dos capas**:

| Capa | Dónde | Cuándo | Si falla |
|---|---|---|---|
| 1 | Web (form) | Al pegar/apuntar el BED, antes de despachar CI | Error inline en el form. No se despacha. No se quema CI. |
| 2 | Harness | Después de `prepare.py`, **antes** de los gates | **Abort** del workflow. Sin reporte, sin badge. Red de seguridad para manifests commiteados a mano. |

Y para que el dueño no se equivoque en primer lugar: **el panel se puede descargar**
desde el form (`loci.bed`, 4-col) y solo tiene que convertirlo al formato de su tool.

---

## Fase A — Publicar loci soportados por panel — ✅ HECHA (Illumina) / ⏸️ ONT bloqueado

**Estado real** (difiere del plan original, ver abajo):

- ✅ `harness/build_panel.py` (NEW) — genera el panel desde la COBERTURA REAL del BAM.
- ✅ `datasets/illumina-bam-hg38/loci.bed` — 24 loci, piso 55x, sin exclusiones.
- ✅ `datasets/illumina-bam-hg38-y/loci.bed` — **14** loci (no 15), piso 10x.
- ✅ `dataset.yml` ×2 + `index.json` — `supported_loci` + `min_loci: 5` cableados.
- ⏸️ `datasets/ont-bam-hg38/loci.bed` — BLOQUEADO, ver abajo.

### Regla del panel (decidida durante la implementación)

> window = el span más ancho alrededor del STR, tope ±1000bp, donde **TODA** base
> tiene ≥10 reads. Un locus cuyo STR cae por debajo del piso se **excluye**.

Crece hacia afuera desde el STR, no recorta hacia adentro desde los bordes: el recorte
inward se detiene en la primera base sobre el piso y deja pasar baches interiores.
(Ese bug existió y lo cazó la columna de evidencia: DYS385_2 salía con min 8x bajo un
piso de 10.)

Formato: BED 5-col — `chrom start end name score(=min_depth)`. La col 5 es `score` en
el estándar BED, así que cada locus carga su propia evidencia y un cambio de muestra
se detecta como regresión.

### 🔴 Hallazgo: DYS385a (DYS385_1) EXCLUIDO del panel Y

El STR de DYS385a tiene profundidad **2-10x** en el slice HG002 (el resto: 48-188x).

No es un artefacto nuestro: los reads que hay son MAPQ 70, no hay secundarios ni
duplicados filtrados, y el BAM conserva MAPQ 0 globalmente (no aplicamos filtro al
cortar). Los reads **no están en el GIAB original**. DYS385a/b son copias palindrómicas
casi idénticas a ~40kb; el alineamiento colapsa la duplicación sobre la copia `b`
(156x) y deja hambrienta a la `a`. No se arregla re-cortando.

Corrobora el reporte existente de `hipstr-v0-7-y`: DYS385_1 salió con **depth 34** vs
161-320 del resto. Estaba ahí a la vista.

Prometer DYS385a le entregaría al autor una llamada de baja confianza y lo dejaría
creyendo que su tool está rota. Recuperarlo requiere un BAM fuente sin el colapso.

### ⏸️ ONT bloqueado — faltan coordenadas de 4 loci

`ont_slices/codis_pm10kb.bed` son ventanas de ±10kb sin coordenadas de STR, y 21/26
violan el piso de 10x (los bordes de una ventana de 20kb no tienen cobertura; el STR
en sí está bien). Para aplicar la regla necesito coords de STR: tengo 22 de 26 (CODIS
+ DYS393 + DYS391, de los assets de HipSTR). **Faltan DXS8378, DXS7132, AMEL, AMEL_Y**
— y AMEL ni siquiera es un STR (es un marcador de sexo por deleción).

No inventé coordenadas genómicas para un panel forense. Requiere decisión + fuente.
Impacto acotado: solo `strspy` usa `ont-bam-hg38`. Las 4 tools que necesitan BED
(HipSTR ×2, GangSTR ×2) usan los paneles Illumina, que están listos.

### Deuda detectada (no bloqueante)

- `datasets/illumina-bam-hg38-y/regions.bed` (10 filas, HipSTR-format, incompleto)
  quedó superado por `loci.bed`. **No lo borré** — decisión tuya.
- **Nada lee `dataset.yml`**: la fuente machine-readable es `index.json`
  (`datasets.py`, `build_index.py`, `generate_pdf.py`). Los dos duplican info y pueden
  driftear. Hoy están sincronizados a mano.

---

## Fase A — plan original (referencia)

La fuente de verdad: por cada dataset BAM, las "ventanas de slice" (cada locus ±1000bp)
que el BAM realmente cubre. El BED del dueño debe caer dentro de esas ventanas.

1. **`datasets/illumina-bam-hg38-y/loci.bed`** (NEW)
   BED canónico 4-col: `chrom  slice_start  slice_end  locus_name`.
   Derivar de las coordenadas de los 15 loci Y ±1000bp. Ya existe casi todo en el
   asset `tools/hipstr-v0-7-y/assets/regions.bed` (18 filas) — convertir a 4-col y
   expandir a ventanas de slice.

2. **`datasets/illumina-bam-hg38/loci.bed`** (NEW)
   Lo mismo para los 24 loci autosómicos (CODIS 20 + PentaD/E + D6S1043 + SE33).
   Tomar coords de la fuente del slice autosómico.

3. **`datasets/ont-bam-hg38/loci.bed`** (NEW)
   CODIS sobre hg38. Ya existe `ont_slices/codis_pm10kb.bed` — normalizar a 4-col.

4. **`datasets/*/dataset.yml`** (EDIT ×3 BAM)
   Agregar:
   ```yaml
   supported_loci: loci.bed     # relativo al dir del dataset
   min_loci: 5                  # mínimo de loci que el BED del dueño debe cubrir
   ```

5. **`datasets/index.json`** (EDIT)
   Por cada dataset BAM agregar `"supported_loci": "datasets/<x>/loci.bed"` y
   `"loci_count": N`. (Lo consume `datasets.py:resolve`, que ya devuelve el record entero.)

6. **Limpieza:** borrar la nota stale "PENDING / 10/18 rows / Y leg not wired" en
   `dataset.yml` Y y en `index.json` (el asset ya tiene 18 filas completas).

---

## Fase B — Contrato: schema + manifest — ✅ HECHA

- ✅ `strhub-verified/schema/manifest.schema.json` — `inputs.regions` (oneOf string | {repo,ref,path}).
- ✅ `strhub-web/lib/verified/submission.ts`:
  - `remotePointerSchema` (renombrado de `remoteFixtureSchema`, con alias deprecado).
  - `inputs.regions` en `submissionSchema` (solo valida shape; cobertura se chequea aparte).
  - `isRemotePointer` type-guard (reemplaza `isRemoteFixture`, alias deprecado).
  - `INPUT_TYPES`: los 2 BAM Illumina con `requiresRegions:true`, `minLoci:5`,
    `supportedLoci:[...]` (copiados exactos de los `loci.bed`). ONT queda sin
    `requiresRegions` hasta tener su panel.
- ✅ `strhub-web/lib/verified/manifest.ts` — emite `inputs.regions` (remoto o string).

Verificado: `tsc --noEmit` limpio (0 errores); test funcional cubre remoto/local/
sin-regions/repo-no-https/campo-extra → todos correctos. Backwards-compat: manifests
sin regions no emiten la clave.

### Plan original (referencia)

Espejar el patrón ya existente de `inputs.fixture` (string local | remoto {repo,ref,path}).

7. **`strhub-verified/schema/manifest.schema.json`** (EDIT)
   En `inputs.properties` agregar `regions`, con el mismo `oneOf` que `fixture`
   (string path | objeto remoto). Descripción: "BED de regiones del dueño; columnas
   1-3 deben caer dentro de los loci soportados del dataset elegido."

8. **`strhub-web/lib/verified/submission.ts`** (EDIT)
   - Nuevo `remoteRegionsSchema` (idéntico a `remoteFixtureSchema`).
   - `submissionSchema.inputs`: agregar
     `regions: z.union([z.string()..., remoteRegionsSchema]).optional()`.
   - En `INPUT_TYPES`, a las entradas BAM (`ont-bam-hg38`, `illumina-bam-hg38`,
     `illumina-bam-hg38-y`) agregar:
     `requiresRegions: true` y `supportedLoci: string[]` (lista legible de loci,
     para mostrar en el form).

9. **`strhub-web/lib/verified/manifest.ts`** (EDIT)
   En `buildManifestObject`, después del bloque `inputs.fixture`, emitir
   `inputs.regions` (remoto o string) con la misma lógica `isRemoteFixture`.
   Agregar helper `isRemoteRegions` (o reusar el genérico).

---

## Fase C — Formulario web — ✅ HECHA

- ✅ `lib/verified/validate-regions.ts` (NEW) — espejo TS de `validate_bed.py`.
  Verificado que coincide con el Python en los mismos fixtures (mismos counts).
- ✅ `verified-submit-form.tsx` — campo BED obligatorio cuando el input-type es BAM,
  panel de loci soportados + descarga del `loci.bed`, validación en vivo (debounce
  600ms) que bloquea el submit. Probado en navegador en ambas direcciones.
- ✅ `app/api/verify/submit/route.ts` — revalidación server-side (el chequeo del form
  es UX, no enforcement).
- ✅ i18n en/es/pt. Corregido de paso: los blurbs decían "15 Y-STR loci" → 14.
- ✅ Bug de display corregido: el rechazo mostraba la col-4 del BED como "name"
  (en HipSTR es el period → salía "(4)"). Contradecía el "solo leemos cols 1-3".

Config: `NEXT_PUBLIC_VERIFIED_ENGINE_RAW` en `.env.local` apunta a la rama de prueba
mientras el panel no esté en `main` del engine. **Borrar esa variable tras el merge**
(el default ya apunta a main).

---

## Fase C — plan original (referencia)

10. **`components/verified/verified-submit-form.tsx`** (EDIT)
    - `INITIAL_F`: agregar `regionsRepo`, `regionsRef`, `regionsPath`.
    - Nueva subsección **"Regions BED"** dentro de la Section "Input data", visible
      solo cuando `selectedTypeInfo?.requiresRegions`. Reusar el patrón de radios
      `same repo / other repo` del fixture. Campos repo/ref/path.
    - **Panel de loci soportados + botón de descarga** del `loci.bed` canónico
      ("Descargá las coordenadas que cubre este slice y convertilas al formato de tu
      tool"). Esto es lo que hace el flujo realmente self-service.
    - **Validación en vivo (Capa 1)**: al tener repo+ref+path, fetchear el BED vía
      `raw.githubusercontent.com` (ya se hace igual para el README, ver
      `fetchCmdFromReadme`) y validarlo client-side contra `supportedLoci`.
      Mostrar error accionable listando las filas fuera de panel. Bloquear `canSubmit`.
    - `buildPayload()`: armar `inputs.regions` desde los campos (mismo criterio que
      fixture: si `same`, repo/ref = source.repo/ref).
    - `SubmissionParams`: mostrar el BED en el resumen.
    - `saveFormState`/`loadFormState`: incluir los campos nuevos.

11. **`lib/verified/validate-regions.ts`** (NEW, compartido web)
    Lógica pura de validación (misma que `validate_bed.py`, en TS): parsear cols 1-3,
    chequear overlap contra ventanas soportadas, contar loci distintos.
    Devuelve `{ok, coveredLoci, outOfPanel[]}`. Sin I/O — testeable y reusable.

12. **`app/api/verify/submit/route.ts`** (EDIT)
    Revalidar server-side antes de commitear el manifest y despachar (la validación
    client-side es UX, no seguridad). Si falla → `400` con el detalle, sin despachar.

13. **`lib/i18n/locales/{en,es,pt}/verified.ts`** (EDIT ×3)
    Strings nuevos: `regionsLabel`, `regionsExplainer`, `regionsPathHint`,
    `supportedLociTitle`, `supportedLociDownload`, `regionsRequiredError`,
    `regionsOutOfPanelError`.

---

## Fase D — Harness: staging + validación — ✅ NÚCLEO HECHO / ⏸️ #16 pendiente

- ✅ `harness/validate_bed.py` (NEW) — valida cols 1-3, overlap contra panel, min_loci,
  normaliza prefijo `chr`. Probado con 6 casos: asset legacy, GangSTR (5-col),
  solo-DYS385a, <min_loci, sin-prefijo-chr, BED válido. Exit 1 = abort.
- ✅ `harness/prepare.py` — `stage_regions()` baja/copia el BED a ambas legs como
  `regions.bed` con **precedencia sobre el asset** (probado). Emite `regions_source`
  (tool|strhub|none), `supported_loci`, `min_loci`.
- ✅ `.github/workflows/verify.yml` — step "Pre-flight · Regions within panel"
  después de Prepare, sin `continue-on-error` → **aborta** si el BED del dueño no
  valida. Condición: `regions_source == 'tool' && supported_loci != ''`.
  Integración probada: BED con DYS385a → exit 1 → job aborta.
- ⏸️ **#16 (provenance en el reporte)** — PENDIENTE. Toca las dos rutas de render de
  `report.py` (MD + HTML) y el wiring de la atestación. Es capa de presentación, no
  bloquea el flujo. **Contenido decidido:**
  - ✅ Provenance del BED: "provided by tool owner" vs "provided by STRhub" + cuántos
    loci del panel cubre (ej: 12 of 14).
  - ✅ Aclarar que el dataset es un **slice** alrededor de N loci forenses, no un
    genoma entero.
  - ❌ NO nombrar loci excluidos (DYS385a) en el reporte — mantenerlo menos técnico.

### Deuda detectada

- El asset legacy `tools/hipstr-v0-7-y/assets/regions.bed` **incluye DYS385_1**. No se
  valida (es `regions_source=strhub`), así que el tool sigue corriendo — pero al
  re-verificarse produciría de nuevo la llamada débil de DYS385_1 (depth 34). Debería
  recortarse al panel. No bloqueante.

### Plan original (referencia)

12. **`harness/prepare.py`** (EDIT)
    - Leer `inputs.regions` del manifest. Si es remoto, bajarlo (reusar la rama
      remota de `stage_own`) a `work/in_own/regions.bed` y `work/in_external/regions.bed`
      con nombre canónico `regions.bed`.
    - **Precedencia:** si hay `inputs.regions`, ignorar el asset `tools/<t>/assets/regions.bed`
      (queda como fallback legacy). Emitir step-output `regions_source=tool|strhub|none`.
    - Emitir también `supported_loci=<path>` y `min_loci=<n>` resueltos del dataset.

14. **`harness/validate_bed.py`** (NEW, ~60 líneas)
    Args: `--bed work/in_external/regions.bed --supported datasets/<x>/loci.bed --min-loci N --json out.json`
    - Parsear cols 1-3 del BED del dueño (ignora columnas extra → agnóstico al formato).
    - Cargar ventanas soportadas (`loci.bed`).
    - Para cada fila del BED: debe **overlapar** alguna ventana soportada.
      Filas fuera de toda ventana → lista de `out_of_panel`.
    - Contar loci distintos cubiertos; fallar si `< min_loci` o si hay `out_of_panel`.
    - Salida JSON: `{pass, covered_loci, out_of_panel[], reason}`. Exit code refleja pass.
    - **Espejo exacto** de `lib/verified/validate-regions.ts` (Fase C, #11). Un fixture
      de tests compartido entre ambos para que no divergan.

15. **`.github/workflows/verify.yml`** (EDIT) — ⚠️ **NO es un gate**
    Nuevo step **"Validate regions (pre-flight)"** justo después de `Prepare run`
    (línea ~54) y **antes** del primer gate (`Gate · Available`, línea ~81).
    - `if: steps.m.outputs.regions_source == 'tool'` (si el BED es legacy de STRhub,
      no se valida — nosotros lo hicimos bien).
    - **SIN `continue-on-error`**: si falla, el job aborta ahí. No se corren gates, no
      se genera reporte ni badge. El log explica qué filas están fuera de panel.
    - Racional: un BED fuera de panel es un input inválido, no una tool defectuosa.
      Publicar un reporte en rojo sería difamatorio e incorrecto.

16. **`harness/report.py` + `harness/generate_pdf.py`** (EDIT)
    - Sección 7 ("Verification Data"): distinguir provenance del BED:
      "Regions BED: provided by tool owner (covers M of N supported loci)" vs
      "provided by STRhub".
    - Sección 7: agregar explícitamente que el dataset es un **slice** alrededor de N
      loci forenses, no un genoma entero — hoy el reporte no lo dice y es información
      material para quien lea la atestación.
    - Sección 11 "No bundled demo data" → reflejar que el dueño aportó el BED.
    - **NO** agregar fila de gate "Regions valid" a la Verification Matrix (ver #15:
      si el BED no valida, no hay reporte).

---

## Orden de ejecución recomendado

```
A (loci panel)  →  B (contrato schema/manifest)  →  D12+D13 (harness baja+valida)
                                                  →  D14 (wire en CI)
                                                  →  C (form web)
                                                  →  D15 (reporte)
```

Razón: A es el insumo de todo. B+D se pueden testear con un manifest escrito a mano
(sin tocar la web todavía). C es lo último porque depende de que el contrato (B) ya
exista y esté probado end-to-end por CLI.

## Esfuerzo estimado

- **Fase A:** ~medio día (sobre todo derivar coords autosómicas correctas).
- **Fase B:** ~2-3 h (patrón ya existe).
- **Fase C:** ~1 día (el grueso de UI/i18n).
- **Fase D:** ~1 día (validador + wiring CI + reporte).

Total ~3 días enfocados. Sin reescrituras: todo extiende patrones existentes.

## Riesgos / decisiones abiertas

- **Contención vs overlap:** ¿el BED del dueño debe estar *contenido* en la ventana
  ±1000bp, o basta con *overlapar*? Recomiendo overlap (más permisivo; el gate de
  output igual atrapa BEDs inservibles).
- **`min_loci` por panel:** ¿5 fijo, o por dataset? Dejarlo en dataset.yml (flexible).
- **Naming de cromosomas:** los slices son `chrY`/`chr*` (hg38 UCSC). Un BED con `Y`
  en vez de `chrY` es un error *recuperable*: normalizar el prefijo `chr` en el
  validador en vez de rechazar. Mismo criterio en TS y Python.
- **Legacy:** las tools ya verificadas con asset BED siguen funcionando (precedencia
  mantiene el fallback). No hay que migrar nada retroactivo.
- **Duplicación TS/Python:** la lógica de validación vive dos veces (web + harness).
  Es deliberado (la web necesita feedback instantáneo sin CI). Mitigación: fixture de
  tests compartido; si diverge, el harness manda.
```
