# Gestor de Requisitos – Backend

Backend del **Gestor de Requisitos**, una aplicación para capturar, analizar y mejorar requisitos de software con asistencia de IA.  
Desarrollado en **FastAPI** + **SQLModel** + **PostgreSQL**, con integración local con modelos **Ollama**.

---

## 🚀 Características

- **Autenticación JWT** con registro/login de usuarios.
- **Gestión de proyectos** con CRUD completo.
- **Chat interactivo con IA** para:
  - Captura inicial de descripción del proyecto.
  - Preguntas aclaratorias.
  - Generación inicial de requisitos.
  - Análisis y mejora iterativa de requisitos.
  - Modo de conversación libre (tipo ChatGPT).
- **Máquina de estados** (`StateMachine`) para orquestar el flujo:
  - `init` → `software_questions` → `new_requisites` → `stall`
  - Ciclo iterativo `stall` ↔ `analyze_requisites`.
- **Gestión de requisitos** con soporte de categorías, prioridades y estados.
- **Soporte multi-idioma** para interacción con la IA.
- **Carga de archivos de ejemplo** (usados solo en generación/análisis de requisitos).

---

## 📂 Estructura principal

app/
├── api/
│ └── endpoints/
│ ├── auth.py # Registro/Login de usuarios
│ ├── projects.py # CRUD de proyectos
│ ├── chat_message.py # Lógica de chat y máquina de estados
│ └── state_machine.py # Control de cambios de estado
│
├── models/ # Modelos SQLModel (User, Project, Requirement, StateMachine, ChatMessage)
├── schemas/ # Schemas Pydantic para validación de entrada/salida
├── utils/
│ ├── ollama_client.py # Cliente para llamar al modelo local Ollama
│ ├── prompt_loader.py # Carga de plantillas de prompt
│ ├── message_loader.py # Carga de mensajes predefinidos
│ └── analyze_parser.py # Parser de salida de IA en análisis de requisitos
│
├── database.py # Configuración y conexión a PostgreSQL
└── main.py # Punto de entrada FastAPI


---

## 🛠 Requisitos previos

- **Python** 3.11+
- **PostgreSQL**
- **Ollama** instalado y ejecutando el modelo configurado (por defecto `llama3:8b`)
- **Poetry** o `pip` para gestionar dependencias

---

## ⚙️ Instalación

```bash
# Clonar repositorio
git clone https://github.com/tu-org/gestor-requisitos-backend.git
cd gestor-requisitos-backend

# Crear entorno virtual e instalar dependencias
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Variables de entorno (ejemplo)
export DATABASE_URL=postgresql://usuario:password@localhost:5432/gestorrequisitos
export SECRET_KEY=clave_secreta
# URL base de Ollama (opcional, por defecto http://localhost:11434)
export OLLAMA_URL=http://localhost:11434
# Log SQL detallado (opcional, por defecto deshabilitado)
export SQL_ECHO=true

# Crear tablas
python3 -m create_tables

# Ejecutar backend
uvicorn app.main:app --reload
```

# Flujo de trabajo
## Estados de StateMachine
**init** – El sistema solicita al usuario una descripción inicial de su proyecto.

**software_questions** – La IA formula preguntas aclaratorias basadas en esa descripción.

**new_requisites** – La IA genera un listado inicial de requisitos en formato estructurado.

**stall** – Edición libre de requisitos y conversación libre con la IA.

**analyze_requisites** – La IA analiza la lista actual de requisitos y formula nuevas preguntas para mejorarlos.

init → software_questions → new_requisites → stall
        ↑                                      ↓
        └────────────── analyze_requisites ───┘

# Endpoints Principales

| Método | Ruta                          | Descripción                   |
| ------ | ----------------------------- | ----------------------------- |
| POST   | `/auth/register`              | Registro de usuario           |
| POST   | `/auth/login`                 | Login de usuario              |
| GET    | `/auth/me`                    | Datos del usuario autenticado |
| GET    | `/projects`                   | Listar proyectos              |
| POST   | `/projects`                   | Crear proyecto                |
| GET    | `/chat_messages/project/{id}` | Mensajes de un proyecto       |
| POST   | `/chat_messages`              | Enviar mensaje (IA o usuario) |
| GET    | `/state_machine/project/{id}` | Estado actual                 |
| POST   | `/state_machine/project/{id}` | Cambiar estado                |


# Integración con Ollama
## Generación de prompts:
Los prompts están en **static/prompts/*.txt** y se formatean con **prompt_loader.py**.

## Modelos soportados:
Por defecto llama3:8b pero configurable vía OLLAMA_MODEL.

La URL base del servicio Ollama se configura mediante `OLLAMA_URL` o el
atributo `ollama_url` en `Settings`; si no se especifica, se usará
`http://localhost:11434`.

## Modo stall:
Los mensajes se envían sin prompt fijo; el backend compone contexto con la conversación previa y requisitos actuales.

# 📌 Notas importantes
Los archivos de ejemplo no se usan en el modo stall salvo que el usuario lo indique explícitamente.

El idioma de interacción se guarda en StateMachine.extra["lang"] y se fuerza en todos los prompts.

El token JWT expira; es recomendable implementar refresh tokens en el frontend para evitar redirecciones a login.

# 📜 Licencia
MIT – Uso libre con atribución.