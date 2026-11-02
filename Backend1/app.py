from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs, urlparse
from html import escape
from pathlib import Path
from conexion import conectar

HTML = Path(__file__).parent / "templates" / "index.html"


def listar_usuarios():
    conexion = conectar()
    cursor = conexion.cursor(dictionary=True)

    cursor.execute("SELECT * FROM usuarios")
    usuarios = cursor.fetchall()

    cursor.close()
    conexion.close()

    return usuarios


def ejecutar_sql(sql, valores=()):
    conexion = conectar()
    cursor = conexion.cursor()

    cursor.execute(sql, valores)
    conexion.commit()

    cursor.close()
    conexion.close()


def mostrar_pagina(mensaje=""):
    plantilla = HTML.read_text(encoding="utf-8")

    filas = ""

    for usuario in listar_usuarios():
        filas += f"""
        <tr>
            <td>{usuario['id']}</td>
            <td>{escape(usuario['nombre'])}</td>
            <td>{escape(usuario['correo'])}</td>
            <td>{escape(usuario['telefono'] or '')}</td>
            <td>
                <form method="post">
                    <input type="hidden" name="accion"
                           value="eliminar">
                    <input type="hidden" name="id"
                           value="{usuario['id']}">
                    <button>Eliminar</button>
                </form>
            </td>
        </tr>
        """

    plantilla = plantilla.replace("{{filas}}", filas)
    plantilla = plantilla.replace("{{mensaje}}", escape(mensaje))

    return plantilla


class Servidor(BaseHTTPRequestHandler):

    def responder(self, contenido):
        self.send_response(200)
        self.send_header(
            "Content-Type", "text/html; charset=utf-8"
        )
        self.end_headers()
        self.wfile.write(contenido.encode("utf-8"))

    def do_GET(self):
        self.responder(mostrar_pagina())

    def do_POST(self):
        longitud = int(self.headers["Content-Length"])
        datos = self.rfile.read(longitud).decode("utf-8")
        formulario = parse_qs(datos)

        accion = formulario.get("accion", [""])[0]
        nombre = formulario.get("nombre", [""])[0]
        correo = formulario.get("correo", [""])[0]
        telefono = formulario.get("telefono", [""])[0]
        id_usuario = formulario.get("id", [""])[0]

        if accion == "crear":
            ejecutar_sql(
                """INSERT INTO usuarios
                (nombre, correo, telefono)
                VALUES (%s, %s, %s)""",
                (nombre, correo, telefono)
            )
            mensaje = "Usuario registrado correctamente."

        elif accion == "actualizar":
            ejecutar_sql(
                """UPDATE usuarios
                SET nombre=%s, correo=%s, telefono=%s
                WHERE id=%s""",
                (nombre, correo, telefono, id_usuario)
            )
            mensaje = "Usuario actualizado correctamente."

        elif accion == "eliminar":
            ejecutar_sql(
                "DELETE FROM usuarios WHERE id=%s",
                (id_usuario,)
            )
            mensaje = "Usuario eliminado correctamente."

        else:
            mensaje = "Seleccione una operación válida."

        self.responder(mostrar_pagina(mensaje))


if __name__ == "__main__":
    servidor = HTTPServer(
        ("127.0.0.1", 8000), Servidor
    )

    print("Aplicación: http://127.0.0.1:8000")

    try:
        servidor.serve_forever()
    except KeyboardInterrupt:
        print("Servidor detenido.")
        servidor.server_close()