# Plan: una corrida enmendada no es un resultado

El alcance de la fase 1 quedó acotado el 30 de septiembre de 2026. Este
documento sigue valiendo para la regla de no enmendar. Qué se ejecuta primero,
las dos frases y la guía están en
[PLAN-Paso-1.md](PLAN-Paso-1.md).

Escrito el 29 de septiembre de 2026, a partir de la auditoría del ensayo desde
URL. Corrige la decisión 1 de
[PLAN-Documented-Is-The-Badge.md](PLAN-Documented-Is-The-Badge.md) (18 de
septiembre): allí una receta *propuesta* cuenta como documentada, y un plan B
también. Esa decisión es la que hoy publica *Runs as documented* sobre un
Dockerfile que STRhub escribió.

Esto es el método de la fase 1. Un revisor de *Forensic Science International:
Genetics* tiene que poder leer el informe y repetir, sin hablar con nosotros,
qué se afirmó, qué se ejecutó y qué no se afirma.

## La pregunta que el informe puede contestar

Una sola, fijada antes de correr:

> En el commit `C` del repositorio público `R`, ¿un tercero puede instalar y
> ejecutar la herramienta de principio a fin siguiendo únicamente un
> procedimiento que ese commit enuncia, sobre una muestra de referencia
> declarada, y obtener una salida no vacía del tipo que ese procedimiento
> nombra?

No se contesta si el genotipo es correcto, si la herramienta sirve para
casework, ni si *nosotros* podemos hacerla correr.

## El principio

> El procedimiento que se ejecutó es la afirmación. Si un paso que corrimos no
> está citado en el commit, o lo cambiamos para que terminara, el resultado no
> puede decir que la herramienta corre como está publicada. El éxito no
> convalida la premisa.

Cuatro pruebas. Las cuatro tienen que pasar para que el titular sea *Runs as
documented*. Si una falla, el titular es otro, y el informe dice cuál.

1. **Sin enmienda.** Cada paso ejecutado es una de tres cosas: una línea
   copiada de un bloque de código citado en el commit; una sustitución de la
   tabla cerrada de condiciones de ensayo (abajo); o `git clone` y
   `git checkout` del propio commit, que es obtener el material, no un paso
   del procedimiento. Cualquier otra línea —un paquete que agregamos, un
   `PATH` reescrito, un `|| true`, una flag que no está en el comando citado,
   un entrypoint reemplazado— es una enmienda. Una enmienda vacía el titular.
2. **Fijado antes.** La afirmación, las citas y la tabla de sustituciones
   quedan escritas antes de `docker run`. Nada de lo que se observe después
   puede agregar un paso, borrar una limitación ni cambiar de qué
   procedimiento habla el titular.
3. **Atribución.** Un fallo es de la herramienta solo si falló el
   procedimiento sin enmendar. El fallo de un procedimiento enmendado, o no
   haber encontrado un procedimiento enunciado, no se publica como *Fails*.
4. **Separación.** La corrida sobre la muestra de referencia, el ejemplo del
   propio repositorio y la imagen publicada son tres afirmaciones. El éxito
   de una no cumple las otras.

Con eso, “forzar que funcione” deja de tener dónde apoyarse. No hace falta
prohibir cada parche: el parche es una enmienda, y una enmienda no tiene
titular.

## Qué se afirma, en la voz que ya exige el registro

Sigue en pie [PLAN-Claims-Need-Evidence.md](PLAN-Claims-Need-Evidence.md):
observación, cita y hallazgo no se mezclan. Aplicado al titular:

| Pieza del procedimiento | Voz | Qué puede decir el titular |
|---|---|---|
| Línea de instalación o de comando, con archivo, línea y texto al commit | Cita | “El commit enuncia este paso.” |
| Muestra, genoma, montajes, límite de tiempo, layout de regiones que puso STRhub | Observación | “Esta corrida usó estas condiciones.” Nunca “el autor documenta este archivo.” |
| Exit 0 y un archivo no vacío en la ruta que la cita nombra | Hallazgo, con el log | “El procedimiento citado terminó y escribió eso.” |
| Un Dockerfile generado, un plan B, una flag inyectada, un tipo de entrada cambiado | Nada en el titular | Puede existir como nota de exploración. No entra en la frase. |

