# STRhub Verified — Handoff de sesión (2026-09-30)

Documento para arrancar una conversación nueva, en Claude Code o en cualquier agente, sin
volver a discutir el alcance ni repetir los errores que esta sesión corrigió.

Dos repos: `strhub-verified` (engine/harness) y `strhub-web` (sitio Next.js, producción
strhub.app). Los dos son públicos.

**Rama de trabajo: `plan/unamended-procedure` en `strhub-verified`. Nada pusheado. `main`
intacto.** Estado al cerrar: harness `235 passed, 1 skipped`; web `275 passed` y `tsc --noEmit`
limpio. **Tanda 1 cerrada** (ver sección 7).

Los cuatro documentos que manda leer antes de tocar código:

- [PLAN-Unamended-Procedure.md](PLAN-Unamended-Procedure.md) — la regla: una corrida enmendada
  no es un resultado.
- [PLAN-Paso-1.md](PLAN-Paso-1.md) — el orden: primero la documentación, y solo si corre entra
  el pipeline forense.
- [GUIA-PASO-1.md](GUIA-PASO-1.md) — el contrato de cuatro bloques que se le pide al commit.
  Está en inglés porque es lo que el informe público enlaza.
- Este handoff — el estado real del código y la cola de trabajo.

---

## 1. La pregunta que la fase 1 contesta, y ninguna otra

Fijada antes de correr:

> En el commit `C` del repositorio público `R`, ¿un tercero puede instalar y ejecutar la
> herramienta de principio a fin siguiendo únicamente un procedimiento que ese commit enuncia,
> y obtener el archivo de salida que ese procedimiento nombra?

No contesta si el genotipo es correcto, si la herramienta sirve para casework, ni si *nosotros*
podemos hacerla correr. El destinatario del informe es un revisor de *Forensic Science
International: Genetics* que tiene que poder repetir la lectura sin hablar con nosotros.

---

## 2. Los errores que esta sesión corrigió

Esta es la sección que evita repetir el ciclo. La auditoría encontró que el motor tenía cinco
mecanismos que forzaban el verde. Ninguno era malicioso: cada uno nació de querer que más
herramientas compilaran.

1. **Plan B contado como éxito del commit.** Si el commit fijado no compilaba, el workflow
   construía `Dockerfile.fallback` (imagen de Docker Hub o paquete de Bioconda) y el veredicto
   seguía siendo `runs`. Eso valida una imagen vieja, no el commit del paper.
2. **Reescritura del comando citado.** `propose_manifest.py` recortaba los corchetes de una
   sinopsis, inyectaba flags que aparecían en otro párrafo (`--bam-samps`), colapsaba
   `a.bam,b.bam` a un archivo y cambiaba el tipo de entrada cuando STRhub no tenía la muestra.
3. **Adivinanzas auto-confirmadas.** Si se adivinaba el layout del BED o el tipo de entrada y
   el proceso dejaba cualquier archivo, `verdict.py` borraba la limitación y publicaba `runs`.
   El éxito bajo una adivinanza no convalida la premisa.
4. **Rescate por el ejemplo del repositorio.** `produced = (runs e io) o example`: si la corrida
   sobre la muestra de referencia fallaba pero el quick start dejaba un archivo, salía `runs`.
5. **Inflación del badge.** `recipe.origin: proposed` se mapeaba a `documented`, y la compuerta
   de contenido subía el verde a `brightgreen`. Un revisor que ve un verde más fuerte lee una
   validación analítica, y la fase 1 no la hace.

### El extremo opuesto también es un error

El primer intento de corregir esto fue tratar cualquier Dockerfile escrito por STRhub como
enmienda ilegítima. Probado contra las 23 del benchmark, dejó **una** herramienta ejecutable.
Eso también es falso: si el repositorio dice cómo se instala (`Makefile`, `CMakeLists.txt`,
`environment.yml`, `setup.py`, un script), empaquetar esas mismas líneas en un contenedor es el
trabajo legítimo de la plataforma, no una receta nuestra.

La distinción quedó fijada en `harness/procedure.py`:

