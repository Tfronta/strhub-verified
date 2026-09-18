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

**Tanda 2 — web.** `/verified/<slug>?at=<sha>` muestra una fila vieja (mismo cuerpo de informe). En la página de la herramienta, *"Verified at other versions"*: versión · commit · fecha del commit · verdict/nivel · verificado el · link, la vigente marcada. La tarjeta del catálogo ordena su lista desplegable por fecha de commit. En cada resultado, *"Test another version"* abre el form con el repo cargado y el foco en el commit; el hint del form dice en una línea que cualquier tag o commit vale — el que cita el paper, o uno anterior, para ver qué cambió.

**Tanda 3 — migración, a mano y una vez.** Los slugs sueltos de antes de la consolidación (`hipstr-v0-7`, `hipstr-b2033bf`, `hipstr-v0-7-y`, `hipstr-b2033bf-y`, `strait-razor-b618e93`, `straitrazor-v3-0`, `strsearch-c70179b`) se pliegan a `<slug consolidado>/<sha>/`, con `committed` rellenado; los duplicados (mismo commit dos veces: `hipstr-v0-7` y `hipstr-b2033bf` son los dos `b2033bf`) quedan en uno; los archivos sueltos de la raíz se borran. Un script, revisado, corrido una vez.

**Tanda 4 — el experimento, que es también un test.** Pares (repo, commit, resultado esperado) sacados de issues reales: en el commit anterior al fix tiene que detenerse donde el usuario dijo, con el diagnóstico que lo nombra; en el posterior, no. Es `test_truth.py` con historia real en vez de snapshots, y no puede correr en el CI de cada PR (Docker, minutos por par): un `workflow_dispatch` aparte, *history check*, que corre los pares y falla si alguno no da lo esperado. Su salida es el material de la nota técnica, y la mejor evidencia de que Verified encuentra lo que la gente encuentra.

## Después, y fuera de alcance

- **Los trials del refresh de releases no entran al historial.** `upstream_refresh` despacha trials *con receta* (la commiteada, re-apuntada al release nuevo), y un trial con receta nunca publica — la barrera de seguridad de PR #36. Hoy esos resultados quedan en el artifact. Que un release nuevo entre solo al historial necesita otra barrera (la receta viene de `tools/<slug>/` en `main`, no de quien despachó): tanda propia.
- **Mismo commit, distinto resultado en el tiempo.** Guardar `<slug>/<sha>/history/<fecha>.json` en vez de reemplazar. Cuando haga falta.
- **Comparar dos filas.** Qué gate cambió, qué diagnóstico apareció o desapareció entre dos commits. Es la vista que la nota técnica escribiría a mano; después de la tanda 2 se ve si vale la pena hacerla automática.
