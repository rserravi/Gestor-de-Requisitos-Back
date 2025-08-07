from fastapi import FastAPI

app = FastAPI()

@app.get("/")
def read_root():
    return {"msg": "Gestor de Requisitos-back running!"}