```python
CITABLE_INSTALL   = {"dockerfile", "release_binary"}
PACKABLE_FROM_REPO = CITABLE_INSTALL | {
    "conda", "pip", "cmake", "make", "autotools", "cargo", "go", "r", "nim", "script",
}
PUBLISHED_INSTALL = {"docker_image", "bioconda"}   # es una afirmación sobre la imagen, no sobre el commit
```

**Empaquetar lo que el repo declara es legítimo. Inventar lo que el repo no declara no lo es.**

### Cómo trabajar, para no volver a forzar

- No se agregan parches por herramienta para que compile (el `PATH` de straglr, el
  `CONDA_PREFIX` de vamos, el Python 3.11 por NanoRepeat son exactamente las enmiendas que este
  plan retira). Si no compila con lo que el commit dice, el resultado es que no compila.
- No se agrega un plan B, un `|| true`, un entrypoint reemplazado ni una flag de conveniencia
  para llegar al final.
- Antes de `docker build`, la afirmación, las citas y la tabla de sustituciones ya están
  escritas. Nada de lo que se observe después agrega un paso ni borra una limitación.
- Falta de datos no es falla de la herramienta. Si nos faltan los slices de esas coordenadas o
  el repo no trae el archivo de ejemplo, se dice eso, con esa palabra.
- Un desacuerdo entre el clasificador y `expected.json` se resuelve antes de correr Docker, no
  se publica.
- Nada se pushea a `main`. Cada tanda se mira en la página local (`http://127.0.0.1:8765/`)
  antes de pasar a la siguiente.
- Sin em-dashes en la prosa de reportes y documentos. Es un delator de texto generado. Las
  celdas vacías `—` de las tablas se mantienen.

---

## 3. El modelo de dos pasos

El orden cambió: la pregunta del panel forense deja de ser la primera.

| Paso | Qué se ejecuta | Qué no se ejecuta |
|---|---|---|
| **1. Ejecución documentada** | Las líneas de instalación citadas, sin una línea más. El comando citado, sobre los archivos que ese comando ya nombra. | Dockerfile generado, plan B, flags agregadas o sacadas, BED adivinado, la muestra de STRhub en lugar de la del comando. |
| **2. Pipeline forense STRhub** | La muestra de referencia (hg38, panel CODIS y expandido), el archivo de regiones que la guía del panel ya registra, la compuerta de contenido. | Cualquier cosa si el paso 1 no terminó. El paso 2 nunca se usa para conseguir un verde del paso 1. |

Si el paso 1 termina, el informe abre con "así como está documentado, corre" y el pipeline va
en otra sección. Si el paso 2 no se puede hacer porque no tenemos la muestra de ese tipo, esa
sección lo dice y el titular del paso 1 queda como está.

---

## 4. Las tres frases

Las mismas en la tarjeta, el informe, el certificado, el PDF, el índice y la página local.
Ninguna dice que la herramienta no funciona.

**Corre** (instalación citada ejecutada, exit 0, y el archivo de salida que el comando nombra
existe y no está vacío):

> Así como está documentado, corre.
>
> Un tercero instaló y corrió el comando que el commit escribe, y apareció el archivo de salida
> que ese comando nombra. No dice nada sobre genotipos ni sobre el panel forense.

**No corre** (se ejecutó el procedimiento sin enmendar y se detuvo):

> Así como está documentado, no corre.
>
> Eso no significa que la herramienta no funcione. Significa que un tercero, siguiendo el README
> en este commit, no llegó al final. Corregí la documentación o el paso que se rompió, y volvé a
> probar con el link.

**No se puede saber** (no hay instalación copiable, no hay comando, el comando es una sinopsis,
o no nombra la entrada o la salida):

> Así como está documentado, un tercero no puede saber cómo correrla.
>
> No se ejecutó nada. Eso no significa que la herramienta no funcione: en este primer paso falta
> en el README lo que la guía pide. Cuando esté, volvé a probar con el link.

Debajo de las dos últimas va la lista de lo que falta, un ítem por bloque de la guía, con el
enlace a `docs/GUIA-PASO-1.md`. El reintento es otro link sobre un commit nuevo. No hay una
receta de STRhub que tape el hueco.

