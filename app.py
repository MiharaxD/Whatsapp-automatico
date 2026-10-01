"""Servidor local da agenda. Execute python app.py ou Abrir agenda.bat."""
import argparse
import base64
import binascii
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import mimetypes
from pathlib import Path
import re
import sqlite3
import threading
from urllib.parse import urlsplit
import webbrowser

from database import Store, UserError
from importing import MAX_FILE, preview_import

ROOT = Path(__file__).resolve().parent
MAX_BODY = 12 * 1024 * 1024


def make_handler(store):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, format, *args):
            # Não guardar nomes, telefones ou conteúdo das mensagens em logs.
            pass

        def local_request(self):
            return self.headers.get("Host") in (f"127.0.0.1:{self.server.server_port}",
                                                f"localhost:{self.server.server_port}")

        def respond(self, status, content, content_type="application/json; charset=utf-8"):
            if isinstance(content, (dict, list)):
                content = json.dumps(content, ensure_ascii=False).encode("utf-8")
            elif isinstance(content, str):
                content = content.encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(content)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Referrer-Policy", "no-referrer")
            self.send_header("Content-Security-Policy", "default-src 'self'; style-src 'self'; script-src 'self'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'")
            self.end_headers()
            self.wfile.write(content)

        def do_GET(self):
            if not self.local_request():
                return self.respond(403, {"error": "Acesso permitido apenas pelo endereço local."})
            path = urlsplit(self.path).path
            if path == "/api/state":
                return self.respond(200, store.state())
            files = {"/": "index.html", "/app.js": "app.js", "/styles.css": "styles.css",
                     "/favicon.svg": "favicon.svg", "/modelo.csv": "modelo.csv"}
            if path not in files:
                return self.respond(404, {"error": "Página não encontrada."})
            file = ROOT / "static" / files[path]
            mime = mimetypes.guess_type(file.name)[0] or "application/octet-stream"
            if mime.startswith("text/") or file.suffix == ".js":
                mime += "; charset=utf-8"
            return self.respond(200, file.read_bytes(), mime)

        def do_POST(self):
            if not self.local_request():
                return self.respond(403, {"error": "Endereço local inválido."})
            allowed_origins = {f"http://127.0.0.1:{self.server.server_port}",
                               f"http://localhost:{self.server.server_port}"}
            if self.headers.get("Origin") not in allowed_origins or self.headers.get("X-Local-App") != "1":
                return self.respond(403, {"error": "Abra a agenda pelo endereço local para fazer alterações."})
            if self.headers.get("Content-Type", "").split(";", 1)[0] != "application/json":
                return self.respond(415, {"error": "Formato de requisição inválido."})
            try:
                length = int(self.headers.get("Content-Length", "0"))
                if not 0 < length <= MAX_BODY:
                    raise UserError("Arquivo ou requisição muito grande.", 413)
                data = json.loads(self.rfile.read(length))
                if not isinstance(data, dict):
                    raise UserError("Dados inválidos.")
                path = urlsplit(self.path).path
                match = re.fullmatch(r"/api/people/(\d+)/([a-z-]+)", path)
                slot_match = re.fullmatch(r"/api/slots/(\d+)/delete", path)
                if path == "/api/people":
                    result = store.create_person(data)
                elif match:
                    person_id, action = int(match[1]), match[2]
                    result = store.edit_person(person_id, data) if action == "edit" else store.person_action(person_id, action)
                elif path == "/api/slots":
                    result = store.add_slots(data)
                elif slot_match:
                    result = store.delete_slot(int(slot_match[1]))
                elif path == "/api/settings":
                    result = store.save_settings(data)
                elif path == "/api/import/preview":
                    encoded = data.get("content", "")
                    filename = data.get("filename", "")
                    if not isinstance(encoded, str) or not isinstance(filename, str) or len(encoded) > (MAX_FILE * 4 // 3 + 8):
                        raise UserError("Arquivo inválido ou muito grande.")
                    try:
                        raw = base64.b64decode(encoded, validate=True)
                    except (ValueError, binascii.Error) as exc:
                        raise UserError("Não foi possível ler o arquivo.") from exc
                    result = preview_import(filename, raw, store.state()["people"])
                elif path == "/api/import/commit":
                    result = store.import_people(data.get("rows"))
                else:
                    raise UserError("Ação não encontrada.", 404)
                self.respond(200, result)
            except UserError as exc:
                self.respond(exc.status, {"error": str(exc)})
            except (ValueError, TypeError, UnicodeError):
                self.respond(400, {"error": "Dados inválidos. Revise o formulário."})
            except sqlite3.Error:
                self.respond(500, {"error": "Não foi possível salvar no banco local. Tente novamente."})
    return Handler


def main():
    parser = argparse.ArgumentParser(description="Agenda pessoal local")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--no-browser", action="store_true")
    parser.add_argument("--database", type=Path, default=ROOT / "data" / "agenda.sqlite3")
    args = parser.parse_args()
    if not 0 <= args.port <= 65535:
        parser.error("Porta inválida")
    store = Store(args.database)
    try:
        server = ThreadingHTTPServer(("127.0.0.1", args.port), make_handler(store))
    except OSError:
        print("A porta já está em uso. Feche a outra agenda ou execute com --port 8766.")
        return 1
    server.daemon_threads = True
    url = f"http://127.0.0.1:{server.server_port}"
    print(f"Agenda aberta em {url}\nDados: {args.database.resolve()}\nMantenha esta janela aberta. Ctrl+C encerra.")
    if not args.no_browser:
        threading.Timer(0.4, webbrowser.open, args=(url,)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nAgenda encerrada. Seus dados estão salvos.")
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