## La tabla cerrada de sustituciones

Únicas sustituciones permitidas, y cada una queda en el informe como
condición de ensayo, no como paso del autor:

- un token que la cita misma presenta como archivo de entrada del tipo bajo
  ensayo, reemplazado por la ruta de la muestra declarada;
- un token que la cita presenta como genoma de referencia, reemplazado por el
  montaje declarado;
- un token que la cita presenta como ruta de salida, reemplazado por la ruta
  de captura;
- un placeholder explícito (`<…>`, `$VARIABLE`, `path/to/x.bam`) cuyo tipo
  identifican las palabras de la propia cita.

No están en la tabla, y por eso son enmiendas:

- borrar argumentos opcionales de una sinopsis (`[…]`): una sinopsis no es un
  comando; si es lo único que hay, no hay comando;
- colapsar `a.bam,b.bam` a un archivo: una lista de N entradas es otro
  ensayo;
- agregar `--bam-samps` u otra flag porque aparece en otro párrafo;
- cambiar el tipo de entrada porque STRhub no tiene muestra del tipo citado;
- adivinar un layout de regiones y, si sale un archivo, dar la adivinanza
  por confirmada;
- reescribir `git@github.com:` a HTTPS dentro del build del autor;
- `git submodule update || true`, o un `|| true` que trague un paso;
- reemplazar el `ENTRYPOINT` del Dockerfile del autor para inyectar un
  comando distinto del que la cita dice correr.

El wrapper que copia archivos puede seguir existiendo para el log. Un
archivo que el wrapper encontró no es la salida. La salida es la ruta que
la cita nombra. Si la cita no nombra salida, el hallazgo es solo el exit 0,
y el titular no dice “produjo su salida documentada”. El glob `**/*` no es
un formato documentado.

## Tres afirmaciones, tres resultados

Ninguna rescata a otra.

**A. El commit, tal como está enunciado.** La única que puede decir *Runs as
documented*. El instalador es uno de estos, citado:

- el Dockerfile del propio commit, construido tal cual, con el contexto que
  sus propias líneas `COPY` exigen;
- la imagen que una línea citada nombra, y entonces la afirmación es sobre
  *esa imagen*, no sobre el commit (ver abajo);
- el binario del release que la documentación citada manda bajar, adjunto al
  tag que resuelve a este commit, con el digest que GitHub registra;
- una transcripción literal: los comandos de instalación de un bloque citado,
  sin una línea más, en la base que esos comandos nombran (`conda env create
  -f environment.yml` vale si la cita dice crear el entorno desde ese
  archivo y el archivo está en el árbol).

Si no hay ninguno: *Could not be determined: this commit does not state an
install procedure a third party can execute.* No se genera un Dockerfile
para salir del paso. `generate_dockerfile` deja de alimentar el titular. Los
parches por herramienta (PATH de straglr, `CONDA_PREFIX` de vamos, Python
3.11 por NanoRepeat) no se siguen acumulando: cada uno es la enmienda que
este plan retira.

**B. La imagen publicada.** Si el README cita una imagen y el build del
commit falla, hoy el workflow construye el plan B y el veredicto sigue siendo
`runs`. Eso se parte. El resultado del commit es que no compiló. El
resultado de la imagen es otro renglón: se bajó la imagen citada y se dice
qué pasó, con la frase que ya existe (*the pinned commit does not build*).
Ese renglón no cambia el código de veredicto del commit a `runs`. Una imagen
no es el commit: contiene lo que alguien empujó por última vez.