---

## 5. Estado del código

### Hecho en esta sesión

| Archivo | Qué hace |
|---|---|
| `harness/procedure.py` (nuevo) | Clasifica el procedimiento antes de Docker, puro (sin red, sin Docker). Devuelve `may_say_runs`, `basis` (`tool` / `strhub` / `recipe`), `blocker`, `reason` y la lista de `amendments`. Lo leen el veredicto y la página local. |
| `harness/verdict.py` | Se retiraron los tres rescates: `fallback_used` ya no pone `runs` en el commit, el ejemplo del repo ya no salva la corrida de datos, y una limitación presente antes de correr sigue presente si hubo salida. |
| `harness/certificate_text.py` | Titulares y colores: se sacó la inflación a `brightgreen` por la compuerta de contenido. |
| `harness/preview_server.py` (nuevo) | Servidor local offline en `127.0.0.1:8765`. Clasifica las 23 del benchmark y muestra de quién sería el fallo. No construye imágenes y no publica nada. |
| `harness/tests/test_procedure.py` (nuevo), `test_verdict.py` | Tests de la regla. Suite completa en verde. |
| `docs/PLAN-Unamended-Procedure.md`, `docs/PLAN-Paso-1.md` (nuevos) | Los dos planes de diseño. |

Tanda 1, cerrada después:

| Archivo | Qué hace |
|---|---|
| `docs/GUIA-PASO-1.md` (nuevo) | El contrato de cuatro bloques: instalación copiable, un comando, la entrada declarada, la salida declarada. Con ejemplos de lo que cuenta y lo que no, las tres frases, y el cuarto caso que es nuestro. |
| `harness/certificate_text.py` | `step1_says(report)` devuelve las tres frases más el bloque de la guía que falta, derivado de `procedure.blocker`. `STEP1_BLOCKERS` dice, para cada freno, qué bloque señala y **de quién es el hueco**: `commit` es un hallazgo de documentación, `strhub` es nuestro y no se cuenta como hueco del autor. `missing` viaja como clave (`command`), no como texto. |
| `harness/report.py` | `report["step1"]` en el JSON, y el resumen markdown abre con la frase del paso 1 antes del veredicto. |
| `harness/claims.py` | Las dos frases nuevas registradas con su fuente (`gates` y `readme`). El guardián de claims obliga a esto y es el mejor control que tiene el repo. |
| `harness/tests/test_step1.py` (nuevo) | Cada freno del commit mapea a un bloque nombrado; una limitación nuestra no se cuenta como hueco del autor; ninguna frase dice que la herramienta no funciona salvo dentro de la oración que lo niega; un procedimiento enmendado con las compuertas en verde no sale como `fails` ni como `runs`. |
| `strhub-web`: `lib/i18n/locales/{es,en,pt}/verified.ts` | Bloque `step1` con los cuatro titulares, los cuatro párrafos, los nombres de los bloques y los encabezados de paso 1 y paso 2. |
| `strhub-web`: `lib/verified/step1.ts`, `types/verified.ts`, `lib/verified/step1.test.ts` (nuevos) | `step1For()` traduce el bloque del engine. El test lee los archivos de locale reales, así que una clave faltante falla ahí y no en una página, y verifica en los tres idiomas que ninguna frase diga que la herramienta no funciona. |

| `harness/trial_fixtures.py` (nuevo) | 14 trials en disco para el lector de fixtures de la web (`VERIFIED_TRIAL_FIXTURE_DIR`). Cada escenario declara solo lo observado (compuertas, freno) y el texto lo produce el motor. Cada uno declara su `expect`: si el clasificador no coincide, no escribe nada y falla. |
| `strhub-web`: `components/verified/verified-trial.tsx` | Renderiza el bloque del paso 1 arriba del veredicto, con el enlace a la guía cuando no corre. |

