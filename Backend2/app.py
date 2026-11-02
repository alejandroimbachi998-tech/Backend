import sqlite3
import os
import urllib.parse
import html as html_escape
import traceback
from http.server import HTTPServer, BaseHTTPRequestHandler

DB_FILE = "backend2.db"
TEMPLATES = os.path.join(os.path.dirname(__file__), "templates")


# ====== INICIALIZAR DB ======
def init_db():
    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()
    cur.executescript("""
    CREATE TABLE IF NOT EXISTS usuarios (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nombre VARCHAR(100) NOT NULL,
        correo VARCHAR(100) NOT NULL UNIQUE,
        telefono VARCHAR(20)
    );
    CREATE TABLE IF NOT EXISTS proveedores (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nombre_empresa VARCHAR(150) NOT NULL,
        nit_o_rut VARCHAR(50) NOT NULL UNIQUE,
        telefono VARCHAR(20),
        usuario_id INTEGER,
        FOREIGN KEY (usuario_id) REFERENCES usuarios(id) ON DELETE SET NULL
    );
    """)
    conn.commit()
    conn.close()


# ====== RENDER ======
def render(template, **ctx):
    path = os.path.join(TEMPLATES, template)
    with open(path, "r", encoding="utf-8") as f:
        html = f.read()
    for k, v in ctx.items():
        html = html.replace("{{" + k + "}}", str(v))
    return html


# ====== ESCAPAR HTML ======
def esc(value):
    """Escapa cualquier valor para que no rompa el HTML."""
    if value is None:
        return ""
    return html_escape.escape(str(value), quote=True)