**C. El ejemplo del repositorio.** Sigue siendo la pregunta del revisor sobre
el quick start, y se informa aparte. Hoy `verdict._decide` pone `runs` si la
pierna de datos falló y el ejemplo dejó un archivo. Eso se va. Un ejemplo
que escribió un archivo no cumple la afirmación A.

La wiki no está en el commit. Un comando leído solo de la wiki puede
informarse como “la wiki, leída el día D, dice…”. No puede ser el
procedimiento de la afirmación A.

## El titular, y nada más

Una frase, la misma en tarjeta, badge, HTML, PDF e índice. El peldaño de la
escalera queda debajo, como ya quedó en la tanda 5c.

| Condición | Titular | Color |
|---|---|---|
| Afirmación A, sin enmiendas, exit 0, y la salida citada existe y no está vacía | Runs as documented | verde |
| Igual, y el log de la herramienta reporta error | Runs as documented (errors reported) | amarillo |
| Afirmación A ejecutada, y se detuvo en la instalación, en la corrida o sin la salida citada | Does not run as documented: stops at … | rojo |
| No hay procedimiento enunciado, o el único procedimiento disponible está enmendado | Could not be determined | gris |
| El runner no puede dar lo que el procedimiento citado pide (GPU, GUI, licencia, red, otro SO) | Out of scope | gris |
| La corrida es una receta de STRhub o del mantenedor que no es la cita | Not verified as documented | gris |

El verde no se aclara a brightgreen por la compuerta Content. “La salida
parece genotipos” es una anotación estructural en el cuerpo del informe, con
el descargo de que no es exactitud. Un revisor que ve un verde más fuerte
lee una validación analítica. La fase 1 no la hace.

*Runs as documented (errors reported)* se queda: el proceso terminó y el log
dijo error. Es un hecho del log, no una enmienda.

## Qué deja de decidir el éxito

En `verdict.py`, estas ramas contradicen la prueba 2 y se retiran:

- borrar `regions_format_guessed` o `input_type_guessed` porque hubo salida;
- `produced = (runs e io) o example`;
- `fallback_used` con código `runs`.

Si antes de correr había una adivinanza, después de correr sigue habiéndola,
y con ella el titular no es *Runs as documented*. El éxito bajo una
adivinanza es una observación (“con un BED de cuatro columnas el proceso
escribió un archivo”), no una confirmación.

En `certificate_text.instrument_of`, `recipe.origin: proposed` hoy devuelve
`documented`, y `documented` es lo que el badge puede sostener. Pasa a
depender de la prueba 1, no del origen. Una propuesta cuyas líneas son todas
citas es documentada. Una propuesta cuyo Dockerfile lo generó
`generate_dockerfile` no lo es, aunque el origen diga `proposed`. El campo
nuevo es `procedure.amended: true|false`, con la lista de enmiendas; el
titular lo lee y no lo interpreta.

En `publish_gate.py` no cambia la idea de que un fallo de la herramienta se
publica. Cambia qué cuenta como fallo de la herramienta: solo la afirmación
A ejecutada y fallida. Un *Could not be determined* se publica como eso, que
es el hallazgo que el revisor necesita (“desde el link del paper no hay un
procedimiento ejecutable”), y el texto no puede leerse como que la
herramienta falla. Un build de plantilla que se rompe no se publica como
*Fails*.

## Lo que un revisor tiene en la primera página

El certificado abre con un recuadro de método, armado de campos, no de
prosa libre:

1. **Afirmación.** La pregunta de arriba, con `R` y `C` completos y la URL
   del commit.
2. **Procedimiento.** Cada paso: cita (archivo, línea, texto, URL) o
   “obtención del material”.
3. **Condiciones de ensayo.** Muestra (nombre, procedencia, loci que cubre),
   genoma, montajes, tiempo, memoria. Si STRhub puso el archivo de regiones,
   está acá, dicho como condición nuestra.
4. **Enmiendas.** Lista. Vacía si el titular es verde o rojo de la afirmación
   A. Si no está vacía, el titular no es *Runs as documented*.