**El bug que encontraron los fixtures.** Una sinopsis recortada y una salida sin nombre salían
como *"la limitación es nuestra"*, cuando el plan las pone entre los huecos del commit. La causa
era de precedencia: `step1_says` dejaba que `verdict.basis == "strhub"` pisara el mapa de bloques.
Las dos cosas son ciertas a la vez y no se contradicen: **recortar** la sinopsis sería una enmienda
nuestra, y por eso el clasificador marca la enmienda como nuestra; pero lo que el autor puede
corregir es que el commit no enuncia un comando. Ahora el freno decide y `basis` solo entra cuando
el freno es uno que la tabla no conoce. Está fijado en `test_step1.py`.

**Una redacción que quedó pendiente.** En el caso de la sinopsis, la razón del veredicto dice
*"optional arguments were dropped rather than run as written"*, en pasado, cuando en realidad no se
ejecutó nada. Es honesta sobre la propuesta pero puede leerse como que corrimos algo. Candidata a
reescribir en la tanda 2.

**Dos decisiones de la tanda 1 que conviene no revertir sin pensarlo.** `headline()` sigue
devolviendo el rótulo corto (*Runs as documented*, *Could not be determined*) porque el badge de
shields necesita una línea corta: las tres frases viven en `step1`, que es el titular del informe.
Y `badge.ts` quedó sin tocar por la misma razón. Lo que falta para que esto se vea es la parte de
render: ningún componente de la web ni `generate_pdf.py` imprime todavía el bloque `step1`.

### Lo que falta, y es la razón por la que todavía no se publica nada

| Archivo | Qué le falta |
|---|---|
| `.github/workflows/verify.yml` | **No consulta `procedure` en ningún lado.** Sigue construyendo `Dockerfile.fallback` cuando el build del commit falla (líneas ~524, ~590). Es el agujero principal. |
| `harness/propose_manifest.py` | Llama al clasificador, pero todavía inyecta y saca flags, adivina el layout del BED y emite Dockerfile de plantilla. |
| `harness/preview_server.py` | Muestra la clasificación con la voz vieja (panel primero), sin las tres frases del paso 1. |
| `harness/generate_pdf.py` y los componentes de `strhub-web` | Los textos y el helper existen, pero nadie **renderiza** el bloque `step1` todavía: ni el PDF, ni la página del informe, ni la de la prueba. |

---

## 6. Los números del benchmark, al 30/09/2026

Corriendo `procedure.classify` offline sobre las 23 herramientas fijadas:

- **6 de 23 entran al paso 1 hoy**: gangstr (`cmake`), hipstr (`make`), nanorepeat (`pip`),
  straitrazor (`make`), strsearch (`dockerfile`), strspy (`conda`).
- **13 de 23 entrarían tras la tanda 2**, cuando el paso 1 deje de exigir que STRhub tenga la
  muestra. Se suman las 5 de `missing_input` (lusstr, mpsproto, strique, tandem-genotypes,
  trtools), expansionhunter (`loci_outside_panel`) y trgt (`input_not_substituted`).
- **6 desacuerdos con la lectura a mano de `expected.json`**, y son la cola de trabajo
  prioritaria porque al menos tres son defectos nuestros, no de esos repositorios:

| Herramienta | Freno | Por qué es nuestro |
|---|---|---|
| strkit | `flag_dropped` | Le sacamos flags al comando citado. |
| longtr | `flag_injected` | Le agregamos flags que la cita no tiene. |
| fdstools | `no_command` | No encontramos comando, y la lectura a mano dice que se puede correr. |
| strling | `regions_guessed` | Adivinamos el layout del BED. |
| straglr | `synopsis_trimmed` | Lo único que hay es una sinopsis. Puede ser hallazgo real de documentación. |
| repeathmm | `output_unnamed` | La documentación no nombra la salida. Puede ser hallazgo real. |

Los que quedan en gris por documentación: lobstr y stretch (`no_command`), vamos
(`missing_file`), expansionhunterdenovo (`regions_guessed`).

Reproducir estos números:

```bash
cd strhub-verified
python3 - <<'PY'
import json, sys, collections
sys.path.insert(0, "harness")
import benchmark_recipes as br
rows = []
for spec in br.rows():
    name = spec["name"]
    exp = json.loads((br.BENCH / name / "expected.json").read_text())
    try:
        _p, recipe = br.propose(name)
        rev = recipe["procedure"]
    except Exception as e:
        rev = {"blocker": f"validator_error: {e}", "install_method": ""}
    rows.append((name, rev.get("blocker"), rev.get("install_method"),
                 bool(exp["runnable_on_strhub_data"]["value"])))
for k, v in collections.Counter(r[1] for r in rows).most_common():
    print(f"{v:3d}  {k}")
PY
```

