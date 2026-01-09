from fastapi import FastAPI, HTTPException
from datetime import datetime
from pydantic import BaseModel
from typing import Optional, Dict, Any
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI()

# ================= MODELOS =================
class WorkerRegistration(BaseModel):
    worker_url: str
    worker_name: str = "Luz-AI-Worker"
    auth_token: Optional[str] = None

class ChatRequest(BaseModel):
    message: str
    conversation_id: Optional[str] = None
    user_id: Optional[str] = None

# ================= ALMACENAMIENTO =================
workers_db = {}
worker_counter = 0

# ================= ENDPOINTS =================
@app.get("/")
async def root():
    return {
        "service": "Luz Assistant Cloud Gateway",
        "status": "online",
        "version": "1.0.0",
        "workers_registered": len(workers_db),
        "endpoints": {
            "chat": "POST /api/chat",
            "register_worker": "POST /api/worker/register",
            "health": "GET /health",
            "workers": "GET /api/workers"
        },
        "timestamp": datetime.now().isoformat()
    }

@app.get("/health")
async def health():
    return {
        "status": "healthy",
        "workers": len(workers_db),
        "timestamp": datetime.now().isoformat(),
        "environment": "production"
    }

# 🔥 ENDPOINT CRÍTICO: Para que tu PC se registre
@app.post("/api/worker/register")
async def register_worker(worker: WorkerRegistration):
    """Endpoint para registrar tu PC como worker"""
    global worker_counter
    
    # Token simple de autenticación
    if worker.auth_token != "luz123":
        raise HTTPException(status_code=401, detail="Token inválido")
    
    worker_counter += 1
    worker_id = f"worker_{worker_counter}"
    
    workers_db[worker_id] = {
        "id": worker_id,
        "url": worker.worker_url,
        "name": worker.worker_name,
        "registered_at": datetime.now().isoformat(),
        "last_seen": datetime.now().isoformat()
    }
    
    logger.info(f"Worker registrado: {worker.worker_name}")
    
    return {
        "status": "success",
        "message": "Worker registrado exitosamente",
        "worker_id": worker_id,
        "gateway_url": "https://luz-assistant.onrender.com",
        "heartbeat_endpoint": f"/api/worker/heartbeat/{worker_id}",
        "registered_workers": len(workers_db)
    }

@app.get("/api/workers")
async def list_workers():
    """Listar todos los workers registrados"""
    return {
        "count": len(workers_db),
        "workers": workers_db
    }

@app.post("/api/worker/heartbeat/{worker_id}")
async def worker_heartbeat(worker_id: str):
    """Worker envía latido para mantenerse activo"""
    if worker_id in workers_db:
        workers_db[worker_id]["last_seen"] = datetime.now().isoformat()
        return {"status": "alive", "worker_id": worker_id}
    else:
        raise HTTPException(status_code=404, detail="Worker no encontrado")

# 🔥 ENDPOINT PARA ANDROID: Chat
@app.post("/api/chat")
async def chat(request: ChatRequest):
    """Endpoint principal de chat para Android"""
    
    # Si hay workers registrados, usar el primero
    if workers_db:
        first_worker = next(iter(workers_db.values()))
        worker_url = first_worker["url"]
        
        return {
            "response": f"Luz Assistant Cloud funcionando\n\nMensaje: {request.message}\n\nWorker: {first_worker['name']}",
            "conversation_id": request.conversation_id or f"chat_{int(datetime.now().timestamp())}",
            "timestamp": datetime.now().isoformat(),
            "worker_available": True
        }
    else:
        # Modo sin workers
        return {
            "response": f"Luz Assistant Cloud Gateway\n\nHas dicho: '{request.message}'\n\nServidor: https://luz-assistant.onrender.com\nStatus: Online\nWorkers: Esperando conexión...",
            "conversation_id": request.conversation_id or f"cloud_{int(datetime.now().timestamp())}",
            "timestamp": datetime.now().isoformat(),
            "worker_available": False
        }

# Endpoint de prueba
@app.get("/api/test/echo/{message}")
async def test_echo(message: str):
    """Endpoint de prueba"""
    return {
        "echo": message,
        "server": "luz-assistant.onrender.com",
        "timestamp": datetime.now().isoformat(),
        "note": "Cloud Gateway funcionando"
    }

if __name__ == "__main__":
    import uvicorn
    
    logger.info("Luz Assistant Cloud Gateway iniciando...")
    
    uvicorn.run(app, host="0.0.0.0", port=8000)
