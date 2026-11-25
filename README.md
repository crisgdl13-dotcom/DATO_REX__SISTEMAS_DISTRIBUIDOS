# Wasap – Equipo Dato_Rex

**Práctica 1 – Sistemas Distribuidos (Grupo 2TV6):** Sistema de mensajería instantánea cliente-servidor construido con sockets TCP puros en Python (sin WebSockets y sin páginas web) y persistencia en SQL Server.

## Funcionalidades

* **Registro e inicio de sesión:** Autenticación con nombre de usuario, contraseña y foto de perfil opcional (`.png` / `.gif`, máx. 250 KB codificada en Base64). Si el usuario no existe, se registra automáticamente.
* **Chat general:** Mensajes en tiempo real (*broadcast*) para todos los usuarios conectados, mostrando quién los envía e historial reciente.
* **Mensaje directo:** Chat privado 1 a 1 con cualquier usuario conectado, con carga de historial previo.
* **Grupos:** Creación de grupos seleccionando usuarios conectados; los mensajes se envían y almacenan únicamente para los integrantes del grupo.
  * **Función extra (Meme):** Botón *"Sálganse del grupo, quiero estar solo"* que expulsa a todos los demás miembros del grupo activo tanto en tiempo real como en la base de datos.
* **Canales de difusión:** Cualquier usuario puede crear un canal; únicamente el dueño puede publicar mensajes, mientras que los suscriptores pueden unirse, consultar el historial y leer en tiempo real (con barra de escritura bloqueada).
* *Eliminación de mensajes:* Cada usuario puede seleccionar o hacer clic derecho sobre sus propios mensajes (en Chat General, DM, Grupos o Canales) para borrarlos para todos en tiempo real y en la base de datos (🚫 Este mensaje fue eliminado).
*


## Arquitectura

```text
Clientes (Tkinter)  <--- TCP, un JSON por línea (\n) --->  servidor.py (puerto 3001)  <--->  SQL Server (Dato_Rex_DB)
```

* **Cliente (`cliente.py`):** Interfaz gráfica desarrollada con `tkinter`. Multiplataforma (Windows, GNU/Linux y macOS) sin dependencias externas.
* **Servidor (`servidor.py`):** Demonio concurrente sin interfaz gráfica (`threading` + `Lock`) que gestiona conexiones, autenticación, enrutamiento de mensajes y consultas SQL.
* **Base de datos (`Dato_Rex_DB`):** Instancia de SQL Server en puerto `1433` que almacena usuarios, avatares, grupos, canales e historiales de mensajes.

## Instrucciones - Cliente

* **Paso 1. Instalar Git y Python 3 (en caso de no tenerlos instalados)

En Windows (PowerShell):

PowerShell
winget install -e --id Git.Git
winget install -e --id Python.Python.3.12
(Si se instalan por primera vez, cerrar y abrir una nueva terminal para que reconozca los comandos).

En GNU/Linux (Ubuntu / Debian):

Bash
sudo apt update && sudo apt install -y git python3 python3-tk

* **Paso 2. Clonar el repositorio y entrar a la carpeta
Abra una terminal en la ubicación donde desee guardar el proyecto (por ejemplo, Descargas o Escritorio) y ejecute:

Bash
git clone https://github.com/crisgdl13-dotcom/DATO_REX__SISTEMAS_DISTRIBUIDOS.git
cd DATO_REX__SISTEMAS_DISTRIBUIDOS

* **Paso 3. Ejecutar la aplicación cliente
Dentro de la carpeta DATO_REX__SISTEMAS_DISTRIBUIDOS, inicie el cliente gráfico:

En Windows:
PowerShell
python cliente.py

En GNU/Linux o macOS:
Bash
python3 cliente.py

* **Paso 4. Acceso al sistema
El cliente ya está configurado para conectarse automáticamente a nuestro servidor activo (3.149.102.2, puerto 3001). En la ventana de inicio, ingrese un nombre de usuario y contraseña (opcionalmente puede cargar una foto .png o .gif menor a 250 KB) y dé clic en Conectar / Registrar para probar las 4 secciones (Chat General, Mensaje Directo, Grupos —con el botón extra de expulsión— y Canales).

El cliente se conecta por defecto al servidor del equipo en **`3.149.102.2`**, puerto **`3001`** (definidos en las constantes `SERVIDOR_IP` y `SERVIDOR_PUERTO` al inicio de `cliente.py`).