---

## 7. Plan de ejecución: cuatro tandas

Sobre `plan/unamended-procedure`, en este orden. Cada tanda se mira en la página local antes de
la siguiente.

### Tanda 1 — La guía y las tres frases. No cambia qué se ejecuta. CERRADA

Lo que queda de esta tanda es solo render: imprimir `report["step1"]` en el PDF, en la página del
informe y en la de la prueba, con los encabezados **Paso 1** y **Paso 2** que los locales ya
traen. Para el detalle de lo hecho, la segunda tabla de la sección 5.

1. Escribir `docs/GUIA-PASO-1.md` con los cuatro bloques que el motor acepta, y ninguno más:
   - **Instalación copiable.** Un bloque de código con los comandos y las versiones. Vale el
     Dockerfile del propio commit, el binario del release que el bloque manda bajar, o las
     líneas del bloque (`conda env create -f environment.yml`, `pip install .`, `make`). No vale
     prosa que haya que interpretar.
   - **Un comando.** El de una sola muestra, en bloque de código, sin corchetes de sinopsis.
   - **La entrada.** El archivo que ese comando nombra, y una línea que diga el tipo (BAM,
     FASTQ u otro). El archivo está en el commit o es un placeholder explícito
     (`<archivo.bam>`, `path/to/x.bam`).
   - **La salida.** El archivo que ese comando escribe, con el nombre.
2. `certificate_text.headline` y `verdict.py` pasan a las tres frases, leyendo
   `procedure.blocker`. El párrafo nombra el bloque de la guía que falta, con la misma palabra
   que usa la guía, **no** el puntaje por palabras de `check_readme.py` (buscar `install` o
   `bam` en un README no ejecuta nada y deja de presentarse como si dijera si alcanza).
3. Las mismas claves en `strhub-web/lib/i18n/locales/{es,en,pt}/verified.ts` y en
   `lib/verified/badge.ts`.
4. Tests: ningún texto de `undetermined` contiene "la herramienta no funciona"; un `fails` de un
   procedimiento enmendado no se publica como `fails`.

### Tanda 2 — El paso 1 deja de pedir el panel

1. `procedure.classify` marca `ready` con instalación copiable, comando que no es sinopsis,
   entrada nombrada y salida nombrada, **sin exigir que STRhub tenga esa muestra**.
2. `input_not_substituted` deja de frenar el paso 1: los archivos del propio comando son el
   ensayo (esto libera trgt).
3. Arreglar el proposer para que no saque ni agregue flags (strkit, longtr).
4. Revisar por qué fdstools queda sin comando detectado.
5. `regions_guessed` sigue siendo freno declarado (strling, expansionhunterdenovo).
6. `preview_server.py` pasa a mostrar la frase del paso 1 y el bloque de la guía que falta.
7. Resolver los 6 desacuerdos: cada uno es un bug del lector o una corrección de
   `expected.json`.

### Tanda 3 — Correr el paso 1, y el pipeline solo después

Única tanda que toca Docker y CI.

1. En `verify.yml`, si el procedimiento no es `ready`: no se construye Dockerfile de plantilla,
   no se dispara la pierna externa, no corre Content.
2. Si es `ready`, se ejecutan las líneas citadas y el comando citado. El exit code y el archivo
   de salida nombrado deciden "corre" o "no corre".
3. Retirar el build de `Dockerfile.fallback` como camino al veredicto. El resultado de un commit
   que no compila es que no compila. La imagen publicada puede informarse como otro renglón, y
   ese renglón no escribe `verdict.code`.
4. Las piernas del pipeline forense se arman solo cuando el paso 1 terminó.
5. Si no tenemos la muestra de ese tipo, el paso 2 dice que no se hizo.

### Tanda 4 — El reintento y el recuadro para el revisor

