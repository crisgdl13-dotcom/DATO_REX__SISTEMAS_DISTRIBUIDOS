import socket
import threading
import json
import base64
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, simpledialog

SERVIDOR_IP = "3.149.102.2"
SERVIDOR_PUERTO = 3001


class WasapCliente:
    def __init__(self, root):
        self.root = root
        self.root.title("Wasap - Equipo Dato_Rex")
        self.root.geometry("880x580")

        self.sock = None
        self.username = None
        self.foto_b64 = ""
        self.avatar_img = None

        self.usuarios_conectados = []
        self.grupos_map = {}   # nombre -> id_grupo
        self.canales_map = {}  # etiqueta -> id_canal
        self.grupo_activo = None
        self.canal_activo = None
        self.es_dueno_canal = False

        self.construir_login()

    # ---------------- PANTALLA DE LOGIN / REGISTRO ----------------
    def construir_login(self):
        self.frame_login = tk.Frame(self.root, padx=30, pady=30)
        self.frame_login.pack(expand=True)

        tk.Label(self.frame_login, text="Wasap - Dato_Rex", font=("Arial", 18, "bold")).pack(pady=10)
        tk.Label(self.frame_login, text=f"Servidor: {SERVIDOR_IP}:{SERVIDOR_PUERTO}", fg="gray").pack(pady=2)

        tk.Label(self.frame_login, text="Nombre de usuario:").pack(anchor="w", pady=(12, 0))
        self.entry_user = tk.Entry(self.frame_login, width=32)
        self.entry_user.pack(pady=4)

        tk.Label(self.frame_login, text="Contraseña:").pack(anchor="w", pady=(8, 0))
        self.entry_pass = tk.Entry(self.frame_login, width=32, show="*")
        self.entry_pass.pack(pady=4)

        self.lbl_foto = tk.Label(self.frame_login, text="Sin foto seleccionada (opcional)", fg="gray")
        self.lbl_foto.pack(pady=(10, 2))
        tk.Button(self.frame_login, text="Seleccionar Foto de Perfil (.png/.gif)", command=self.seleccionar_foto).pack(pady=4)

        tk.Button(
            self.frame_login,
            text="Conectar / Registrar",
            bg="#128C7E",
            fg="white",
            font=("Arial", 11, "bold"),
            width=25,
            command=self.conectar,
        ).pack(pady=18)

    def seleccionar_foto(self):
        ruta = filedialog.askopenfilename(filetypes=[("Imágenes PNG/GIF", "*.png *.gif"), ("Todos", "*.*")])
        if ruta:
            try:
                with open(ruta, "rb") as f:
                    raw = f.read()
                if len(raw) > 250_000:
                    messagebox.showwarning("Imagen grande", "Elige una imagen menor a 250 KB.")
                    return
                self.foto_b64 = base64.b64encode(raw).decode("utf-8")
                self.lbl_foto.config(text=f"Foto cargada: {ruta.split('/')[-1]}", fg="green")
            except Exception as e:
                messagebox.showerror("Error", f"No se pudo leer la imagen: {e}")

    def conectar(self):
        user = self.entry_user.get().strip()
        pwd = self.entry_pass.get().strip()
        if not user or not pwd:
            messagebox.showwarning("Campos vacíos", "Ingresa usuario y contraseña.")
            return

        try:
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.sock.connect((SERVIDOR_IP, SERVIDOR_PUERTO))
        except Exception as e:
            messagebox.showerror("Error de conexión", f"No se pudo conectar al servidor:\n{e}")
            return

        threading.Thread(target=self.escuchar_servidor, daemon=True).start()
        self.enviar_json({"accion": "AUTH", "username": user, "password": pwd, "foto_perfil": self.foto_b64})

    def enviar_json(self, data):
        if self.sock:
            try:
                self.sock.sendall((json.dumps(data, ensure_ascii=False) + "\n").encode("utf-8"))
            except Exception:
                pass

    # ---------------- INTERFAZ PRINCIPAL ----------------
    def construir_app(self):
        self.frame_login.destroy()

        top_bar = tk.Frame(self.root, bg="#075E54", height=55)
        top_bar.pack(fill="x")

        if self.foto_b64:
            try:
                img = tk.PhotoImage(data=self.foto_b64)
                w = img.width()
                if w > 44:
                    img = img.subsample(max(1, w // 44))
                self.avatar_img = img
                tk.Label(top_bar, image=self.avatar_img, bg="#075E54").pack(side="left", padx=10, pady=5)
            except Exception:
                pass

        tk.Label(
            top_bar,
            text=f"Usuario conectado: {self.username}   |   Equipo Dato_Rex",
            bg="#075E54",
            fg="white",
            font=("Arial", 12, "bold"),
        ).pack(side="left", padx=12, pady=14)

        self.tabs = ttk.Notebook(self.root)
        self.tabs.pack(fill="both", expand=True, padx=8, pady=8)

        self.crear_tab_general()
        self.crear_tab_directo()
        self.crear_tab_grupos()
        self.crear_tab_canales()

    # 1. CHAT GENERAL
    def crear_tab_general(self):
        tab = tk.Frame(self.tabs)
        self.tabs.add(tab, text="1. Chat General")

        bottom = tk.Frame(tab)
        bottom.pack(side="bottom", fill="x", padx=6, pady=6)
        self.entry_general = tk.Entry(bottom, font=("Arial", 10))
        self.entry_general.pack(side="left", fill="x", expand=True, padx=(0, 6))
        self.entry_general.bind("<Return>", lambda e: self.enviar_general())
        tk.Button(bottom, text="Enviar a Todos", bg="#128C7E", fg="white", command=self.enviar_general).pack(side="right")

        self.txt_general = tk.Text(tab, state="disabled", wrap="word", font=("Arial", 10))
        self.txt_general.pack(fill="both", expand=True, padx=6, pady=6)

    def enviar_general(self):
        msg = self.entry_general.get().strip()
        if msg:
            self.enviar_json({"accion": "ENVIAR_GENERAL", "contenido": msg})
            self.entry_general.delete(0, tk.END)

    # 2. MENSAJE DIRECTO
    def crear_tab_directo(self):
        tab = tk.Frame(self.tabs)
        self.tabs.add(tab, text="2. Mensaje Directo")

        izq = tk.Frame(tab, width=200)
        izq.pack(side="left", fill="y", padx=6, pady=6)
        tk.Label(izq, text="Usuarios conectados:", font=("Arial", 10, "bold")).pack(anchor="w")
        self.list_usuarios = tk.Listbox(izq, width=24)
        self.list_usuarios.pack(fill="y", expand=True, pady=4)
        self.list_usuarios.bind("<<ListboxSelect>>", self.seleccionar_usuario_dm)

        der = tk.Frame(tab)
        der.pack(side="right", fill="both", expand=True, padx=6, pady=6)
        self.lbl_dm_destino = tk.Label(der, text="Selecciona un usuario de la lista", font=("Arial", 10, "bold"))
        self.lbl_dm_destino.pack(anchor="w")

        bottom = tk.Frame(der)
        bottom.pack(side="bottom", fill="x")
        self.entry_dm = tk.Entry(bottom, font=("Arial", 10))
        self.entry_dm.pack(side="left", fill="x", expand=True, padx=(0, 6))
        self.entry_dm.bind("<Return>", lambda e: self.enviar_dm())
        tk.Button(bottom, text="Enviar Privado", bg="#128C7E", fg="white", command=self.enviar_dm).pack(side="right")

        self.txt_dm = tk.Text(der, state="disabled", wrap="word", font=("Arial", 10))
        self.txt_dm.pack(fill="both", expand=True, pady=4)

    def seleccionar_usuario_dm(self, _event):
        sel = self.list_usuarios.curselection()
        if sel:
            destino = self.list_usuarios.get(sel[0])
            self.lbl_dm_destino.config(text=f"Chat privado con: {destino}")
            self.limpiar_texto(self.txt_dm)
            self.enviar_json({"accion": "HISTORIAL_DM", "con_usuario": destino})

    def enviar_dm(self):
        sel = self.list_usuarios.curselection()
        if not sel:
            messagebox.showinfo("Mensaje Directo", "Selecciona primero un usuario conectado.")
            return
        destino = self.list_usuarios.get(sel[0])
        msg = self.entry_dm.get().strip()
        if msg:
            self.enviar_json({"accion": "ENVIAR_DM", "destino": destino, "contenido": msg})
            self.entry_dm.delete(0, tk.END)

    # 3. GRUPOS + BOTÓN DEL MEME
    def crear_tab_grupos(self):
        tab = tk.Frame(self.tabs)
        self.tabs.add(tab, text="3. Grupos")

        izq = tk.Frame(tab, width=220)
        izq.pack(side="left", fill="y", padx=6, pady=6)
        tk.Button(izq, text="+ Crear Grupo", bg="#25D366", fg="white", font=("Arial", 9, "bold"), command=self.dialogo_crear_grupo).pack(fill="x", pady=(0, 4))
        tk.Button(
            izq,
            text="🚪 Sálganse del grupo,\nquiero estar solo",
            bg="#C62828",
            fg="white",
            font=("Arial", 9, "bold"),
            command=self.salganse_del_grupo,
        ).pack(fill="x", pady=(0, 8))

        tk.Label(izq, text="Mis grupos:", font=("Arial", 10, "bold")).pack(anchor="w")
        self.list_grupos = tk.Listbox(izq, width=26)
        self.list_grupos.pack(fill="y", expand=True, pady=4)
        self.list_grupos.bind("<<ListboxSelect>>", self.seleccionar_grupo)

        der = tk.Frame(tab)
        der.pack(side="right", fill="both", expand=True, padx=6, pady=6)
        self.lbl_grupo_titulo = tk.Label(der, text="Selecciona o crea un grupo", font=("Arial", 10, "bold"))
        self.lbl_grupo_titulo.pack(anchor="w")

        bottom = tk.Frame(der)
        bottom.pack(side="bottom", fill="x")
        self.entry_grupo = tk.Entry(bottom, font=("Arial", 10))
        self.entry_grupo.pack(side="left", fill="x", expand=True, padx=(0, 6))
        self.entry_grupo.bind("<Return>", lambda e: self.enviar_grupo())
        tk.Button(bottom, text="Enviar al Grupo", bg="#128C7E", fg="white", command=self.enviar_grupo).pack(side="right")

        self.txt_grupo = tk.Text(der, state="disabled", wrap="word", font=("Arial", 10))
        self.txt_grupo.pack(fill="both", expand=True, pady=4)

    def salganse_del_grupo(self):
        if not self.grupo_activo:
            messagebox.showinfo("Grupos", "Selecciona primero el grupo donde quieres quedarte solo.")
            return
        self.enviar_json({"accion": "SALGANSE_GRUPO", "id_grupo": self.grupo_activo})

    def dialogo_crear_grupo(self):
        nombre = simpledialog.askstring("Nuevo Grupo", "Nombre del grupo:")
        if not nombre:
            return
        otros = [u for u in self.usuarios_conectados if u != self.username]
        if not otros:
            self.enviar_json({"accion": "CREAR_GRUPO", "nombre": nombre, "miembros": []})
            return

        win = tk.Toplevel(self.root)
        win.title("Agregar usuarios conectados")
        tk.Label(win, text="Selecciona miembros para el grupo:", padx=10, pady=8).pack()
        vars_chk = {}
        for u in otros:
            v = tk.BooleanVar()
            tk.Checkbutton(win, text=u, variable=v).pack(anchor="w", padx=15)
            vars_chk[u] = v

        def confirmar():
            elegidos = [u for u, v in vars_chk.items() if v.get()]
            self.enviar_json({"accion": "CREAR_GRUPO", "nombre": nombre, "miembros": elegidos})
            win.destroy()

        tk.Button(win, text="Crear Grupo", bg="#128C7E", fg="white", command=confirmar).pack(pady=10)

    def seleccionar_grupo(self, _event):
        sel = self.list_grupos.curselection()
        if sel:
            nombre = self.list_grupos.get(sel[0])
            self.grupo_activo = self.grupos_map.get(nombre)
            self.lbl_grupo_titulo.config(text=f"Grupo: {nombre}")
            self.limpiar_texto(self.txt_grupo)
            self.enviar_json({"accion": "HISTORIAL_GRUPO", "id_grupo": self.grupo_activo})

    def enviar_grupo(self):
        if not self.grupo_activo:
            messagebox.showinfo("Grupos", "Selecciona primero un grupo.")
            return
        msg = self.entry_grupo.get().strip()
        if msg:
            self.enviar_json({"accion": "ENVIAR_GRUPO", "id_grupo": self.grupo_activo, "contenido": msg})
            self.entry_grupo.delete(0, tk.END)

    # 4. CANALES DE DIFUSIÓN
    def crear_tab_canales(self):
        tab = tk.Frame(self.tabs)
        self.tabs.add(tab, text="4. Canales")

        izq = tk.Frame(tab, width=230)
        izq.pack(side="left", fill="y", padx=6, pady=6)
        tk.Button(izq, text="+ Crear Canal", bg="#25D366", fg="white", command=self.crear_canal).pack(fill="x", pady=(0, 6))
        tk.Label(izq, text="Canales disponibles (clic para unirte):", font=("Arial", 9, "bold")).pack(anchor="w")
        self.list_canales = tk.Listbox(izq, width=28)
        self.list_canales.pack(fill="y", expand=True, pady=4)
        self.list_canales.bind("<<ListboxSelect>>", self.unirse_canal)

        der = tk.Frame(tab)
        der.pack(side="right", fill="both", expand=True, padx=6, pady=6)
        self.lbl_canal_titulo = tk.Label(der, text="Selecciona un canal para unirte", font=("Arial", 10, "bold"))
        self.lbl_canal_titulo.pack(anchor="w")

        bottom = tk.Frame(der)
        bottom.pack(side="bottom", fill="x")
        self.entry_canal = tk.Entry(bottom, font=("Arial", 10), state="disabled")
        self.entry_canal.pack(side="left", fill="x", expand=True, padx=(0, 6))
        self.entry_canal.bind("<Return>", lambda e: self.enviar_canal())
        self.btn_canal = tk.Button(bottom, text="Difundir en Canal", bg="#128C7E", fg="white", state="disabled", command=self.enviar_canal)
        self.btn_canal.pack(side="right")

        self.txt_canal = tk.Text(der, state="disabled", wrap="word", font=("Arial", 10))
        self.txt_canal.pack(fill="both", expand=True, pady=4)

    def crear_canal(self):
        nombre = simpledialog.askstring("Nuevo Canal", "Nombre del canal de difusión:")
        if nombre:
            self.enviar_json({"accion": "CREAR_CANAL", "nombre": nombre})

    def unirse_canal(self, _event):
        sel = self.list_canales.curselection()
        if sel:
            etiqueta = self.list_canales.get(sel[0])
            id_canal = self.canales_map.get(etiqueta)
            if id_canal:
                self.enviar_json({"accion": "UNIRSE_CANAL", "id_canal": id_canal})

    def enviar_canal(self):
        if self.canal_activo and self.es_dueno_canal:
            msg = self.entry_canal.get().strip()
            if msg:
                self.enviar_json({"accion": "ENVIAR_CANAL", "id_canal": self.canal_activo, "contenido": msg})
                self.entry_canal.delete(0, tk.END)

    # ---------------- UTILIDADES DE TEXTO Y ESCUCHA ----------------
    def agregar_linea(self, widget, texto):
        widget.config(state="normal")
        widget.insert(tk.END, texto + "\n")
        widget.see(tk.END)
        widget.config(state="disabled")

    def limpiar_texto(self, widget):
        widget.config(state="normal")
        widget.delete("1.0", tk.END)
        widget.config(state="disabled")

    def escuchar_servidor(self):
        buffer = ""
        try:
            while True:
                datos = self.sock.recv(4096)
                if not datos:
                    break
                buffer += datos.decode("utf-8", errors="ignore")
                while "\n" in buffer:
                    linea, buffer = buffer.split("\n", 1)
                    if linea.strip():
                        data = json.loads(linea)
                        self.root.after(0, self.procesar_evento, data)
        except Exception:
            pass

    def procesar_evento(self, data):
        accion = data.get("accion")

        if accion == "AUTH_RESP":
            if data.get("ok"):
                self.username = data["username"]
                self.foto_b64 = data.get("foto_perfil", "")
                self.construir_app()
            else:
                messagebox.showerror("Acceso denegado", data.get("msg", "Error de autenticación"))

        elif accion == "USUARIOS_CONECTADOS":
            self.usuarios_conectados = data.get("usuarios", [])
            if hasattr(self, "list_usuarios"):
                self.list_usuarios.delete(0, tk.END)
                for u in self.usuarios_conectados:
                    if u != self.username:
                        self.list_usuarios.insert(tk.END, u)

        elif accion == "MSG_GENERAL":
            self.agregar_linea(self.txt_general, f"[{data['remitente']}]: {data['contenido']}")

        elif accion == "HISTORIAL_DM_RESP":
            self.limpiar_texto(self.txt_dm)
            for m in data.get("mensajes", []):
                self.agregar_linea(self.txt_dm, f"[{m['remitente']}]: {m['contenido']}")

        elif accion == "MSG_DM":
            sel = self.list_usuarios.curselection()
            activo = self.list_usuarios.get(sel[0]) if sel else None
            if activo in (data["remitente"], data["destino"]):
                self.agregar_linea(self.txt_dm, f"[{data['remitente']}]: {data['contenido']}")
            elif data["remitente"] != self.username:
                self.agregar_linea(self.txt_general, f"📩 (Nuevo mensaje directo de {data['remitente']})")

        elif accion == "LISTA_GRUPOS":
            self.grupos_map.clear()
            self.list_grupos.delete(0, tk.END)
            for g in data.get("grupos", []):
                self.grupos_map[g["nombre"]] = g["id_grupo"]
                self.list_grupos.insert(tk.END, g["nombre"])

        elif accion == "HISTORIAL_GRUPO_RESP":
            if data.get("id_grupo") == self.grupo_activo:
                self.limpiar_texto(self.txt_grupo)
                for m in data.get("mensajes", []):
                    self.agregar_linea(self.txt_grupo, f"[{m['remitente']}]: {m['contenido']}")

        elif accion == "MSG_GRUPO":
            if data.get("id_grupo") == self.grupo_activo:
                self.agregar_linea(self.txt_grupo, f"[{data['remitente']}]: {data['contenido']}")

        elif accion == "EXPULSADO_GRUPO":
            if self.grupo_activo == data.get("id_grupo"):
                self.grupo_activo = None
                self.limpiar_texto(self.txt_grupo)
                self.lbl_grupo_titulo.config(text="Selecciona o crea un grupo")
            messagebox.showinfo(
                "Sálganse del grupo...",
                f"🚪 {data['por']} dijo: 'Sálganse del grupo, quiero estar solo' y te sacó de '{data['nombre_grupo']}'.",
            )

        elif accion == "LISTA_CANALES":
            self.canales_map.clear()
            self.list_canales.delete(0, tk.END)
            for c in data.get("canales", []):
                etiqueta = f"{c['nombre']} (Dueño: {c['dueno']})"
                self.canales_map[etiqueta] = c["id_canal"]
                self.list_canales.insert(tk.END, etiqueta)

        elif accion == "CANAL_UNIDO":
            self.canal_activo = data["id_canal"]
            self.es_dueno_canal = data["es_dueno"]
            self.limpiar_texto(self.txt_canal)
            for m in data.get("mensajes", []):
                self.agregar_linea(self.txt_canal, f"[📢 {m['remitente']}]: {m['contenido']}")

            if self.es_dueno_canal:
                self.lbl_canal_titulo.config(text=f"Canal: {data['nombre']} (Eres el dueño - Puedes publicar)")
                self.entry_canal.config(state="normal")
                self.btn_canal.config(state="normal")
            else:
                self.lbl_canal_titulo.config(text=f"Canal: {data['nombre']} (Modo lectura - Solo el dueño publica)")
                self.entry_canal.delete(0, tk.END)
                self.entry_canal.config(state="disabled")
                self.btn_canal.config(state="disabled")

        elif accion == "MSG_CANAL":
            if data.get("id_canal") == self.canal_activo:
                self.agregar_linea(self.txt_canal, f"[📢 {data['remitente']}]: {data['contenido']}")

        elif accion == "ERROR":
            messagebox.showwarning("Aviso", data.get("msg", "Error"))


if __name__ == "__main__":
    root = tk.Tk()
    app = WasapCliente(root)
    root.mainloop()