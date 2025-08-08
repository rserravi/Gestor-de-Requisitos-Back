D. Crea y activa entorno virtual

python3 -m venv venv
source venv/bin/activate

E. Instala FastAPI, Uvicorn y dependencias principales

pip install fastapi uvicorn[standard] python-multipart pydantic[dotenv] python-jose[cryptography] passlib[bcrypt] sqlmodel psycopg2-binary
