from app import CheatTrie
from pydantic._internal._validators import min_length_validator
from pathlib import Path
from fastapi import APIRouter, UploadFile, File, HTTPException, Header
from pydantic import BaseModel, Field
from app.core.config import get_settings


router = APIRouter(prefix="/api")

settings = get_settings()

class ChatRequest(BaseModel):
    question:str = Field(min_length=2,max_length=3100)

@router.get("/health")
def health():
    return {"status":"ok","service":"api"}


@router.post("/chat")
def chat(payload: ChatRequest):
    return


# @router.post("/ingest")