# ====== HANDLER ======
class Handler(BaseHTTPRequestHandler):

    def _send(self, content, status=200):
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(content.encode("utf-8"))

    def _redirect(self, path, msg=None):
        self.send_response(302)
        if msg:
            self.send_header("Location", path + "?msg=" + urllib.parse.quote(msg))
        else:
            self.send_header("Location", path)
        self.end_headers()

    def _parse(self):
        length = int(self.headers.get("Content-Length", 0))
        data = self.rfile.read(length).decode("utf-8")
        return {k: v[0] for k, v in urllib.parse.parse_qs(data).items()}

    def _query_msg(self):
        qs = urllib.parse.urlparse(self.path).query
        return urllib.parse.parse_qs(qs).get("msg", [None])[0]

    # ============= GET =============
    def do_GET(self):
        try:
            parsed = urllib.parse.urlparse(self.path)
            path = parsed.path

            if path == "/" or path == "":
                self._send(render("index.html"))

            elif path == "/usuarios":
                conn = sqlite3.connect(DB_FILE)
                cur = conn.cursor()
                cur.execute("SELECT id, nombre, correo, telefono FROM usuarios ORDER BY id")
                rows = cur.fetchall()
                conn.close()
                self._send(render("usuarios.html",
                                  filas=self._build_usuarios(rows),
                                  mensaje=self._flash(self._query_msg())))

            elif path == "/proveedores":
                conn = sqlite3.connect(DB_FILE)
                cur = conn.cursor()
                cur.execute("""SELECT p.id, p.nombre_empresa, p.nit_o_rut, p.telefono,
                                      p.usuario_id, u.nombre
                               FROM proveedores p
                               LEFT JOIN usuarios u ON p.usuario_id = u.id
                               ORDER BY p.id""")
                rows = cur.fetchall()
                cur.execute("SELECT id, nombre FROM usuarios ORDER BY nombre")
                usuarios = cur.fetchall()
                conn.close()

                self._send(render("proveedores.html",
                                  filas=self._build_proveedores(rows, usuarios),
                                  opciones_usuarios=self._build_opciones_usuarios(usuarios),
                                  mensaje=self._flash(self._query_msg())))

            elif path.startswith("/usuarios/eliminar/"):
                uid = int(path.split("/")[-1])
                conn = sqlite3.connect(DB_FILE)
                conn.execute("DELETE FROM usuarios WHERE id=?", (uid,))
                conn.commit()
                conn.close()
                self._redirect("/usuarios", "Usuario eliminado")

            elif path.startswith("/proveedores/eliminar/"):
                pid = int(path.split("/")[-1])
                conn = sqlite3.connect(DB_FILE)
                conn.execute("DELETE FROM proveedores WHERE id=?", (pid,))
                conn.commit()
                conn.close()
                self._redirect("/proveedores", "Proveedor eliminado")

            else:
                self._send("<h1>404 - No encontrado</h1>", 404)

        except Exception:
            # 🔥 LOG DEL ERROR REAL EN LA CONSOLA
            print("\n💥 ERROR EN GET:", self.path)
            traceback.print_exc()
            self._send("<h1>500 - Error interno</h1><pre>" + esc(traceback.format_exc()) + "</pre>", 500)

    # ============= POST =============
    def do_POST(self):
        data = self._parse()
        path = self.path

        try:
            conn = sqlite3.connect(DB_FILE)
            cur = conn.cursor()

            if path == "/usuarios/crear":
                cur.execute("INSERT INTO usuarios (nombre, correo, telefono) VALUES (?,?,?)",
                            (data["nombre"], data["correo"], data.get("telefono") or None))
                conn.commit()
                self._redirect("/usuarios", "Usuario creado")

            elif path.startswith("/usuarios/editar/"):
                uid = int(path.split("/")[-1])
                cur.execute("UPDATE usuarios SET nombre=?, correo=?, telefono=? WHERE id=?",
                            (data["nombre"], data["correo"], data.get("telefono") or None, uid))
                conn.commit()
                self._redirect("/usuarios", "Usuario actualizado")

            elif path == "/proveedores/crear":
                uid = data.get("usuario_id") or None
                cur.execute("""INSERT INTO proveedores (nombre_empresa, nit_o_rut, telefono, usuario_id)
                               VALUES (?,?,?,?)""",
                            (data["nombre_empresa"], data["nit_o_rut"],
                             data.get("telefono") or None,
                             int(uid) if uid else None))
                conn.commit()
                self._redirect("/proveedores", "Proveedor creado")

            elif path.startswith("/proveedores/editar/"):
                pid = int(path.split("/")[-1])
                uid = data.get("usuario_id") or None
                cur.execute("""UPDATE proveedores
                               SET nombre_empresa=?, nit_o_rut=?, telefono=?, usuario_id=?
                               WHERE id=?""",
                            (data["nombre_empresa"], data["nit_o_rut"],
                             data.get("telefono") or None,
                             int(uid) if uid else None, pid))
                conn.commit()
                self._redirect("/proveedores", "Proveedor actualizado")

            else:
                self._send("<h1>404</h1>", 404)

        except sqlite3.IntegrityError as e:
            print("⚠️ IntegrityError:", e)
            self._redirect(path.rsplit("/", 1)[0] or "/", f"Error: {e}")
        except Exception:
            print("\n💥 ERROR EN POST:", path)
            traceback.print_exc()
            self._redirect("/", "Error interno del servidor")
        finally:
            try:
                conn.close()
            except:
                pass

    # ============= HELPERS HTML (con escape) =============
    def _flash(self, msg):
        if not msg:
            return ""
        return f'<div class="flash">{esc(msg)}</div>'

    def _build_usuarios(self, rows):
        if not rows:
            return '<p class="empty">No hay usuarios registrados.</p>'
        html = ""
        for u in rows:
            uid, nombre, correo, tel = u
            n_esc = esc(nombre)
            html += f"""
            <tr>
              <form method="POST" action="/usuarios/editar/{uid}">
                <td>{uid}</td>
                <td><input name="nombre" value="{n_esc}" required></td>
                <td><input name="correo" value="{esc(correo)}" required></td>
                <td><input name="telefono" value="{esc(tel)}"></td>
                <td style="white-space:nowrap;">
                    <button class="btn btn-warning" type="submit">💾</button>
                    <a class="btn btn-danger" href="/usuarios/eliminar/{uid}"
                       onclick="return confirm('¿Eliminar a {n_esc}?')">🗑️</a>
                </td>
              </form>
            </tr>"""
        return html

    def _build_proveedores(self, rows, usuarios):
        if not rows:
            return '<p class="empty">No hay proveedores registrados.</p>'
        html = ""
        for r in rows:
            pid, empresa, nit, tel, uid, uname = r
            opts = '<option value="">— Sin usuario —</option>'
            for u in usuarios:
                u_id, u_nombre = u
                sel = "selected" if (uid is not None and u_id == uid) else ""
                opts += f'<option value="{u_id}" {sel}>{esc(u_nombre)}</option>'

            empresa_esc = esc(empresa)
            html += f"""
            <tr>
              <form method="POST" action="/proveedores/editar/{pid}">
                <td>{pid}</td>
                <td><input name="nombre_empresa" value="{empresa_esc}" required></td>
                <td><input name="nit_o_rut" value="{esc(nit)}" required></td>
                <td><input name="telefono" value="{esc(tel)}"></td>
                <td><select name="usuario_id">{opts}</select></td>
                <td style="white-space:nowrap;">
                    <button class="btn btn-warning" type="submit">💾</button>
                    <a class="btn btn-danger" href="/proveedores/eliminar/{pid}"
                       onclick="return confirm('¿Eliminar {empresa_esc}?')">🗑️</a>
                </td>
              </form>
            </tr>"""
        return html

    def _build_opciones_usuarios(self, usuarios):
        opts = '<option value="">— Sin usuario asociado —</option>'
        for u in usuarios:
            u_id, u_nombre = u
            opts += f'<option value="{u_id}">{esc(u_nombre)}</option>'
        return opts


if __name__ == "__main__":
    init_db()
    print("✅ Servidor en http://localhost:8000")
    HTTPServer(("0.0.0.0", 8000), Handler).serve_forever()