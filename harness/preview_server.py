"""Local preview of the unamended-procedure rule. Nothing is published and
nothing is built.

    python harness/preview_server.py

Opens a page on 127.0.0.1 that classifies every pinned benchmark tool, offline,
into the three answers a reviewer needs before spending a Docker run:

  - STRhub does not hold the input, so a failure would be ours
  - the only way to run it would amend the procedure, so a failure would be ours
  - the commit states the install and we hold the input, so a failure would be
    the tool's

A repository URL is not fetched. The page is the benchmark, which is the set
of tools the engine is measured against.
"""
from __future__ import annotations

import html
import json
import pathlib
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import benchmark_recipes as br  # noqa: E402

HOST = "127.0.0.1"
PORT = 8765

LEAD = {
    "ready": ("Se puede correr",
              "El repo trae la instalación y STRhub tiene la muestra. El contenedor es el empaque de esa instalación. Si el comando no termina, el fallo es de lo que está documentado.",
              "tool"),
    "missing_input": ("No correr: falta la muestra",
                      "STRhub no tiene un dato del tipo que este procedimiento lee. No se ejecutó nada. Un fallo no sería de la herramienta.",
                      "ours"),
    "input_not_substituted": ("No correr: el comando no apunta a nuestra muestra",
                              "Sigue nombrando los archivos del ejemplo del repositorio. Correrlo no es el ensayo sobre la muestra de referencia, y un 'file not found' sería nuestro.",
                              "ours"),
    "flag_dropped": ("No publicar: se sacarían flags del comando citado",
                     "El comando que correría no es el citado: le faltan flags que la documentación pone.",
                     "ours"),
    "missing_file": ("No correr: falta un archivo",
                     "El comando citado lee un archivo que no está en el commit ni en STRhub. No se ejecutó. El fallo sería nuestro.",
                     "ours"),
    "loci_outside_panel": ("No correr: los loci no están en la muestra",
                           "El catálogo del repositorio no cae en el panel de la muestra de referencia. Correrlo no diría nada de la herramienta.",
                           "ours"),
    "no_command": ("No hay comando citado",
                   "En el commit no hay una línea que invoque la herramienta. No se puede atribuir un fallo.",
                   "unstated"),
    "no_install_procedure": ("No hay instalación citada",
                             "El commit no enuncia un procedimiento de instalación que un tercero pueda ejecutar.",
                             "unstated"),
    "published_image": ("La imagen no es el commit",
                        "Lo que está citado es una imagen o un paquete publicado. Eso no demuestra que este commit corre, y no se cuenta como si lo hiciera.",
                        "ours"),
    "input_swapped": ("No publicar: cambiaríamos el tipo de entrada",
                      "La documentación nombra un tipo de dato y STRhub le daría otro, porque no tiene el primero.",
                      "ours"),
    "input_guessed": ("No publicar: el tipo de entrada es una adivinanza",
                      "Ninguna frase dice qué lee la herramienta. Un archivo de salida no convierte la adivinanza en un hecho.",
                      "ours"),
    "regions_guessed": ("No publicar: el archivo de regiones es nuestro",
                       "Habría que inventar el layout del BED. Si con eso aparece un archivo, no queda confirmado que era el layout correcto.",
                       "ours"),
    "output_unnamed": ("No publicar: no está nombrada la salida",
                       "Cualquier archivo que el wrapper copie contaría como salida documentada. Eso no se acepta como resultado.",
                       "ours"),
    "synopsis_trimmed": ("No publicar: se recortó el comando",
                         "Lo único encontrado es una sinopsis de uso. Tirar los argumentos opcionales es enmendar el comando.",
                         "ours"),
    "flag_injected": ("No publicar: se agregarían flags",
                      "El comando que correría lleva flags que la cita no tiene.",
                      "ours"),
    "input_list_collapsed": ("No publicar: se achicó la lista de entradas",
                             "Una lista de archivos se redujo a uno. Es otro ensayo.",
                             "ours"),
    "ssh_rewritten": ("No publicar: se reescribiría el build",
                      "Un paso baja dependencias por SSH y STRhub lo pasaría a HTTPS.",
                      "ours"),
}


def _load() -> list[dict]:
    rows = []
    for spec in br.rows():
        name = spec["name"]
        expected = json.loads((br.BENCH / name / "expected.json").read_text())
        try:
            _proposal, recipe = br.propose(name)
            review = recipe["procedure"]
            error = ""
        except Exception as exc:  # noqa: BLE001
            review = {"blocker": "validator_error", "amendments": [], "install_method": "",
                      "input_type": "", "may_say_runs": False, "reason": str(exc),
                      "citable_install": False, "output_glob": ""}
            error = f"{type(exc).__name__}: {exc}"
        rows.append({"name": name, "set": spec["set"], "repo": spec["repo"], "sha": spec["sha"],
                     "review": review, "error": error,
                     "expected_runnable": bool(expected["runnable_on_strhub_data"]["value"]),
                     "expected_type": expected["input"].get("strhub_type"),
                     "expected_methods": expected["install"]["acceptable_methods"],
                     "expected_program": expected["program"].get("value")})
    return rows


def _esc(value) -> str:
    return html.escape("" if value is None else str(value))


