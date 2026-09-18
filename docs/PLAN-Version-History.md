# Plan: el historial de una herramienta, por versión

Escrito el 18 de septiembre de 2026, a partir de dos cosas que aparecieron el mismo día.

## Los dos problemas

**1. Publicar pisa.** Desde que hay un slug estable por herramienta (PR #33) y un trial desde URL publica solo cuando su verdict es de la herramienta (PR #36), el catálogo tiene una entrada `hipstr`, y cada corrida que publica escribe `hipstr.json` encima de la anterior. Eso es lo que se quería para el refresh mensual y para un release nuevo. Pero el form acepta cualquier commit — *"Version, tag or commit"*, y el hint dice que se puede cambiar — y nada compara: si alguien verifica desde `strhub.app` el primer commit de STRspy v2, y el verdict es `runs` o `fails`, ese resultado reemplaza al vigente con el de un commit más viejo. Sin guarda, invitar a probar versiones anteriores es invitar a romper el catálogo.

**2. La pregunta real es sobre versiones.** Quien revisa un paper tiene una versión citada. Quien mantiene la herramienta quiere saber si el commit anterior al fix se rompía donde el usuario dijo, y si el posterior ya no. Quien escribe la nota técnica quiere mostrar la serie: STRspy en el primer commit de v2 se detiene en el wrapper; después de los issues el autor agrega cosas y "mejora", y sigue rompiendo más adelante. Hoy eso son N corridas del form, anotadas a mano, en trials que expiran a los 30 días. Y las verificaciones viejas que sí están publicadas (`hipstr-v0-7`, `hipstr-b2033bf`, `straitrazor-v3-0`…) son slugs sueltos de antes de la consolidación, que la tarjeta lista como "6 verification runs" sin decir cuál es más nueva.

Los dos tienen la misma respuesta: la unidad publicada no es "la herramienta" sino **"la herramienta en un commit"**, y la página de la herramienta es la lista de esos commits.

## Las decisiones

1. **Dos relojes.** La fecha del commit (`source.committed`, la del committer, la que muestra GitHub) es la línea de tiempo *del software* y es la que ordena: lo más nuevo arriba. La fecha de verificación (`generated`) es cuándo tomamos la foto, y va en cada fila. Verificar hoy v2.0 cae abajo, donde pertenece, y la fila dice *verified 2026-09-18*.

2. **Una fila por commit, con la última verificación de ese commit.** El refresh mensual re-verifica el mismo commit: actualiza la fila. Que el mismo commit pasara en junio y falle en septiembre (una dependencia que se pudrió) es un dato interesante que esta estructura *permite* guardar; no se guarda todavía (ver "Después").

3. **La tarjeta del catálogo y el badge son la fila de arriba**: el commit más nuevo verificado, que casi siempre es el último release porque el form lo precarga. Con eso el problema 1 desaparece sin código de guarda: un commit viejo publicado después aparece abajo, y no toca ni la tarjeta ni el badge ni `hipstr.json`.

4. **Release y commit suelto no se distinguen en el orden.** Si alguien verifica el head de `master` después de v2.5, queda arriba y la tarjeta dice `12e989b` en vez de `v2.5`. Es lo honesto — es el estado más nuevo que conocemos — y es lo que ya pasa hoy con `hipstr`.

5. **La línea de tiempo es por repositorio; cada fila lleva su variante.** La tarjeta ya agrupa por repositorio (`hipstr` y `hipstr-y` son la misma herramienta con dos paneles). Las filas del mismo commit con distinta variante quedan juntas.

6. **`committed` sale de la llamada que ya hacemos.** `upstream.check` compara el ref fijado contra la rama por defecto; la respuesta de `compare` trae `base_commit.commit.committer.date`. Cero llamadas nuevas para una corrida normal. Un informe sin `committed` (los publicados antes de este plan) se ordena por `generated` *debajo* de los que lo tienen, y el deploy le rellena la fecha la primera vez que lo mueve al layout nuevo.

## La forma en gh-pages

Hoy: `hipstr.json`, `hipstr.html`, `hipstr.pdf`, `hipstr.badge.json`, `hipstr.summary.md`, `hipstr.log-*.txt` en la raíz, y `index.json` con una entrada por archivo.

Después:

```
hipstr.json, hipstr.html, hipstr.pdf, hipstr.badge.json, …   ← alias: el commit más nuevo (sin cambios para la web, el badge, shields)
hipstr/12e989be4a8f9ab59f0c4c5da3784b82018cac82/hipstr.json, hipstr.html, hipstr.pdf, hipstr.log-*.txt, …
hipstr/b2033bf…/hipstr.json, …
index.json  (schema /3): cada tool como hoy (= el alias) + committed + versions: [{sha, version, committed, generated, level, label, verdict, errors_reported, report, page, pdf}], la más nueva primero
```

Los archivos de una corrida **no cambian de nombre**: van a un directorio por commit. Así los links relativos de la copia HTML (`hipstr.log-external.txt`, `hipstr.json`) y los nombres de log dentro del JSON siguen valiendo dentro de su directorio, y la web resuelve los logs relativos a la página, como ya hace. El SHA completo en el directorio (sin ambigüedad); la web acorta a 7 en la URL (`/verified/hipstr?at=12e989b`) y lo resuelve contra `versions`.

El alias se decide en un solo lugar, `harness/publish_layout.py`, puro y con tests: dado el árbol de gh-pages y el `reports/` de la corrida, deja la corrida en `<slug>/<sha>/`, elige el commit más nuevo entre los directorios de ese slug, y copia ese conjunto a la raíz. Las reglas que lo sostienen:

- un commit más nuevo publicado después **se vuelve** el alias;
- un commit más viejo publicado después **no lo mueve**;
- el mismo commit re-verificado reemplaza su directorio (y el alias, si es el más nuevo);
- un conjunto que hoy está en la raíz sin directorio (lo publicado antes de este plan) se pliega primero a su directorio, con `committed` rellenado por la API si falta, y compite en igualdad;
- nunca se borra un directorio de commit.

## Tandas

**Tanda 1 — engine ✅ hecha el 18 de septiembre.** `source.committed` en el informe (de `upstream.check`, sin llamada nueva; `upstream.commit_date` para rellenarlo a un informe viejo); `harness/publish_layout.py` con sus ocho tests; `build_index` escribe `versions` (schema /3, entradas planas intactas para `pick_tools`, `upstream_refresh` y la web actual); el paso de deploy llama a `publish_layout` en vez del `cp` plano. Sin cambio visible en la web hasta la tanda 2, salvo que un commit viejo ya no pisa.

Probado en seco sobre un clon de gh-pages con el trial real de GangSTR: el informe (del engine viejo, sin `committed`) recibió su fecha por la API y quedó en `gangstr/e368b9f…/`; un segundo informe del mismo slug en `6ea9b2b` — el commit que fija la receta commiteada — resultó ser **más nuevo** (abril de 2021 contra enero) y se llevó el alias. Lo que muestra que la fecha la tiene que decir GitHub, no la etiqueta: `v2.5` es la más vieja de las dos.

**Tanda 2 — web ✅ hecha el 18 de septiembre (Tfronta/strhub-web#41).** `/verified/<slug>?at=<sha>` muestra una fila vieja (mismo cuerpo de informe; el PDF, la copia HTML y los logs resuelven dentro de `<slug>/<sha>/`), y abre con un aviso — *"You are reading an older commit"* — que nombra el más nuevo de su tipo. En la página de la herramienta, *"Verified at these versions"*: versión · commit · fecha del commit · panel · resultado · verificado el, la fila leída marcada. La tarjeta del catálogo lista las mismas filas y su badge es el del commit más nuevo. *"Test another version"* abre el form con el repo cargado; el hint dice que cualquier tag o commit vale.

Dos precisiones que salieron al hacerla. *"Más nuevo" es por tipo* (misma herramienta, mismo panel): la corrida Y-STR de un commit viejo sigue siendo la corrida Y-STR más nueva, y el aviso compara dentro del tipo. Y *plegar los slugs viejos exige saber qué es una versión y qué es un kit*: `hipstr-v0-7` y `hipstr-b2033bf` son una verificación listada dos veces, pero `strait-razor-ForenSeqv1.27` y `strait-razor-PowerSeqv2.31` en el mismo commit son dos — solo se recorta del slug la versión que el propio informe declara. La tanda 3 retira los slugs viejos y con ellos esa heurística.

**Tanda 3 — migración, a mano y una vez ✅ el script, 18 de septiembre; la corrida, después del merge de #39.** `harness/migrate_layout.py`: una **tabla**, no una heurística — cada slug viejo de gh-pages con el slug bajo el que esa verificación se archiva hoy (el de su receta en `tools/`, o el que le tocaría a un trial desde su URL: `straitrazor` para las dos corridas genéricas de STRait Razor; los dos kits conservan los suyos, porque un kit es otra verificación). Cada conjunto pasa a `<slug>/<sha>/` con sus archivos renombrados por dentro y por fuera (los nombres de log en el JSON, los links y el slug en la copia HTML y el resumen; el PDF queda como se escribió); de dos conjuntos del mismo commit se conserva el que tiene etiqueta de versión y no un sha pelado (`hipstr-v0-7` sobre `hipstr-b2033bf`, `straitrazor-v3-0` sobre `strait-razor-b618e93`) y el otro se borra; `committed` se pide a la API; los alias se reescriben al commit más nuevo; un slug con la forma vieja que la tabla no conoce se reporta y no se toca. Sin `--apply` imprime el plan y no cambia nada; correrlo dos veces es inocuo. Ocho tests.

Ensayado con `--apply` sobre un clon (sin push): 12 entradas → 8 herramientas, 9 directorios de commit, 34 archivos sueltos borrados. Y un hallazgo que el catálogo de hoy esconde: para HipSTR, `b2033bf` (v0.7, mayo de 2021) es **más nuevo** que `12e989b` (abril de 2020) — la corrida que hoy encabeza `hipstr` es de un commit más viejo que el v0.7 verificado en septiembre. Después de la migración la tarjeta dice v0.7, que es la verdad.

Para correrla, en este orden: mergear #39 (el deploy tiene que publicar por commit antes, o la próxima corrida pisaría el alias con un archivo suelto), clonar `gh-pages`, `python harness/migrate_layout.py site` y leer el plan, `--apply`, `build_index.py`, revisar `git status`, commit y push. Las instrucciones están en el docstring del script.

**Tanda 4 — el experimento, que es también un test ✅ el mecanismo y el primer caso, 18 de septiembre; la primera corrida, después del merge.** Pares (repo, commit, resultado esperado) sacados de issues reales: en el commit anterior al fix tiene que detenerse donde el usuario dijo, con el diagnóstico que lo nombra; en el posterior, no. Es `test_truth.py` con historia real en vez de snapshots, y no puede correr en el CI de cada PR (Docker, minutos por par): un `workflow_dispatch` aparte, *history check*, que corre los pares y falla si alguno no da lo esperado. Su salida es el material de la nota técnica, y la mejor evidencia de que Verified encuentra lo que la gente encuentra.

Cómo quedó. Los casos viven en `history/<slug>.yml`: un commit, una etiqueta, el *porqué* (qué issue lo documenta) y la expectativa — `verdict`, `level`, diagnósticos que tienen que aparecer (o no), y un texto que el log tiene que contener (o no). `harness/history_check.py` los despacha como trials del workflow de verificación, espera las corridas por el id que llevan en el nombre, baja los artifacts y sostiene cada resultado contra su expectativa, nombrando cada afirmación que falla; `history-check.yml` encadena los tres pasos y deja la tabla en el resumen de la corrida. Ocho tests.

**Dos instrumentos, porque ven bugs distintos.** `committed` re-apunta la receta commiteada de `tools/<slug>/` al commit: entorno curado, nunca publica, y como llama al script directamente no pasa por el wrapper. `proposed` corre lo que correría un usuario nuevo — la receta que el engine lee del repositorio *en ese commit*, comando del README incluido — y publica en los términos de siempre, así que cada commit que corre entra en el historial como la fila que es. Fue decisión mirar STRspy: el bug 1 (el wrapper comprueba nombres de v1.1 y sale con *"please make sure you are in the same directory"*) solo lo ve `proposed`; los bugs 2-5 (la base de datos) solo los ve una corrida que llegue al script, o sea `committed`.

**El primer caso, `history/strspy-ont.yml`**: STRspy v2.0 a través de los issues #12 (24 de marzo, cuatro bugs) y #14 (21 de abril, cinco), en cinco commits de la rama `STRspy2.0`: `e069e19` (v2.0 recién publicada, 21 de febrero: sin base de datos precompilada, wrapper roto), `4ee9f7c` (6 de abril, la respuesta del autor a #12 — *"all other bugs have been addressed"* — con la base precompilada; #14 encontró los cinco bugs todavía ahí), `f7e0897` (4 de mayo, el wrapper arreglado: bug 1 cerrado), `dafdee7` (4 de mayo, BuildDB arreglado: bugs 2-4 cerrados, bug 5 abierto — lo que el catálogo verificó el 15 de septiembre, con 18 loci cuyo alineamiento no puede abrir, que es exactamente el bug 5). Las expectativas están escritas desde los issues, no desde corridas: la primera corrida es la calibración, y donde no coincidan la tabla lo dice.

Para correrlo: el workflow tiene que estar en `main` (un `workflow_dispatch` nuevo no se puede lanzar desde una rama), y después `gh workflow run history-check.yml -f cases=history/strspy-ont.yml`. Cinco trials en paralelo, del orden de media hora. Los dos casos `proposed` publican, si el verdict es de la herramienta, como filas viejas del historial de `strspy-ont`.

Lo que dejé fuera a propósito: el fork con los cinco fixes (`Tfronta/strspy@STRspy2.0`). Un trial desde su URL se archivaría bajo `strspy-ont` — el slug sale del nombre, no del repositorio — y mezclaría el historial del fork con el del upstream. Antes de sumar forks hace falta que el slug (o al menos el historial) distinga el repositorio.

## Después, y fuera de alcance

- **Los trials del refresh de releases no entran al historial.** `upstream_refresh` despacha trials *con receta* (la commiteada, re-apuntada al release nuevo), y un trial con receta nunca publica — la barrera de seguridad de PR #36. Hoy esos resultados quedan en el artifact. Que un release nuevo entre solo al historial necesita otra barrera (la receta viene de `tools/<slug>/` en `main`, no de quien despachó): tanda propia.
- **Mismo commit, distinto resultado en el tiempo.** Guardar `<slug>/<sha>/history/<fecha>.json` en vez de reemplazar. Cuando haga falta.
- **Comparar dos filas.** Qué gate cambió, qué diagnóstico apareció o desapareció entre dos commits. Es la vista que la nota técnica escribiría a mano; después de la tanda 2 se ve si vale la pena hacerla automática.
