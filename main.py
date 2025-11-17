import os
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, JSONResponse
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class ChatTurn(BaseModel):
    role: str
    content: str

class ChatRequest(BaseModel):
    message: str
    history: List[ChatTurn] = Field(default_factory=list)
    mode: Optional[str] = None  # e.g., 'ebook'

class EbookPayload(BaseModel):
    id: Optional[str] = None
    title: str
    content: str
    style: str
    progress: int = 0
    updated_at: Optional[datetime] = None


@app.get("/")
def read_root():
    return {"message": "Hello from FastAPI Backend!"}

@app.get("/api/hello")
def hello():
    return {"message": "Hello from the backend API!"}

@app.get("/test")
def test_database():
    """Test endpoint to check if database is available and accessible"""
    response = {
        "backend": "✅ Running",
        "database": "❌ Not Available",
        "database_url": None,
        "database_name": None,
        "connection_status": "Not Connected",
        "collections": []
    }
    
    try:
        # Try to import database module
        from database import db
        
        if db is not None:
            response["database"] = "✅ Available"
            response["database_url"] = "✅ Configured"
            response["database_name"] = db.name if hasattr(db, 'name') else "✅ Connected"
            response["connection_status"] = "Connected"
            
            # Try to list collections to verify connectivity
            try:
                collections = db.list_collection_names()
                response["collections"] = collections[:10]  # Show first 10 collections
                response["database"] = "✅ Connected & Working"
            except Exception as e:
                response["database"] = f"⚠️  Connected but Error: {str(e)[:50]}"
        else:
            response["database"] = "⚠️  Available but not initialized"
            
    except ImportError:
        response["database"] = "❌ Database module not found (run enable-database first)"
    except Exception as e:
        response["database"] = f"❌ Error: {str(e)[:50]}"
    
    # Check environment variables
    import os
    response["database_url"] = "✅ Set" if os.getenv("DATABASE_URL") else "❌ Not Set"
    response["database_name"] = "✅ Set" if os.getenv("DATABASE_NAME") else "❌ Not Set"
    
    return response


@app.post("/api/chat")
async def chat(req: ChatRequest):
    """
    Simple streaming chat endpoint that simulates AI typing by streaming tokens.
    - Accepts current message and history
    - Optional mode 'ebook' will stream step-by-step generation cues
    """
    user_text = req.message.strip()
    if not user_text:
        raise HTTPException(status_code=400, detail="Message cannot be empty")

    async def token_stream():
        import asyncio
        if req.mode == "ebook":
            # Stream a staged plan -> chapters -> cover generation
            stages = [
                (10, "[progress:10] Plan de l'ebook généré.\n\n1. Introduction\n2. Concepts clés\n3. Études de cas\n4. Conclusion\n"),
                (55, "[progress:55] Rédaction des chapitres en cours...\n\nChapitre 1: ...\nChapitre 2: ...\nChapitre 3: ...\n"),
                (85, "[progress:85] Création de la couverture: Titre, sous-titre, auteur, palette.\n"),
                (100, "[progress:100] [done]"),
            ]
            preface = (
                "Voici un plan détaillé, puis une rédaction progressive des chapitres et enfin une proposition de couverture. "
                "Vous pouvez continuer à me donner des instructions pendant la génération.\n\n"
            )
            for ch in preface:
                yield ch
                await asyncio.sleep(0.01)
            for p, text in stages:
                for ch in text:
                    yield ch
                    await asyncio.sleep(0.01)
            return
        else:
            # Generic playful AI response echoing the user
            reply = (
                "Bien sûr! "
                + "Vous avez dit: '" + user_text + "'. "
                + "Voici une réponse utile, avec des idées concrètes et des étapes suivantes."
            )
            for ch in reply:
                yield ch
                await asyncio.sleep(0.01)

    return StreamingResponse(token_stream(), media_type="text/plain")


@app.post("/api/ebook/save")
async def save_ebook(payload: EbookPayload):
    """Save or update ebook draft in MongoDB (autosave)."""
    try:
        from database import db
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database not available: {e}")

    if db is None:
        raise HTTPException(status_code=500, detail="Database not configured")

    doc = payload.model_dump()
    doc["updated_at"] = datetime.utcnow()

    # Use a stable key by title for simplicity in this demo
    existing = db["ebook"].find_one({"title": payload.title})
    if existing:
        db["ebook"].update_one({"_id": existing["_id"]}, {"$set": doc})
        return {"status": "updated", "id": str(existing["_id"]) }
    else:
        res = db["ebook"].insert_one(doc)
        return {"status": "created", "id": str(res.inserted_id)}


@app.get("/api/ebook/list")
async def list_ebooks(limit: int = 20):
    try:
        from database import db
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database not available: {e}")

    if db is None:
        return {"items": []}

    cursor = db["ebook"].find({}).sort("updated_at", -1).limit(limit)
    items = []
    for d in cursor:
        d["id"] = str(d.pop("_id"))
        items.append(d)
    return {"items": items}


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