1. El certificado abre con el recuadro de método, armado de campos y no de prosa libre:
   afirmación, procedimiento citado (archivo, línea, texto, URL), condiciones de ensayo
   (muestra, genoma, montajes, tiempo, memoria), enmiendas, resultado (exit code, ruta de salida
   citada, si estaba vacía, log a un clic), y qué no se afirma.
2. El informe y la página enlazan la guía y dicen que el próximo intento es un commit nuevo. No
   hay formulario para que STRhub escriba el Dockerfile.
3. Recorrer lo ya publicado como *Runs as documented* sobre receta generada y pisar la misma
   URL, con la lápida del titular anterior (`withdrawn: the executed procedure was amended`).
   No se borra nada.
4. Ensayo local con Docker en cuatro casos: compila y corre (hipstr o gangstr), falla
   documentado (strspy), falta la muestra (trtools), falta el bloque de instalación (lobstr).

---

## 8. Comandos

```bash
cd strhub-verified
git branch --show-current                 # plan/unamended-procedure

python3 -m pytest harness/tests -q        # 238 passed, 1 skipped
python3 harness/preview_server.py         # http://127.0.0.1:8765/  (offline, no publica nada)
python3 harness/trial_fixtures.py         # 14 trials en .trial-fixtures, e imprime las URLs

cd ../strhub-web
npx vitest run                            # 275 passed
npx tsc --noEmit                          # limpio

# La página de resultado, sin GitHub. WATCHPACK_POLLING evita que el watcher de
# macOS agote los file descriptors; si /verified da 404, borrá .next primero.
WATCHPACK_POLLING=true \
  VERIFIED_TRIAL_FIXTURE_DIR=../strhub-verified/.trial-fixtures npx next dev -p 3100
```

**Por qué un despacho real no sale de un dev server, y no hay que "arreglarlo".** Tres capas
independientes. El dev server no tiene DNS a `api.github.com` si corre en sandbox. `assertWritable`
en `strhub-web/lib/verified/github.ts` se niega a despachar contra el engine de producción desde un
proceso que no es producción, y ese guardián existe por un incidente real: un smoke test del submit
commiteó un directorio de tool, fue aprobado, corrió y publicó una atestación de software que no
existía. Y el workflow vive en `main`, así que una corrida real no traería nada de esta rama. Para
un end-to-end de verdad hace falta un repo engine de prueba y `VERIFIED_ENGINE_REPO` apuntado ahí.

**El formulario sí funciona en local, contra los fixtures.** `startFixtureTrial` en
`strhub-web/lib/verified/trial.ts` resuelve el submit desde los trials en disco cuando
`VERIFIED_TRIAL_FIXTURE_DIR` está seteado y no es producción, antes de resolver el ref, así que no
necesita red. **Solo empareja por repositorio y solo contra un fixture que ya existe**: un
repositorio desconocido cae al camino real y recibe el error real, porque inventar un resultado para
un repositorio que nadie corrió es justamente lo que este proyecto viene a sacar, y sería peor en la
herramienta que demuestra la regla. Los repos que el formulario acepta son los de los 14 escenarios;
el que quedó con dos (`unique379r/strspy`) resuelve siempre al mismo por orden alfabético de id y
avisa por consola cuál es el otro. El ref que escribas no se respeta: el fixture está fijado a su
commit.

---

## 9. Hecho cuando

- La página local muestra, para cada herramienta del benchmark, una de las tres frases y, si
  falta algo, el bloque de la guía.
- Ninguna frase dice que la herramienta no funciona.
- Una corrida con Dockerfile generado, plan B o salida `**/*` no puede quedar en "así como está
  documentado, corre".
- Content y la muestra de STRhub no se ejecutan si el paso 1 no terminó.
- `python3 -m pytest harness/tests -q` pasa, incluidos los tests de las tres frases.

Párrafo para el paper, estable porque sale de los mismos campos:

> We tested whether a third party can install and run the tool at the pinned commit by following
> only a procedure stated in that commit, on a declared public reference sample. A step we added
> or altered was recorded as an amendment and excluded the result from "runs as documented". We
> did not assess genotype accuracy, concordance, or fitness for casework.
