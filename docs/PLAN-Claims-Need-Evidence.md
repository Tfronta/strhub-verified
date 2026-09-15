# Plan: una afirmación sobre la herramienta de otro necesita evidencia

Escrito el 15 de septiembre de 2026, a partir de un error real.

## El error

STRhub reportó, sobre STRspy 2.0:

> Input: the README suggests **ont-fastq** first; STRhub has reference data only as ont-bam-hg38.

El README de STRspy documenta los dos formatos y **recomienda BAM**:

> *Input either fastq (raw reads usually from ONT) or bam (pre-aligned reads by user)*
> *Tip: Its good practice to use pre-aligned bams for quicker outcomes.*

La afirmación salió de `detect_input_type`, que cuenta palabras clave: 7 menciones de fastq contra 4 de bam. Un conteo no es una lectura. El informe dijo lo contrario de la documentación que decía estar leyendo, en la voz del autor.

Lo detectó la dueña del proyecto porque conocía la herramienta. **Ese es el problema**: el sistema existe para gente que no la conoce. Con cualquier otra tool, esa frase se publicaba.

Buscando lo mismo en el resto del motor apareció un segundo caso, peor porque era incondicional:

> This tool does not include its own demo or test data.

Se imprimía para toda herramienta, mirara o no el repositorio. Es falso para STRsearch, que trae 35 archivos de ejemplo incluido `example/test_data/test.bam`.

