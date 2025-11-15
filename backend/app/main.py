from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routes import chat, ingest, ingest_drive, knowledge, playbook


app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "https://aiclone-production-32dc.up.railway.app",
    ],
    allow_methods=["*"],
    allow_headers=["*"],
    allow_credentials=True,
)

app.include_router(chat.router, prefix="/api/chat")
app.include_router(ingest.router, prefix="/api/ingest")
app.include_router(knowledge.router, prefix="/api/knowledge")
app.include_router(ingest_drive.router, prefix="/api")
app.include_router(playbook.router, prefix="/api/playbook")


@app.get("/")
def root():
    return {"status": "aiclone backend running"}
