from fastapi import FastAPI
from app.api.endpoints import auth
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
