from fastapi import FastAPI
from app.api.endpoints import auth
from app.api.endpoints import projects
from app.api.endpoints import chat_message
from app.api.endpoints import state_machine
from app.api.endpoints import requirements
from app.api.endpoints import files


from fastapi.middleware.cors import CORSMiddleware
from app.core.config import Settings

settings = Settings()   # 
app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router, prefix="/auth", tags=["auth"])
app.include_router(projects.router, prefix="/projects", tags=["projects"])
app.include_router(chat_message.router, prefix="/chat_messages", tags=["chat_messages"])
app.include_router(state_machine.router, prefix="/state_machine", tags=["state_machine"])
app.include_router(requirements.router, prefix="/requirements", tags=["requirements"])
app.include_router(files.router, prefix="/files", tags=["files"])
