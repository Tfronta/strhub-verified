# STRhub Verified — Handoff de sesión (2026-07-20)

Resumen para arrancar una conversación nueva con contexto. Dos repos:
`Validacion-Softwares-NGS/strhub-verified` (engine/harness) y `.../strhub-web` (sitio Next.js).
Producción: **strhub.app**. Ambos repos son **públicos** (GitHub Actions gratis/ilimitado).

---

## Qué es STRhub Verified

Atestación **automática, fechada, anclada a un commit y reproducible** de que una tool
forense de STR **instala, corre end-to-end y produce output con estructura válida** en un
entorno limpio. Nivel de claim: *"Runs + Output Structure Validation"*. **NO** afirma
exactitud de genotipos ni aptitud para casework (fuera de scope, sin truth set).

Nació de las preocupaciones de reproducibilidad de la usuaria (Tamara) sobre **STRspy** —
ella reportó bugs a mano en issues #12 y #14 del repo oficial.

---

## Lo construido en esta sesión (TODO MERGEADO A MAIN)

### Feature 1 — BED provisto por el dueño (self-service para tools por coordenadas)
Motivo: los datasets de STRhub son **slices**, no genomas enteros. Antes STRhub armaba el
BED a mano para cada tool (HipSTR, GangSTR). Ahora el dueño lo provee.

- **Paneles de loci soportados** (`datasets/<type>/loci.bed`, 5-col con min_depth), generados
  por `harness/build_panel.py` desde la COBERTURA REAL del BAM (ventana ±1000bp con ≥10x en
  toda la ventana). Autosómico=24 loci, Y=14 loci.
  - **DYS385a EXCLUIDO del panel Y**: colapso palindrómico a/b en el alineamiento GIAB deja
    la copia `a` a 2-10x. No es artefacto de slicing. Visible en el reporte HipSTR (depth 34).
  - Candidatos de coords viven en `datasets/<type>/str_candidates.bed` (NO en assets de tools).
- **Contrato**: `inputs.regions` en el manifest. Forma final = **UPLOAD** del BED
  (`{path, provided_by:'author'}`), no puntero a repo. Motivo del pivote: HipSTR publica su
  referencia como .gz de 78MB genome-wide tras URL /raw/ — "cada tool es un mundo, imposible
  soportar todas". El dueño sube el archivo; STRhub lo commitea en `tools/<slug>/assets/`.
- **Validación dos capas**: web (rechazo inline antes de despachar) + harness pre-flight
  (aborta el workflow SIN generar reporte — un BED fuera de panel NO es fallo de la tool).
- **Advertencia "panel sin convertir"**: si el usuario sube NUESTRO panel tal cual (col4 =
  nombres de loci nuestros), advertencia no bloqueante. No podemos validar el formato de cada
  tool (imposible), pero SÍ detectar nuestro propio archivo devuelto.
- **Detección de gzip** por magic bytes (1f 8b) con mensaje claro.
- **Panel ONT: BLOQUEADO** — faltan coords hg38 de DXS8378, DXS7132, AMEL, AMEL_Y.
  Solo afecta a tools que usen `ont-bam-hg38` con regions (STRspy NO lo usa, trae su DB).