5. **Resultado.** El titular, el exit code, la ruta de salida citada y si
   estaba vacía. El log a un clic.
6. **No se afirma.** Exactitud de genotipos, concordancia, aptitud para
   casework, que otra forma de instalarla funcionaría, que una imagen
   publicada sea este commit.

Ese recuadro es el método. El resto del informe es el detalle.

Párrafo para un paper, estable, porque sale de los mismos campos:

> We tested whether a third party can install and run the tool at the pinned
> commit by following only a procedure stated in that commit, on a declared
> public reference sample. A step we added or altered was recorded as an
> amendment and excluded the result from “runs as documented”. We did not
> assess genotype accuracy, concordance, or fitness for casework.

## Tandas

**Tanda 1 — la regla, en un solo lugar.** `procedure.amended` y la lista de
enmiendas en el informe. `headline` y `verdict._decide` leen eso y nada más:
sin las tres ramas de arriba, sin brightgreen por Content. Tests de
propiedad, cada uno con un informe mínimo: un entorno `generated` no puede
titular *Runs as documented*; `fallback_used` no puede poner `runs` en el
commit; el ejemplo en verde con la pierna de datos en rojo no puede poner
`runs`; una limitación presente antes de correr sigue presente si hubo
salida; un glob `**/*` no aprueba la compuerta de salida documentada. Esta
tanda no cambia qué se ejecuta. Cambia qué se puede decir de lo que ya se
ejecuta. El catálogo de hoy, rehecho con esta regla, va a perder verdes: es
la corrección, no una regresión.

**Tanda 2 — no enmendar para poder correr.** `propose_manifest` no emite un
Dockerfile de plantilla como procedimiento de la afirmación A. Si el método
detectado no es una de las cuatro formas citables, el ensayo termina en
*Could not be determined* antes del `docker build`, con la cita de lo que sí
se encontró (“hay un `environment.yml` y el README no dice el comando que lo
usa”, o “el README no tiene un bloque de instalación”). El plan B se corre
solo como afirmación B, en un resultado aparte, y no escribe
`verdict.code`. El entrypoint del Dockerfile del autor no se reemplaza salvo
que la cita diga correr un comando de shell. La transcripción literal se
ejecuta tal cual: si una línea falla, la instalación falló.

**Tanda 3 — el comando citado, o ninguno.** La sinopsis con corchetes no se
elige como comando. No se inyectan flags. No se cambia el tipo de entrada.
No se adivina el layout: si el comando citado pide regiones y el repositorio
trae un archivo que cae en el panel, se usa ese archivo y se cita; si no, la
condición “STRhub suministró un BED” queda en el recuadro y, por ser
enmienda de materiales que el commit no enuncia, el titular no es *Runs as
documented* salvo que la cita diga el layout y el archivo de STRhub sea ese
layout ya registrado. El archivo de regiones nuestro sigue siendo una
condición declarada, nunca un hallazgo sobre el autor.

**Tanda 4 — el recuadro y el catálogo.** El certificado, las tres copias y la
página abren con los seis puntos. Las corridas ya publicadas como *Runs as
documented* sobre receta generada se vuelven a correr con la tanda 2 y pisan
la misma URL, como en la tanda 5d: no se borran. Las que pasen a *Could not
be determined* o a *Does not run* quedan así, con el motivo en la lápida del
titular anterior (“withdrawn: the executed procedure was amended”). El piso
del benchmark que premia una receta generada “viable” se reemplaza por un
piso de rechazos honestos: una herramienta sin procedimiento citable no
puede sumar en la columna que habilita el badge.

## Qué no hace este plan

No agrega plantillas para que compilen más herramientas. Ese trabajo es el
que produjo el resultado forzado. No evalúa genotipos. No convierte un gris
en un defecto de la herramienta: el gris dice que desde el repositorio, en
ese commit, un tercero no tiene un procedimiento que ejecutar. Para el
revisor, ese gris es un resultado.