Los dos están arreglados (PR #26). Lo que sigue es cómo evitar el tercero.

## El principio

> **Medir no es afirmar.** Una señal (un conteo, una heurística, un ranking) es evidencia de STRhub sobre su propia decisión. Una afirmación sobre la herramienta, su documentación o su autor necesita una cita: archivo, línea y texto. Sin cita, el informe describe lo que STRhub hizo, no lo que el autor documentó.

Tres voces, y no se mezclan:

| Voz | Quién responde por la frase | Ejemplo |
|---|---|---|
| **Observación** | STRhub, sobre su propia corrida | "Esta corrida usó el dato de referencia ont-bam-hg38." |
| **Cita** | el autor, textual | "El README dice: *'Its good practice to use pre-aligned bams'*." |
| **Hallazgo** | STRhub, sobre el repositorio, con evidencia adjunta | "El repositorio no trae datos de ejemplo (0 archivos en el árbol al commit `dafdee7`)." |

Hoy el motor mezcla las tres. Toda frase que hoy suene a la segunda o la tercera sin evidencia debe bajar a la primera.

## Fase A — Auditoría de afirmaciones ✅ hecha el 15 de septiembre

Se extrajeron por AST todas las cadenas de los siete módulos que llegan a un informe, un certificado o una página (`propose_manifest`, `report`, `certificate_text`, `generate_pdf`, `verdict`, `check_readme`, `diagnose_log`): **141 candidatas**, de las cuales **56 hablan en voz de hallazgo** — afirman algo sobre la herramienta, su repositorio, su documentación o su autor. Las otras 85 son observaciones sobre la propia corrida y no necesitan respaldo.

Las 56 están registradas en `harness/claims.py` con la fuente que las sostiene:

| fuente | frases | qué la sostiene |
|---|---:|---|
| `manifest` | 14 | algo que declaró el envío |
| `tree` | 9 | el árbol del repo al commit fijado |
| `readme` | 8 | texto del README al commit fijado |
| `run` | 6 | la propia configuración de STRhub |
| `gates` | 6 | el resultado de las compuertas de esta corrida |
| `log` | 5 | una línea que la herramienta imprimió |
| `strhub-table` | ~~5~~ 0 | conocimiento de STRhub — retirada, ver abajo |
| `policy` | 2 | alcance de STRhub, no afirma nada sobre la tool |
| `advice` | 1 | instrucción al lector |

Por módulo: `verdict.py` 19, `diagnose_log.py` 16, `propose_manifest.py` 9, `report.py` 7, `generate_pdf.py` 3, `certificate_text.py` 2.

**Lo que la auditoría dejó ver, y ya se corrigió.** Ninguna de las 56 quedó sin fuente, pero cinco descansaban en `strhub-table`: conocimiento nuestro presentado como hecho sobre la herramienta. Dos problemas distintos, los dos arreglados el 15 de septiembre:

- *"the tool is known to read this format"* — lo sabe **nuestra tabla** de nombres de programa, no el repositorio. Ahora: *"STRhub records the hipstr layout for a program of this name"*.
- *"the tool needs a regions file in its own format"* — la necesidad es **del dato de referencia de STRhub**, que cubre un panel de loci y no un genoma entero. Ninguna lectura del repositorio la establece. Ahora: *"this run had to supply a regions file, because STRhub's reference data covers a panel of loci"*.

Y una tercera que viajaba con ellas: el issue pre-escrito que el lector postea en el repositorio del autor afirmaba *"the repository does not ship one for hg38 covering forensic STR loci"* — nadie lo había mirado, y STRsearch trae `example/ref_test.bed`. Esa frase se fue: el borrador ahora dice qué hizo STRhub y qué le alcanzaría, sin afirmar qué le falta al repositorio.

Dichas así son **observaciones, no hallazgos**: el registro bajó de 56 a 54 entradas y `strhub-table` quedó **retirada como fuente válida**, más dos frases nuevas en la lista de prohibidas (`the tool is known to`, `the tool needs a regions file`) para que la forma no vuelva.

Las que ya estaban bien, y conviene no romper: los 16 diagnósticos de `diagnose_log` citan la línea que la herramienta imprimió, con ejemplos; los 14 de `manifest` repiten lo que el envío declaró.

## Fase B — Evidencia en el tipo de dato ✅ hecha el 15 de septiembre

`detect_recipe` emite `evidence`: una entrada por afirmación, con `kind` (`tree` / `readme`), `path`, `line` cuando la hay, el texto tal cual se leyó, y la **URL al commit fijado** (`blob/<sha>/README.md#L120`). Cubre: método de instalación, imagen publicada o paquete de Bioconda (con la línea del README que lo nombra), entorno de respaldo, comando de ejecución (la línea del README donde empieza — el joiner de bloques de código ahora conserva el número), datos de ejemplo y problemas conocidos. Viaja al informe para recetas propuestas y commiteadas, al resumen como links, y a la web (página del ensayo y del catálogo).

Lo que la sostiene es `harness/tests/test_evidence_is_real.py`: sobre los 5 repos snapshot, cada `path` citado existe en el árbol, cada línea citada existe y **dice lo citado**, cada URL es la que GitHub sirve, y la línea citada para un comando contiene ese comando. Probado corriendo la cita una línea: falla con *"command starts with './HipSTR' but README line 70 is '--fasta genome.fa'"*. Ese chequeo habría atrapado a `where:` — el texto de ayuda — citado como comando de STRspy.

La idea original era un campo por hallazgo en prosa:

```json
{ "claim": "repo_ships_no_test_data",
  "evidence": { "kind": "tree", "ref": "dafdee7", "matched": [], "searched": ["*.bam","*.fastq","*.fq"] } }
```

```json
{ "claim": "documents_bam_input",
  "evidence": { "kind": "readme_line", "file": "README.md", "line": 295,
                "text": "Tip: Its good practice to use pre-aligned bams for quicker outcomes." } }
```

La regla mecánica ("sin `evidence`, la frase no se escribe en voz de hallazgo") vive en dos capas: el registro de `claims.py` para las frases fijas del código, y `test_evidence_is_real` para los datos que cada corrida cita.

## Fase C — Leer, no contar (3 a 5 días)

Para lo que hoy se decide por frecuencia:

1. **Entradas aceptadas**: buscar enunciados explícitos ("either X or Y", "-r is input bam? (yes/no)", `INPUT_BAM`) en vez de contar menciones. Cuando el README documenta varios, el informe dice *varios* — nunca rankea uno como preferido del autor.
2. **Recomendaciones del autor**: detectar "Tip:", "recommended", "good practice", "faster" cerca de un formato, y citarlas. Si el autor recomienda algo que STRhub no puede correr, eso es un dato para el lector, no un defecto.
3. **Cuando la lectura no alcanza**: decirlo. "STRhub no pudo determinar qué entradas acepta" es una frase honesta y accionable; "el README sugiere FASTQ" es una invención.

## Fase D — La red que lo sostiene

1. **Tests de veracidad sobre los 5 repos snapshot** (pendiente). Para cada uno, una lista de afirmaciones verificadas a mano contra el repositorio real. Un cambio en las heurísticas que haga falsa una afirmación rompe el test. Es lo que faltó acá: los tests comprobaban *que* se generaba un caveat, no que fuera **cierto**.
2. **Regla de lint de afirmaciones** ✅ hecha el 15 de septiembre — `harness/tests/test_claims_have_evidence.py`, en el job `resolve` que corre antes de verificar nada:
   - toda cadena en voz de hallazgo tiene que estar en `claims.py` con su fuente; una nueva o reescrita falla con su huella y el renglón listo para registrar;
   - el registro no puede tener entradas muertas (si la frase se borró, la entrada se borra);
   - cinco **frases prohibidas** que ninguna evidencia rescata, porque ponen una preferencia o una ausencia en boca del autor: `the README suggests`, `this tool does not include its own`, `the tool prefers`, `the README recommends/wants/expects`, `is designed/intended for`;
   - un test de regresión con las dos frases que efectivamente se publicaron: hoy las dos rompen el build.
3. **Un repo nuevo al banco de pruebas** cada vez que se encuentre un error de este tipo, con el caso que lo destapó (pendiente).

## Fase E — Que el lector pueda desconfiar (2 días)

Nada de lo anterior alcanza si el lector no puede chequear:

1. **Cada hallazgo, enlazado a su evidencia** en la web: la línea del README con `#L295` al commit fijado. Un revisor abre el link y ve el texto.
2. **"¿Esto está mal?"** en la página del informe: un botón que arma un issue en `strhub-verified` con el hallazgo, la evidencia y el link. El autor de la tool y el lector son quienes más rápido detectan una afirmación falsa — hay que darles el camino, no esperar a que escriban un mail.
3. **La escalera ya dice dónde se rompió** (PR web #33): rojo donde se detuvo, gris lo que no se intentó. Mismo principio: no dejar que el lector infiera de más.

## Lo que NO propongo

- **Un modelo que lea el README.** Agrega una fuente de invención donde el problema es exactamente inventar. Las reglas deterministas se pueden auditar, testear y explicar; un modelo, no.
- **Suavizar todo a "puede que…".** Un informe lleno de hedge no sirve a nadie. La solución es afirmar menos cosas, pero afirmarlas con evidencia.

## Orden sugerido

~~A~~ → ~~D2~~ → ~~C1~~ → ~~B~~ → **D1** (tests de veracidad sobre las afirmaciones, no sólo sobre las citas) → C2/C3 → E.

A, D2 y C1 están hechas: el problema queda congelado — ninguna afirmación nueva entra sin fuente, las que se publicaron romperían el build hoy, y ya no queda ninguna frase que hable con conocimiento nuestro en voz de hecho sobre la herramienta. Lo que sigue es adjuntar la evidencia como dato (Fase B) para que el lector pueda abrirla, y los tests de veracidad (D1) que comprueben que lo afirmado es cierto y no sólo que se generó.