### Feature 2 — Reporte honesto de errores (nace de STRspy)
Descubrimiento clave: STRspy **corre pero falla en silencio en 9 loci** (cannot_open, por su
DB rota — bugs #12/#14 horneados en el zip). El gate IO pasaba con output parcial y el badge
salía verde limpio.

- **Badge**: si hay diagnósticos `severity: error`, pasa a **amarillo** + "(errors reported)".
  Warnings NO lo tocan (ej. too_few_reads = cobertura del slice, es warning).
- **diagnose_log.py**: antes descartaba todo menos el primer match por regla (sub-reportaba
  9 loci como 1). Ahora lleva `count` + `examples` distintos, con limpieza de comillas.
- **Sección "Errors Reported During the Run"** (PDF §9 + HTML + markdown + WEB): tabla
  "What happened / Times / Affected" con los loci legibles (paths recortados a su token
  variable: `vWA_input.bam... → vWA`). El revisor forense ve "vWA, TPOX, FGA" sin abrir un log.
- **Caveat honesto del leg external**: si el error es del leg external (nuestro slice), agrega
  "pueden reflejar la cobertura de la muestra, no la tool" + **recomendación de incluir demo
  data en el repo**. Errores del leg own (dato del autor) NO llevan caveat.
- **Línea que NO cruzamos**: nada sobre exactitud de genotipos (necesita truth set; los
  genotipos ONT/Illumina de Tamara están validados con HipSTR, no con CE → circular).
  Descartamos auto-poblar `expect_loci` desde el panel por ser benchmarking-adjacent.

### Feature 3 — Guard de deploy y pulido
- `verify.yml`: **deploy solo si `github.ref == 'refs/heads/main'`**. Un dispatch desde rama
  de prueba NO publica a strhub.app (gh-pages ES producción).
- Bug cazado en CI: los steps de reporte tienen `if: always()` → sobrevivían al abort del
  pre-flight y emitían un badge rojo fantasma. Ahora guardados contra `steps.preflight.conclusion`.
- **Sin em-dashes** en la prosa de reportes (delator de IA). Celdas vacías "—" se mantienen.
- Fix web: tag de panel ONT ya no dice "Autosomal STR" (nueva label "ONT CODIS").

---

## Estado actual concreto

- **PRs**: engine #1-5 y web #2-5 TODOS MERGEADOS. Cero abiertos.
- **STRspy publicado**: `strhub.app/verified/strspy-v2-0-ont` — badge amarillo, 9 loci, caveat.
  - ⚠️ Ese reporte se generó ANTES del merge de em-dashes (#5 engine) → su dataset name aún
    muestra "ONT — hg38". Se corrige al re-correr STRspy. El fix web de errores ya aplica
    (es render, no necesita re-run), pero requiere que el deploy de web #5 esté live.
- **HipSTR Y**: re-verificado y publicado limpio (13 loci, DYS385_1 excluido).

## Pendiente / deuda

1. **Re-correr STRspy** para que el reporte publicado tome el fix de em-dashes (dataset name).
2. **Limpiar ramas de prueba** (locales + remotas): `test/owner-bed`, `test/strspy-report`,
   `test/strspy-run`, y las `feat/*` ya mergeadas.
3. **Slugs STRspy duplicados**: existe `tools/strspy` (hand-crafted, sin publicar) y
   `tools/strspy-v2-0-ont` (del form, publicado). Decidir si unificar/borrar uno.
4. **Commits duplicados** de la submission de STRspy en main (`add strspy-v2-0-ont` ×2) —
   revisar si el form permite re-enviar un pending dos veces (posible bug).
5. **Panel ONT** bloqueado por 4 coordenadas faltantes.
6. **Labels del dropdown del form** (`Illumina BAM (hg38) — Y-STR`) aún con em-dash (UI, no
   reporte — menor).
7. **Idea futura no implementada**: atar el `run` al entry point documentado del README
   (para que un manifest no reemplace el camino documentado por un atajo). Se investigó:
   NO aplica a STRspy (su README documenta y recomienda el script core que usamos).

## Cómo aprobar un repo nuevo en el form
Panel admin: `strhub.app/admin` (login: `ADMIN_USERNAME`/`ADMIN_PASSWORD`, env vars del
deploy) → `strhub.app/admin/dashboard` → sección pending → botón aprobar. Aprobar
auto-dispara la corrida (no hace falta re-enviar). Nota de seguridad: `JWT_SECRET` tiene
default inseguro — verificar que esté seteado en prod.

## STRspy — hallazgos técnicos (para el relato/paper de Tamara)
- El repo OFICIAL (`unique379r/strspy` @ `dafdee7e`, HEAD de hoy) **falla en 9 loci CODIS**:
  D10S1248, D12S391, D13S317, D5S818, D7S820, D8S1179, FGA, TPOX, vWA.
- El "fix" del mantenedor es **cosmético**: el commit "Fix output file naming..." arregló el
  script BuildDB pero **el zip de la DB que los usuarios reciben es byte-idéntico desde
  2026-04-06** (blob `75ca2875ce`) — nunca lo regeneró. Por eso sigue roto.
- El fork de Tamara (`Tfronta/strspy`) SÍ tiene los fixes + una DB corregida
  (`db-v2/STRspy2.0-DB-fixed/` con los 52 .fa bien nombrados, vWA regenerado). Pero el
  mantenedor no acepta PRs, así que el oficial no se beneficia.
- La atestación pública prueba, reproducible y sin correr nada local, que el oficial falla.

## Archivos/utilidades clave
- `harness/build_panel.py` — genera loci.bed desde cobertura real (`--check` guarda drift).
- `harness/validate_bed.py` — valida BED (cols 1-3, agnóstico al formato).
- `harness/diagnose_log.py` — reglas de diagnóstico + `summarize()` + `external_leg_notes()`.
- `harness/report.py` / `harness/generate_pdf.py` — render MD/HTML / PDF.
- `strhub-web/lib/verified/validate-regions.ts` — espejo TS del validador + panel/unconverted.
- `strhub-web/lib/verified/diagnostics.ts` — espejo TS del resumen de errores para la web.
- `PLAN-Owner-Provided-BED.md` — plan detallado de la Feature 1.

## Convenciones (memoria del proyecto)
- Commits: usar `git-commit "msg"` (no raw git commit). `git push` inmediato tras commit.
- main de ambos repos = PRODUCCIÓN (deploya live). Branchear siempre antes de tocar.
- El entorno limpia procesos background entre turnos (venv de /tmp, dev servers) — re-crear.