### Uso
1. Escribe un nombre de usuario y contraseña (opcionalmente elige una foto `.png` o `.gif`) y pulsa **Conectar / Registrar**.
2. Si el usuario no existe se crea la cuenta automáticamente; si ya existe, se valida su contraseña.
3. Navega entre las pestañas: **1. Chat General**, **2. Mensaje Directo**, **3. Grupos** y **4. Canales**.
4. Para probar los chats privados, grupos y canales en tiempo real, abre el cliente en dos o más computadoras (o terminales) con usuarios distintos.

## Ejecutar el servidor (En caso de ser necesario, ya que el servidor ya se encuentra en ejecución en 3.149.102.2:3001. Solo es necesario ejecutar el cliente.)

**Requisitos:** Python 3.8+, `pyodbc`, **ODBC Driver 18 for SQL Server** y acceso a la base de datos `Dato_Rex_DB`.

```bash
pip install pyodbc
# Configurar usuario y contraseña de SQL Server en CONN_STR dentro de servidor.py
python3 servidor.py      # escucha en 0.0.0.0:3001
```

*(Las credenciales reales de la base de datos no están incluidas en el repositorio).*

## Base de datos

La base `Dato_Rex_DB` está compuesta por 9 tablas relacionales:
`Usuarios`, `Mensajes_Generales`, `Mensajes_Directos`, `Grupos`, `Grupo_Miembros`, `Mensajes_Grupo`, `Canales`, `Canal_Suscriptores` y `Mensajes_Canal`.

## Protocolo de mensajes

Cada mensaje se envía como un objeto **JSON en una sola línea (UTF-8) terminada en `\n`**. El campo `accion` indica la operación.

### Cliente → Servidor

| `accion` | Campos |
| :--- | :--- |
| `AUTH` | `username`, `password`, `foto_perfil` (Base64) |
| `ENVIAR_GENERAL` | `contenido` |
| `HISTORIAL_DM` | `con_usuario` |
| `ENVIAR_DM` | `destino`, `contenido` |
| `CREAR_GRUPO` | `nombre`, `miembros` (lista) |
| `HISTORIAL_GRUPO` | `id_grupo` |
| `ENVIAR_GRUPO` | `id_grupo`, `contenido` |
| `SALGANSE_GRUPO` | `id_grupo` |
| `CREAR_CANAL` | `nombre` |
| `UNIRSE_CANAL` | `id_canal` |
| `ENVIAR_CANAL` | `id_canal`, `contenido` |
| `ELIMINAR_MENSAJE` | `tipo` (`general`, `dm`, `grupo`, `canal`), `id_mensaje` |

### Servidor → Cliente

| `accion` | Campos |
| :--- | :--- |
| `AUTH_RESP` | `ok`, `username`, `foto_perfil`, `msg` |
| `USUARIOS_CONECTADOS` | `usuarios` (lista) |
| `MSG_GENERAL` | `remitente`, `contenido` |
| `HISTORIAL_DM_RESP` | `con_usuario`, `mensajes` (lista de `remitente`, `destino`, `contenido`) |
| `MSG_DM` | `remitente`, `destino`, `contenido` |
| `LISTA_GRUPOS` | `grupos` (lista de `id_grupo`, `nombre`) |
| `HISTORIAL_GRUPO_RESP` | `id_grupo`, `mensajes` (lista de `remitente`, `contenido`) |
| `MSG_GRUPO` | `id_grupo`, `remitente`, `contenido` |
| `EXPULSADO_GRUPO` | `id_grupo`, `por`, `nombre_grupo` |
| `LISTA_CANALES` | `canales` (lista de `id_canal`, `nombre`, `dueno`) |
| `CANAL_UNIDO` | `id_canal`, `nombre`, `es_dueno`, `mensajes` |
| `MSG_CANAL` | `id_canal`, `remitente`, `contenido` |
| `MENSAJE_ELIMINADO` | `tipo`, `id_mensaje`, `remitente`, `texto` (más `destino`, `id_grupo` o `id_canal` según el chat) |**
| `ERROR` | `msg` |

## Estructura del repositorio

```text
├── cliente.py    # Cliente con interfaz gráfica (Tkinter)
├── servidor.py   # Servidor concurrente de sockets TCP
├── README.md     # Documentación del proyecto
└── LICENSE       # Licencia MIT
```

## Integrantes (Equipo Dato_Rex)

* **Garnica González Christopher Aldair**
* *Ayala Rodriguez Axel Alejandro*
* **Hernández Avilés Luis Alberto**

## Licencia

MIT. Ver el archivo `LICENSE`.
