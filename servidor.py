import socket
import threading
import json
import pyodbc

HOST = "0.0.0.0"
PORT = 3001
TEXTO_ELIMINADO = "🚫 Este mensaje fue eliminado"

CONN_STR = (
    "DRIVER={ODBC Driver 18 for SQL Server};"
    "SERVER=localhost;"
    "DATABASE=Dato_Rex_DB;"
    "UID=User_Dato_Rex;"
    "PWD=TU_PASSWORD;"
    "TrustServerCertificate=yes;"
)

clientes_conectados = {}
lock = threading.Lock()


def get_db():
    return pyodbc.connect(CONN_STR, autocommit=True)


def enviar_json(sock, data):
    try:
        mensaje = json.dumps(data, ensure_ascii=False) + "\n"
        sock.sendall(mensaje.encode("utf-8"))
    except Exception:
        pass


def broadcast_conectados():
    with lock:
        lista_usuarios = list(clientes_conectados.keys())
        conexiones = [info["sock"] for info in clientes_conectados.values()]
    paquete = {"accion": "USUARIOS_CONECTADOS", "usuarios": lista_usuarios}
    for s in conexiones:
        enviar_json(s, paquete)


def broadcast_general(id_mensaje, remitente, contenido):
    with lock:
        conexiones = [info["sock"] for info in clientes_conectados.values()]
    paquete = {
        "accion": "MSG_GENERAL",
        "id_mensaje": id_mensaje,
        "remitente": remitente,
        "contenido": contenido,
    }
    for s in conexiones:
        enviar_json(s, paquete)


