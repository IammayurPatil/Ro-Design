"""FastAPI entry point. Run: uvicorn app.main:app --reload (from the backend folder)."""
import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import router

app = FastAPI(title="RO Design API", version="1.0")

origins = os.environ.get("CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173").split(",")
app.add_middleware(CORSMiddleware, allow_origins=origins, allow_methods=["*"], allow_headers=["*"])
app.include_router(router)
