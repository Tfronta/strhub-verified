# Plan: el paso 1 es la documentación, y solo si corre entra el pipeline

Escrito el 30 de septiembre de 2026. Acota
[PLAN-Unamended-Procedure.md](PLAN-Unamended-Procedure.md): la pregunta del
panel forense deja de ser la primera. La primera es si un tercero puede
correr la herramienta como el commit la documenta.

Se trabaja en la rama local `plan/unamended-procedure`. Nada se pushea a
`main` hasta que la página de prueba, en `http://127.0.0.1:8765/`, muestre
las dos frases de abajo y no un verde armado por STRhub.

## Las dos preguntas, en este orden

**Paso 1.** En el commit fijado, ¿un tercero puede instalar y correr la
herramienta siguiendo solo lo que ese commit escribe, sobre los archivos que
el propio comando nombra, y obtener el archivo de salida que el comando
nombra?

**Paso 2.** Recién si el paso 1 terminó: la corrida sobre el pipeline de
STRhub (la muestra de referencia, el archivo de regiones, la compuerta de
contenido). El paso 2 no cambia el titular del paso 1.

El paso 1 no pide la muestra de STRhub, ni un BED inventado, ni un Dockerfile
generado. Si para llegar al final hay que agregar un paso que el commit no
tiene, el paso 1 no se corre.

## Las dos frases

El titular es corto. Debajo va el párrafo, igual en la tarjeta, el informe,
el certificado y la página de prueba. Ninguna frase dice que la herramienta
no funciona.

**Se ejecutó lo documentado y no terminó** (`fails`, y el procedimiento no
estaba enmendado):

> Así como está documentado, no corre.
>
> Eso no significa que la herramienta no funcione. Significa que un tercero,
> siguiendo el README en este commit, no llegó al final. Corregí la
> documentación o el paso que se rompió, y volvé a probar con el link.

**El commit no alcanza para ejecutar** (`undetermined`: no hay instalación
copiable, no hay comando, el comando es una sinopsis, no nombra la entrada o
no nombra la salida):

> Así como está documentado, un tercero no puede saber cómo correrla.
>
> No se ejecutó nada. Eso no significa que la herramienta no funcione: en
> este primer paso falta en el README lo que la guía pide. Cuando esté,
> volvé a probar con el link.

Debajo de las dos, la lista de lo que falta, un ítem por bloque de la guía, y
el enlace a la guía. El reintento es otro link, sobre el commit nuevo. No hay
una receta de STRhub que tape el hueco.

El verde del paso 1 dice solo esto:

> Así como está documentado, corre.
>
> Un tercero instaló y corrió el comando que el commit escribe, y apareció el
> archivo de salida que ese comando nombra. No dice nada sobre genotipos ni
> sobre el panel forense.

## La guía es el contrato de la máquina

Un documento corto para quien mantiene la herramienta,
`docs/GUIA-PASO-1.md`. Pide cuatro bloques, los mismos que el motor acepta, y
ninguno más. El chequeo por palabras de `harness/check_readme.py` no es este
contrato: buscar `install` o `bam` no ejecuta nada, y deja de presentarse
como si dijera si el README alcanza.

1. **Instalación copiable.** Un bloque de código con los comandos, y las
   versiones. Vale el Dockerfile del propio commit, el binario del release
   que el bloque manda bajar, o las líneas del bloque (`conda env create -f
   environment.yml`, `pip install .`, `make`). No vale una prosa que haya
   que interpretar.
2. **Un comando.** El de una sola muestra, en un bloque de código, sin
   corchetes de sinopsis (`[opcional]` no es un comando).
3. **La entrada.** El archivo que ese comando nombra, y una línea que diga
   el tipo (BAM, FASTQ u otro). El archivo tiene que estar en el commit o
   ser un placeholder explícito (`<archivo.bam>`, `path/to/x.bam`).
4. **La salida.** El archivo que ese comando escribe, con el nombre.

Cada ítem que falte se nombra en el informe con la misma palabra que en la
guía, para que corregir y volver a probar sea seguir la lista.