def _page(rows: list[dict]) -> str:
    counts = {"tool": 0, "ours": 0, "unstated": 0, "error": 0}
    body = []
    for row in rows:
        review = row["review"]
        blocker = review.get("blocker") or "validator_error"
        if row["error"]:
            title, sentence, kind = ("Error del validador", row["error"], "error")
        else:
            title, sentence, kind = LEAD.get(blocker, ("Sin clasificar", review.get("reason") or "", "error"))
        counts[kind] = counts.get(kind, 0) + 1
        amends = "".join(f"<li>{_esc(a.get('what'))}</li>" for a in review.get("amendments") or [])
        disagree = ""
        if not row["error"] and row["expected_runnable"] and blocker != "ready":
            disagree = ("<p class=\"warn\">La lectura a mano del benchmark dice que esta herramienta sí se puede "
                        "correr con los datos de STRhub. Esta ficha dice que no. Esa diferencia es del lector "
                        "automático, no un fallo de la herramienta.</p>")
        elif not row["error"] and not row["expected_runnable"] and blocker == "ready":
            disagree = ("<p class=\"warn\">Esta ficha dice que se puede intentar, y la lectura a mano dice que "
                        "los datos de STRhub no alcanzan. No correr: el desacuerdo se resuelve antes de Docker.</p>")
        body.append(f"""
        <article class="{_esc(kind)}" id="{_esc(row['name'])}">
          <header>
            <h2>{_esc(row['name'])}</h2>
            <p class="tag">{_esc(title)}</p>
          </header>
          <p>{_esc(sentence)}</p>
          {disagree}
          <dl>
            <dt>Repositorio</dt><dd><code>{_esc(row['repo'])}</code> @ <code>{_esc(row['sha'][:12])}</code></dd>
            <dt>Instalación leída</dt><dd><code>{_esc(review.get('install_method'))}</code>
              {"· citable" if review.get("citable_install") else ""}</dd>
            <dt>Entrada que STRhub usaría</dt><dd><code>{_esc(review.get('input_type') or '—')}</code>
              · la documentación, leída a mano, pide <code>{_esc(row['expected_type'] or 'ninguna')}</code></dd>
            <dt>Programa documentado</dt><dd><code>{_esc(row['expected_program'] or '—')}</code></dd>
            <dt>Métodos de instalación aceptables</dt><dd><code>{_esc(", ".join(row["expected_methods"]))}</code></dd>
            <dt>¿El benchmark dice que se puede correr con los datos de STRhub?</dt>
            <dd>{"sí" if row["expected_runnable"] else "no"}</dd>
          </dl>
          {"<ul>" + amends + "</ul>" if amends else ""}
        </article>""")
    return f"""<!doctype html>
<html lang="es"><head><meta charset="utf-8"><title>STRhub · prueba local</title>
<style>
  body {{ font: 16px/1.45 system-ui, sans-serif; margin: 2rem auto; max-width: 52rem; color: #1c1917; }}
  h1 {{ font-size: 1.4rem; }}
  .note {{ background: #f5f5f4; padding: 0.8rem 1rem; border-radius: 8px; }}
  .counts {{ display: flex; gap: 1rem; padding: 0; }}
  .counts li {{ list-style: none; }}
  article {{ border-top: 1px solid #e7e5e4; padding: 1rem 0; }}
  article header {{ display: flex; justify-content: space-between; gap: 1rem; align-items: baseline; }}
  h2 {{ font-size: 1.05rem; margin: 0; }}
  .tag {{ margin: 0; font-weight: 600; }}
  .tool .tag {{ color: #166534; }}
  .ours .tag {{ color: #9a3412; }}
  .unstated .tag {{ color: #57534e; }}
  .error .tag {{ color: #991b1b; }}
  .warn {{ background: #fff7ed; padding: 0.5rem 0.7rem; border-radius: 6px; }}
  dl {{ display: grid; grid-template-columns: 16rem 1fr; gap: 0.2rem 1rem; }}
  dt {{ color: #57534e; }}
  dd {{ margin: 0; }}
  code {{ font-size: 0.9em; }}
</style></head><body>
<h1>Prueba local: ¿se puede correr con lo que hay?</h1>
<p class="note">Esto no construye imágenes y no publica nada. Verde: el repo trae cómo
instalarse y STRhub tiene la muestra, así que esa corrida entra. Naranja o gris: no
podemos armar el entorno con lo que hay en el repo, o no tenemos la muestra (por ejemplo
slices de otras coordenadas). Eso es lo que se le diría a quien mantiene la herramienta,
con la limitación concreta, para que documente el README o suba un ejemplo.</p>
<ul class="counts">
  <li>Se puede correr: {counts.get("tool", 0)}</li>
  <li>No podemos, y el motivo es nuestro: {counts.get("ours", 0)}</li>
  <li>Falta documentación para empezar: {counts.get("unstated", 0)}</li>
  <li>Error del validador: {counts.get("error", 0)}</li>
</ul>
{"".join(body)}
</body></html>"""


def main() -> None:
    rows = _load()
    page = _page(rows).encode()

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):  # noqa: N802
            if self.path not in ("/", "/index.html"):
                self.send_error(404)
                return
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(page)))
            self.end_headers()
            self.wfile.write(page)

        def log_message(self, fmt, *args):
            sys.stderr.write("%s\n" % (fmt % args))

    server = ThreadingHTTPServer((HOST, PORT), Handler)
    print(f"http://{HOST}:{PORT}/  ({len(rows)} tools, nothing published)", flush=True)
    server.serve_forever()


if __name__ == "__main__":
    main()