def manejar_cliente(conn, addr):
    buffer = ""
    usuario_actual = None
    id_usuario_actual = None

    try:
        while True:
            datos = conn.recv(4096)
            if not datos:
                break
            buffer += datos.decode("utf-8", errors="ignore")

            while "\n" in buffer:
                linea, buffer = buffer.split("\n", 1)
                linea = linea.strip()
                if not linea:
                    continue

                req = json.loads(linea)
                accion = req.get("accion")
                db = get_db()
                cur = db.cursor()

                if accion == "AUTH":
                    username = req.get("username", "").strip()
                    password = req.get("password", "").strip()
                    foto = req.get("foto_perfil", "")

                    if not username or not password:
                        enviar_json(conn, {"accion": "AUTH_RESP", "ok": False, "msg": "Usuario y contraseña requeridos."})
                        db.close()
                        continue

                    cur.execute("SELECT id_usuario, password, foto_perfil FROM Usuarios WHERE username = ?", (username,))
                    row = cur.fetchone()

                    if row:
                        if row.password != password:
                            enviar_json(conn, {"accion": "AUTH_RESP", "ok": False, "msg": "Contraseña incorrecta."})
                            db.close()
                            continue
                        id_usuario_actual = row.id_usuario
                        if foto:
                            cur.execute("UPDATE Usuarios SET foto_perfil = ? WHERE id_usuario = ?", (foto, id_usuario_actual))
                        else:
                            foto = row.foto_perfil or ""
                    else:
                        cur.execute(
                            "INSERT INTO Usuarios (username, password, foto_perfil) OUTPUT INSERTED.id_usuario VALUES (?, ?, ?)",
                            (username, password, foto),
                        )
                        id_usuario_actual = cur.fetchone()[0]

                    with lock:
                        if username in clientes_conectados:
                            enviar_json(conn, {"accion": "AUTH_RESP", "ok": False, "msg": "Ese usuario ya tiene una sesión activa."})
                            db.close()
                            continue
                        usuario_actual = username
                        clientes_conectados[username] = {"sock": conn, "id": id_usuario_actual}

                    enviar_json(conn, {"accion": "AUTH_RESP", "ok": True, "username": username, "foto_perfil": foto})

                    cur.execute("""
                        SELECT TOP 30 m.id_mensaje, u.username, m.contenido
                        FROM Mensajes_Generales m
                        JOIN Usuarios u ON m.id_remitente = u.id_usuario
                        ORDER BY m.id_mensaje ASC
                    """)
                    for r in cur.fetchall():
                        enviar_json(conn, {"accion": "MSG_GENERAL", "id_mensaje": r[0], "remitente": r[1], "contenido": r[2]})

                    broadcast_conectados()
                    enviar_grupos_usuario(cur, conn, id_usuario_actual)
                    enviar_lista_canales(cur, conn)

                elif accion == "ENVIAR_GENERAL" and usuario_actual:
                    contenido = req.get("contenido", "").strip()
                    if contenido:
                        cur.execute(
                            "INSERT INTO Mensajes_Generales (id_remitente, contenido) OUTPUT INSERTED.id_mensaje VALUES (?, ?)",
                            (id_usuario_actual, contenido),
                        )
                        id_msg = cur.fetchone()[0]
                        broadcast_general(id_msg, usuario_actual, contenido)

                elif accion == "ENVIAR_DM" and usuario_actual:
                    destino = req.get("destino", "").strip()
                    contenido = req.get("contenido", "").strip()
                    cur.execute("SELECT id_usuario FROM Usuarios WHERE username = ?", (destino,))
                    r_dest = cur.fetchone()
                    if r_dest and contenido:
                        cur.execute(
                            "INSERT INTO Mensajes_Directos (id_remitente, id_destinatario, contenido) OUTPUT INSERTED.id_mensaje VALUES (?, ?, ?)",
                            (id_usuario_actual, r_dest[0], contenido),
                        )
                        id_msg = cur.fetchone()[0]
                        paquete = {
                            "accion": "MSG_DM",
                            "id_mensaje": id_msg,
                            "remitente": usuario_actual,
                            "destino": destino,
                            "contenido": contenido,
                        }
                        enviar_json(conn, paquete)
                        with lock:
                            if destino in clientes_conectados and destino != usuario_actual:
                                enviar_json(clientes_conectados[destino]["sock"], paquete)

                elif accion == "HISTORIAL_DM" and usuario_actual:
                    otro = req.get("con_usuario", "").strip()
                    cur.execute("""
                        SELECT m.id_mensaje, u1.username, u2.username, m.contenido
                        FROM Mensajes_Directos m
                        JOIN Usuarios u1 ON m.id_remitente = u1.id_usuario
                        JOIN Usuarios u2 ON m.id_destinatario = u2.id_usuario
                        WHERE (u1.username = ? AND u2.username = ?) OR (u1.username = ? AND u2.username = ?)
                        ORDER BY m.id_mensaje ASC
                    """, (usuario_actual, otro, otro, usuario_actual))
                    mensajes = [{"id_mensaje": r[0], "remitente": r[1], "destino": r[2], "contenido": r[3]} for r in cur.fetchall()]
                    enviar_json(conn, {"accion": "HISTORIAL_DM_RESP", "con_usuario": otro, "mensajes": mensajes})

                elif accion == "CREAR_GRUPO" and usuario_actual:
                    nombre = req.get("nombre", "").strip()
                    miembros = set(req.get("miembros", []))
                    miembros.add(usuario_actual)
                    if nombre:
                        cur.execute(
                            "INSERT INTO Grupos (nombre, id_creador) OUTPUT INSERTED.id_grupo VALUES (?, ?)",
                            (nombre, id_usuario_actual),
                        )
                        id_grupo = cur.fetchone()[0]
                        for m_user in miembros:
                            cur.execute("SELECT id_usuario FROM Usuarios WHERE username = ?", (m_user,))
                            rm = cur.fetchone()
                            if rm:
                                cur.execute("INSERT INTO Grupo_Miembros (id_grupo, id_usuario) VALUES (?, ?)", (id_grupo, rm[0]))
                                with lock:
                                    if m_user in clientes_conectados:
                                        enviar_grupos_usuario(cur, clientes_conectados[m_user]["sock"], rm[0])

                elif accion == "ENVIAR_GRUPO" and usuario_actual:
                    id_grupo = req.get("id_grupo")
                    contenido = req.get("contenido", "").strip()
                    if id_grupo and contenido:
                        cur.execute(
                            "INSERT INTO Mensajes_Grupo (id_grupo, id_remitente, contenido) OUTPUT INSERTED.id_mensaje VALUES (?, ?, ?)",
                            (id_grupo, id_usuario_actual, contenido),
                        )
                        id_msg = cur.fetchone()[0]
                        cur.execute("""
                            SELECT u.username
                            FROM Grupo_Miembros gm
                            JOIN Usuarios u ON gm.id_usuario = u.id_usuario
                            WHERE gm.id_grupo = ?
                        """, (id_grupo,))
                        paquete = {
                            "accion": "MSG_GRUPO",
                            "id_grupo": id_grupo,
                            "id_mensaje": id_msg,
                            "remitente": usuario_actual,
                            "contenido": contenido,
                        }
                        for r in cur.fetchall():
                            with lock:
                                if r[0] in clientes_conectados:
                                    enviar_json(clientes_conectados[r[0]]["sock"], paquete)

                elif accion == "HISTORIAL_GRUPO" and usuario_actual:
                    id_grupo = req.get("id_grupo")
                    cur.execute("""
                        SELECT m.id_mensaje, u.username, m.contenido
                        FROM Mensajes_Grupo m
                        JOIN Usuarios u ON m.id_remitente = u.id_usuario
                        WHERE m.id_grupo = ?
                        ORDER BY m.id_mensaje ASC
                    """, (id_grupo,))
                    mensajes = [{"id_mensaje": r[0], "remitente": r[1], "contenido": r[2]} for r in cur.fetchall()]
                    enviar_json(conn, {"accion": "HISTORIAL_GRUPO_RESP", "id_grupo": id_grupo, "mensajes": mensajes})

                elif accion == "SALGANSE_GRUPO" and usuario_actual:
                    id_grupo = req.get("id_grupo")
                    if id_grupo:
                        cur.execute("SELECT nombre FROM Grupos WHERE id_grupo = ?", (id_grupo,))
                        rg = cur.fetchone()
                        nombre_grupo = rg[0] if rg else "el grupo"
                        cur.execute("""
                            SELECT u.id_usuario, u.username
                            FROM Grupo_Miembros gm
                            JOIN Usuarios u ON gm.id_usuario = u.id_usuario
                            WHERE gm.id_grupo = ? AND u.id_usuario <> ?
                        """, (id_grupo, id_usuario_actual))
                        expulsados = cur.fetchall()
                        cur.execute("DELETE FROM Grupo_Miembros WHERE id_grupo = ? AND id_usuario <> ?", (id_grupo, id_usuario_actual))
                        for exp_id, exp_user in expulsados:
                            with lock:
                                if exp_user in clientes_conectados:
                                    s_exp = clientes_conectados[exp_user]["sock"]
                                    enviar_grupos_usuario(cur, s_exp, exp_id)
                                    enviar_json(s_exp, {
                                        "accion": "EXPULSADO_GRUPO",
                                        "id_grupo": id_grupo,
                                        "nombre_grupo": nombre_grupo,
                                        "por": usuario_actual,
                                    })
                        enviar_json(conn, {
                            "accion": "MSG_GRUPO",
                            "id_grupo": id_grupo,
                            "id_mensaje": None,
                            "remitente": "SISTEMA",
                            "contenido": "🚪 Sálganse del grupo, quiero estar solo. (Todos los demás fueron expulsados).",
                        })

                elif accion == "CREAR_CANAL" and usuario_actual:
                    nombre = req.get("nombre", "").strip()
                    if nombre:
                        try:
                            cur.execute(
                                "INSERT INTO Canales (nombre, id_dueno) OUTPUT INSERTED.id_canal VALUES (?, ?)",
                                (nombre, id_usuario_actual),
                            )
                            id_canal = cur.fetchone()[0]
                            cur.execute("INSERT INTO Canal_Suscriptores (id_canal, id_usuario) VALUES (?, ?)", (id_canal, id_usuario_actual))
                            with lock:
                                conns = [info["sock"] for info in clientes_conectados.values()]
                            for s in conns:
                                enviar_lista_canales(cur, s)
                        except Exception:
                            enviar_json(conn, {"accion": "ERROR", "msg": "Ya existe un canal con ese nombre."})

                elif accion == "UNIRSE_CANAL" and usuario_actual:
                    id_canal = req.get("id_canal")
                    cur.execute("SELECT id_dueno, nombre FROM Canales WHERE id_canal = ?", (id_canal,))
                    rc = cur.fetchone()
                    if rc:
                        es_dueno = (rc[0] == id_usuario_actual)
                        cur.execute(
                            "SELECT 1 FROM Canal_Suscriptores WHERE id_canal = ? AND id_usuario = ?",
                            (id_canal, id_usuario_actual),
                        )
                        if not cur.fetchone():
                            cur.execute("INSERT INTO Canal_Suscriptores (id_canal, id_usuario) VALUES (?, ?)", (id_canal, id_usuario_actual))

                        cur.execute("""
                            SELECT m.id_mensaje, u.username, m.contenido
                            FROM Mensajes_Canal m
                            JOIN Usuarios u ON m.id_remitente = u.id_usuario
                            WHERE m.id_canal = ?
                            ORDER BY m.id_mensaje ASC
                        """, (id_canal,))
                        mensajes = [{"id_mensaje": r[0], "remitente": r[1], "contenido": r[2]} for r in cur.fetchall()]
                        enviar_json(conn, {
                            "accion": "CANAL_UNIDO",
                            "id_canal": id_canal,
                            "nombre": rc[1],
                            "es_dueno": es_dueno,
                            "mensajes": mensajes,
                        })

                elif accion == "ENVIAR_CANAL" and usuario_actual:
                    id_canal = req.get("id_canal")
                    contenido = req.get("contenido", "").strip()
                    cur.execute("SELECT id_dueno FROM Canales WHERE id_canal = ?", (id_canal,))
                    rc = cur.fetchone()
                    if rc and rc[0] == id_usuario_actual and contenido:
                        cur.execute(
                            "INSERT INTO Mensajes_Canal (id_canal, id_remitente, contenido) OUTPUT INSERTED.id_mensaje VALUES (?, ?, ?)",
                            (id_canal, id_usuario_actual, contenido),
                        )
                        id_msg = cur.fetchone()[0]
                        cur.execute("""
                            SELECT u.username
                            FROM Canal_Suscriptores cs
                            JOIN Usuarios u ON cs.id_usuario = u.id_usuario
                            WHERE cs.id_canal = ?
                        """, (id_canal,))
                        paquete = {
                            "accion": "MSG_CANAL",
                            "id_canal": id_canal,
                            "id_mensaje": id_msg,
                            "remitente": usuario_actual,
                            "contenido": contenido,
                        }
                        for r in cur.fetchall():
                            with lock:
                                if r[0] in clientes_conectados:
                                    enviar_json(clientes_conectados[r[0]]["sock"], paquete)

                elif accion == "ELIMINAR_MENSAJE" and usuario_actual:
                    tipo = req.get("tipo")
                    id_mensaje = req.get("id_mensaje")
                    if tipo and id_mensaje:
                        if tipo == "general":
                            cur.execute("SELECT 1 FROM Mensajes_Generales WHERE id_mensaje = ? AND id_remitente = ?", (id_mensaje, id_usuario_actual))
                            if cur.fetchone():
                                cur.execute("UPDATE Mensajes_Generales SET contenido = ? WHERE id_mensaje = ?", (TEXTO_ELIMINADO, id_mensaje))
                                with lock:
                                    conns = [info["sock"] for info in clientes_conectados.values()]
                                paquete = {"accion": "MENSAJE_ELIMINADO", "tipo": "general", "id_mensaje": id_mensaje, "remitente": usuario_actual, "texto": TEXTO_ELIMINADO}
                                for s in conns:
                                    enviar_json(s, paquete)

                        elif tipo == "dm":
                            cur.execute("""
                                SELECT u2.username
                                FROM Mensajes_Directos m
                                JOIN Usuarios u2 ON m.id_destinatario = u2.id_usuario
                                WHERE m.id_mensaje = ? AND m.id_remitente = ?
                            """, (id_mensaje, id_usuario_actual))
                            row_dm = cur.fetchone()
                            if row_dm:
                                destino_user = row_dm[0]
                                cur.execute("UPDATE Mensajes_Directos SET contenido = ? WHERE id_mensaje = ?", (TEXTO_ELIMINADO, id_mensaje))
                                paquete = {
                                    "accion": "MENSAJE_ELIMINADO",
                                    "tipo": "dm",
                                    "id_mensaje": id_mensaje,
                                    "remitente": usuario_actual,
                                    "destino": destino_user,
                                    "texto": TEXTO_ELIMINADO,
                                }
                                enviar_json(conn, paquete)
                                with lock:
                                    if destino_user in clientes_conectados and destino_user != usuario_actual:
                                        enviar_json(clientes_conectados[destino_user]["sock"], paquete)

                        elif tipo == "grupo":
                            cur.execute("SELECT id_grupo FROM Mensajes_Grupo WHERE id_mensaje = ? AND id_remitente = ?", (id_mensaje, id_usuario_actual))
                            row_g = cur.fetchone()
                            if row_g:
                                id_grupo = row_g[0]
                                cur.execute("UPDATE Mensajes_Grupo SET contenido = ? WHERE id_mensaje = ?", (TEXTO_ELIMINADO, id_mensaje))
                                cur.execute("""
                                    SELECT u.username
                                    FROM Grupo_Miembros gm
                                    JOIN Usuarios u ON gm.id_usuario = u.id_usuario
                                    WHERE gm.id_grupo = ?
                                """, (id_grupo,))
                                paquete = {
                                    "accion": "MENSAJE_ELIMINADO",
                                    "tipo": "grupo",
                                    "id_grupo": id_grupo,
                                    "id_mensaje": id_mensaje,
                                    "remitente": usuario_actual,
                                    "texto": TEXTO_ELIMINADO,
                                }
                                for r in cur.fetchall():
                                    with lock:
                                        if r[0] in clientes_conectados:
                                            enviar_json(clientes_conectados[r[0]]["sock"], paquete)

                        elif tipo == "canal":
                            cur.execute("SELECT id_canal FROM Mensajes_Canal WHERE id_mensaje = ? AND id_remitente = ?", (id_mensaje, id_usuario_actual))
                            row_c = cur.fetchone()
                            if row_c:
                                id_canal = row_c[0]
                                cur.execute("UPDATE Mensajes_Canal SET contenido = ? WHERE id_mensaje = ?", (TEXTO_ELIMINADO, id_mensaje))
                                cur.execute("""
                                    SELECT u.username
                                    FROM Canal_Suscriptores cs
                                    JOIN Usuarios u ON cs.id_usuario = u.id_usuario
                                    WHERE cs.id_canal = ?
                                """, (id_canal,))
                                paquete = {
                                    "accion": "MENSAJE_ELIMINADO",
                                    "tipo": "canal",
                                    "id_canal": id_canal,
                                    "id_mensaje": id_mensaje,
                                    "remitente": usuario_actual,
                                    "texto": TEXTO_ELIMINADO,
                                }
                                for r in cur.fetchall():
                                    with lock:
                                        if r[0] in clientes_conectados:
                                            enviar_json(clientes_conectados[r[0]]["sock"], paquete)

                db.close()

    except Exception as e:
        print(f"[!] Error con {addr}: {e}")
    finally:
        if usuario_actual:
            with lock:
                if usuario_actual in clientes_conectados:
                    del clientes_conectados[usuario_actual]
            broadcast_conectados()
        conn.close()


