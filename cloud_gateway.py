from fastapi import FastAPI, HTTPException, UploadFile, File
from datetime import datetime
from pydantic import BaseModel
from typing import Optional, Dict, Any
import logging
import io
import base64
from fastapi.responses import Response

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

class TranscriptionRequest(BaseModel):
    text: str
    voice: str = "luz"

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
            "transcribe": "POST /api/transcribe",
            "tts": "POST /api/tts",
            "register_worker": "POST /api/worker/register",
            "health": "GET /health",
            "workers": "GET /api/workers"
        },
        "timestamp": datetime.now().isoformat()
    }

# ... (tus otros endpoints existentes se mantienen igual) ...

# 🔥 NUEVO ENDPOINT: Transcribir audio con Whisper
@app.post("/api/transcribe")
async def transcribe_audio(audio: UploadFile = File(...)):
    """
    Transcribe audio usando Whisper (simulado por ahora)
    """
    try:
        logger.info(f"Transcribiendo audio: {audio.filename}, tamaño: {audio.size}")
        
        # Por ahora, devolvemos un texto simulado
        # En el futuro, esto llamará a tu PC worker o a OpenAI directamente
        simulated_text = "Hola, esto es una transcripción de prueba desde el gateway"
        
        return {
            "text": simulated_text,
            "filename": audio.filename,
            "file_size": audio.size,
            "status": "transcribed",
            "note": "Esta es una transcripción simulada. Configura tu worker para transcripción real.",
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error en transcripción: {e}")
        raise HTTPException(status_code=500, detail=f"Error de transcripción: {str(e)}")

# 🔥 NUEVO ENDPOINT: Text-to-Speech
@app.post("/api/tts")
async def text_to_speech(request: Dict[str, Any]):
    """
    Convierte texto a voz (simulado por ahora)
    Devuelve un archivo de audio WAV base64
    """
    try:
        text = request.get("text", "Hola, soy Luz Assistant")
        voice = request.get("voice", "luz")
        
        logger.info(f"Generando TTS: '{text}' con voz: {voice}")
        
        # Por ahora, devolvemos un audio WAV simulado (silencioso)
        # En el futuro, esto generará audio real o lo pedirá al worker
        
        # Crear un archivo WAV de silencio (1 segundo, 16-bit, mono, 44100 Hz)
        import wave
        import tempfile
        
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp_file:
            with wave.open(tmp_file.name, 'wb') as wav_file:
                wav_file.setnchannels(1)  # mono
                wav_file.setsampwidth(2)  # 16-bit
                wav_file.setframerate(44100)  # 44.1kHz
                
                # 1 segundo de silencio (0s)
                silent_frames = b'\x00' * (44100 * 2)  # 44100 frames * 2 bytes
                wav_file.writeframes(silent_frames)
            
            # Leer el archivo como bytes
            with open(tmp_file.name, 'rb') as f:
                audio_bytes = f.read()
        
        # Convertir a base64 para la respuesta
        audio_base64 = base64.b64encode(audio_bytes).decode('utf-8')
        
        return {
            "audio": audio_base64,
            "text": text,
            "voice": voice,
            "format": "wav",
            "sample_rate": 44100,
            "duration_seconds": 1.0,
            "note": "Audio simulado. Configura tu worker para TTS real.",
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error en TTS: {e}")
        raise HTTPException(status_code=500, detail=f"Error de TTS: {str(e)}")

# Endpoint de chat existente (ya lo tienes)
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

if __name__ == "__main__":
    import uvicorn
   
    logger.info("Luz Assistant Cloud Gateway iniciando...")
   
    uvicorn.run(app, host="0.0.0.0", port=8000)