## Qué corre en cada paso

| Paso | Qué se ejecuta | Qué no se ejecuta |
|---|---|---|
| 1 | Las líneas de instalación citadas, sin una línea más. El comando citado, sobre los archivos que ya nombra. | Dockerfile generado, plan B, flags agregadas o sacadas, BED adivinado, muestra de STRhub en lugar de la del comando. |
| 2 | La muestra de referencia, el archivo de regiones que la guía del panel ya registra, la compuerta de contenido. | Cualquier cosa si el paso 1 no terminó. El paso 2 no se usa para conseguir un verde del paso 1. |

Si el paso 1 termina, el informe abre con “así como está documentado, corre” y
después, en otra sección, el resultado del pipeline. Si el pipeline no tiene
la muestra de ese tipo, esa sección dice que el paso 2 no se hizo, y el
titular del paso 1 queda.

## Tandas

Sobre `plan/unamended-procedure`, en este orden. Cada tanda se mira en la
página local antes de la siguiente.

**Tanda 1 — la guía y las dos frases, sin cambiar qué se ejecuta.**
`docs/GUIA-PASO-1.md` con los cuatro bloques. `certificate_text.headline` y
`verdict.py` dejan de decir *Runs as documented* / *Could not be determined*
como única voz: el titular y el párrafo son las tres frases de arriba
(corre / no corre / no se puede saber). Las mismas claves en
`strhub-web/lib/i18n/locales/{es,en,pt}/verified.ts` y en `badge.ts`. El
párrafo nombra el bloque que falta, tomado de `procedure.blocker`, no del
puntaje de `check_readme.py`. Test: un `undetermined` no contiene “la
herramienta no funciona”; un `fails` de un procedimiento enmendado no se
publica como `fails`.

**Tanda 2 — el paso 1 deja de pedir el panel.** `procedure.classify` marca
`ready` cuando hay instalación copiable, un comando que no es sinopsis, una
entrada nombrada y una salida nombrada. No hace falta que STRhub tenga esa
muestra. `input_not_substituted` deja de ser un freno del paso 1: los
archivos del propio comando son el ensayo. Siguen siendo freno, y caen en
“no se puede saber”: sinopsis recortada, flags agregadas o sacadas, entorno
generado, imagen publicada contada como el commit, salida `**/*`. La página
`harness/preview_server.py` pasa a mostrar la frase del paso 1 y el bloque
que falta. Sobre las 23 del benchmark se anota, a mano, cuántas quedan en
cada frase; un desacuerdo con `expected.json` se muestra como hoy, en
naranja, y es del lector, no de la herramienta.

**Tanda 3 — correr el paso 1, y el pipeline solo después.** En `verify.yml`,
si el procedimiento no es `ready`, no se construye un Dockerfile de plantilla
y no se dispara la pierna externa ni Content. Si es `ready`, se ejecutan las
líneas citadas y el comando citado; el exit y el archivo de salida nombrado
deciden “corre” o “no corre”. Solo con “corre” se arman las piernas del
pipeline que ya existen. El plan B no corre. El ejemplo del repositorio no
salva una corrida que no se hizo: en el paso 1 el ejemplo *es* la corrida,
porque usa los archivos del comando.

**Tanda 4 — el reintento.** El informe y la página de prueba enlazan la guía
y dicen que el próximo link es un commit nuevo. No se ofrece un formulario
para que STRhub escriba el Dockerfile. Un maintainer que igual quiera el
paso 2 con un archivo que el commit no trae lo declara, y esa corrida sale
como paso 2, sin tocar el titular del paso 1.

## Hecho cuando

- La página local muestra, para cada herramienta del benchmark, una de las
  tres frases y, si falta algo, el bloque de la guía.
- Ninguna frase dice que la herramienta no funciona.
- Una corrida con Dockerfile generado, plan B o salida `**/*` no puede quedar
  en “así como está documentado, corre”.
- Content y la muestra de STRhub no se ejecutan si el paso 1 no terminó.
- `python3 -m pytest harness/tests -q` pasa, incluidos los tests de las dos
  frases.