def enviar_grupos_usuario(cur, sock, id_usuario):
    cur.execute("""
        SELECT g.id_grupo, g.nombre
        FROM Grupos g
        JOIN Grupo_Miembros gm ON g.id_grupo = gm.id_grupo
        WHERE gm.id_usuario = ?
    """, (id_usuario,))
    grupos = [{"id_grupo": r[0], "nombre": r[1]} for r in cur.fetchall()]
    enviar_json(sock, {"accion": "LISTA_GRUPOS", "grupos": grupos})


def enviar_lista_canales(cur, sock):
    cur.execute("""
        SELECT c.id_canal, c.nombre, u.username
        FROM Canales c
        JOIN Usuarios u ON c.id_dueno = u.id_usuario
    """)
    canales = [{"id_canal": r[0], "nombre": r[1], "dueno": r[2]} for r in cur.fetchall()]
    enviar_json(sock, {"accion": "LISTA_CANALES", "canales": canales})


def iniciar_servidor():
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind((HOST, PORT))
    server.listen(50)
    print(f"[*] Servidor Wasap Dato_Rex escuchando en {HOST}:{PORT}...")

    while True:
        conn, addr = server.accept()
        t = threading.Thread(target=manejar_cliente, args=(conn, addr), daemon=True)
        t.start()


if __name__ == "__main__":
    iniciar_servidor()
















