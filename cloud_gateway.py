from fastapi import FastAPI, HTTPException, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from datetime import datetime
from pydantic import BaseModel
from typing import Optional, Dict, Any
import logging
import requests
import base64
import tempfile
import os
from pathlib import Path

# ================= CONFIGURACIÓN =================
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Luz Assistant Gateway", version="1.0.0")

# CORS para permitir conexiones desde Android
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # En producción, especifica el dominio de tu app
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# URLs de tus servicios (ajusta según tu configuración)
# Estas son las URLs donde tienes corriendo Whisper, LLM y TTS
SERVICES = {
    "whisper": os.getenv("WHISPER_URL", "http://localhost:9000"),  # Servicio Whisper
    "llm": os.getenv("LLM_URL", "http://localhost:9001"),          # Servicio LLM (Ollama/Llama)
    "tts": os.getenv("TTS_URL", "http://localhost:9002"),          # Servicio TTS (Coqui/XTTs)
}

# ================= MODELOS =================
class WorkerRegistration(BaseModel):
    worker_url: str
    worker_name: str = "Luz-AI-Worker"
    auth_token: Optional[str] = None

class ChatRequest(BaseModel):
    message: str
    conversation_id: Optional[str] = None
    user_id: Optional[str] = None

class TTSRequest(BaseModel):
    text: str
    voice: str = "luz"

# ================= ENDPOINTS =================
@app.get("/")
async def root():
    """Endpoint raíz - Información del gateway"""
    return {
        "service": "Luz Assistant Cloud Gateway",
        "status": "online",
        "version": "1.0.0",
        "services": SERVICES,
        "endpoints": {
            "chat": "POST /api/chat",
            "transcribe": "POST /api/transcribe",
            "tts": "POST /api/tts",
            "health": "GET /health",
            "service_status": "GET /api/services/status"
        },
        "timestamp": datetime.now().isoformat()
    }

@app.get("/health")
async def health_check():
    """Health check simple"""
    return {"status": "healthy", "timestamp": datetime.now().isoformat()}

@app.get("/api/services/status")
async def services_status():
    """Verifica el estado de todos los servicios conectados"""
    status = {}
    
    for service_name, service_url in SERVICES.items():
        try:
            response = requests.get(f"{service_url}/health", timeout=5)
            status[service_name] = {
                "url": service_url,
                "status": "online" if response.status_code == 200 else "error",
                "code": response.status_code
            }
        except requests.exceptions.RequestException as e:
            status[service_name] = {
                "url": service_url,
                "status": "offline",
                "error": str(e)
            }
    
    return {
        "gateway": "online",
        "services": status,
        "timestamp": datetime.now().isoformat()
    }

# ================= ENDPOINT CRÍTICO: TRANSCRIBE =================
@app.post("/api/transcribe")
async def transcribe_audio(audio: UploadFile = File(...)):
    """
    Transcribe audio usando Whisper
    Android envía: Multipart form con campo 'audio'
    """
    logger.info(f"🔊 Transcribiendo audio: {audio.filename}")
    
    try:
        # 1. Guardar audio temporalmente
        audio_content = await audio.read()
        
        if not audio_content or len(audio_content) == 0:
            raise HTTPException(status_code=400, detail="Archivo de audio vacío")
        
        # 2. Crear archivo temporal
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp_file:
            tmp_file.write(audio_content)
            temp_path = tmp_file.name
        
        try:
            # 3. Enviar a servicio Whisper
            whisper_url = SERVICES["whisper"]
            logger.info(f"Enviando a Whisper: {whisper_url}")
            
            with open(temp_path, 'rb') as audio_file:
                files = {'file': (audio.filename, audio_file, audio.content_type)}
                response = requests.post(
                    f"{whisper_url}/transcribe",
                    files=files,
                    timeout=60  # Whisper puede tardar
                )
            
            # 4. Procesar respuesta
            if response.status_code == 200:
                result = response.json()
                transcribed_text = result.get("text", "").strip()
                
                if not transcribed_text:
                    transcribed_text = "No se pudo transcribir el audio"
                    logger.warning("Whisper devolvió texto vacío")
                
                logger.info(f"✅ Transcripción exitosa: {transcribed_text[:50]}...")
                
                return {
                    "text": transcribed_text,
                    "status": "success",
                    "filename": audio.filename,
                    "file_size": len(audio_content),
                    "note": "Transcripción completada por Whisper",
                    "timestamp": datetime.now().isoformat()
                }
            else:
                error_msg = f"Whisper error {response.status_code}: {response.text}"
                logger.error(error_msg)
                
                # Modo de fallback: texto simulado
                fallback_text = "Hola, esto es una transcripción de prueba desde el gateway"
                logger.warning(f"Usando fallback: {fallback_text}")
                
                return {
                    "text": fallback_text,
                    "status": "fallback",
                    "filename": audio.filename,
                    "note": "Servicio Whisper no disponible. Usando texto de prueba.",
                    "timestamp": datetime.now().isoformat()
                }
                
        except requests.exceptions.Timeout:
            logger.error("⏱️ Timeout al conectar con Whisper")
            raise HTTPException(status_code=504, detail="Whisper service timeout")
            
        except requests.exceptions.ConnectionError:
            logger.error("🔌 Error de conexión con Whisper")
            raise HTTPException(status_code=503, detail="Whisper service unreachable")
            
        finally:
            # 5. Limpiar archivo temporal
            if os.path.exists(temp_path):
                os.unlink(temp_path)
                
    except Exception as e:
        logger.error(f"🔥 Error en transcripción: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Gateway error: {str(e)}")

# ================= ENDPOINT CRÍTICO: CHAT =================
@app.post("/api/chat")
async def chat(request: ChatRequest):
    """
    Procesa mensajes con el LLM (Llama/Ollama)
    Android envía: JSON con message, conversation_id, user_id
    """
    logger.info(f"💭 Chat request: {request.message[:50]}...")
    
    try:
        # 1. Preparar payload para LLM
        llm_url = SERVICES["llm"]
        
        payload = {
            "prompt": request.message,
            "conversation_id": request.conversation_id or f"conv_{int(datetime.now().timestamp())}",
            "user_id": request.user_id or "android_user",
            "max_tokens": 500,
            "temperature": 0.7
        }
        
        logger.info(f"Enviando a LLM: {llm_url}")
        
        # 2. Enviar a servicio LLM
        response = requests.post(
            f"{llm_url}/generate",
            json=payload,
            timeout=30
        )
        
        # 3. Procesar respuesta
        if response.status_code == 200:
            result = response.json()
            ai_response = result.get("response", "Lo siento, no pude procesar tu mensaje.")
            
            logger.info(f"✅ Chat response: {ai_response[:50]}...")
            
            return {
                "response": ai_response,
                "conversation_id": request.conversation_id,
                "timestamp": datetime.now().isoformat(),
                "model": result.get("model", "llama"),
                "tokens_used": result.get("tokens_used", 0)
            }
        else:
            error_msg = f"LLM error {response.status_code}: {response.text}"
            logger.error(error_msg)
            
            # Modo de fallback
            fallback_response = f"Luz Assistant Cloud Gateway\n\nHas dicho: '{request.message}'\n\nServidor: https://luz-assistant-claud.onrender.com\nStatus: Online\nNota: LLM service unavailable"
            
            return {
                "response": fallback_response,
                "conversation_id": request.conversation_id,
                "timestamp": datetime.now().isoformat(),
                "note": "LLM service temporarily unavailable",
                "status": "fallback"
            }
            
    except requests.exceptions.Timeout:
        logger.error("⏱️ Timeout en chat")
        raise HTTPException(status_code=504, detail="LLM service timeout")
        
    except requests.exceptions.ConnectionError:
        logger.error("🔌 Error de conexión LLM")
        raise HTTPException(status_code=503, detail="LLM service unreachable")
        
    except Exception as e:
        logger.error(f"🔥 Error en chat: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Chat processing error: {str(e)}")

# ================= ENDPOINT CRÍTICO: TTS =================
@app.post("/api/tts")
async def text_to_speech(request: TTSRequest):
    """
    Convierte texto a voz usando TTS service
    Android envía: JSON con text y voice
    """
    logger.info(f"🔊 TTS request: '{request.text[:50]}...' con voz: {request.voice}")
    
    try:
        # 1. Preparar payload para TTS
        tts_url = SERVICES["tts"]
        
        payload = {
            "text": request.text,
            "voice": request.voice,
            "language": "es",
            "speed": 1.0
        }
        
        logger.info(f"Enviando a TTS: {tts_url}")
        
        # 2. Enviar a servicio TTS
        response = requests.post(
            f"{tts_url}/synthesize",
            json=payload,
            timeout=30
        )
        
        # 3. Procesar respuesta
        if response.status_code == 200:
            # Asumimos que TTS devuelve audio WAV
            audio_content = response.content
            
            if not audio_content or len(audio_content) < 100:  # WAV mínimo
                raise ValueError("TTS devolvió audio inválido")
            
            # Codificar en base64 para Android
            audio_base64 = base64.b64encode(audio_content).decode('utf-8')
            
            logger.info(f"✅ TTS generado: {len(audio_content)} bytes")
            
            return {
                "audio": audio_base64,
                "text": request.text,
                "voice": request.voice,
                "format": "wav",
                "sample_rate": 24000,  # Ajusta según tu TTS
                "duration_seconds": len(audio_content) / (24000 * 2),  # Estimado
                "timestamp": datetime.now().isoformat()
            }
        else:
            error_msg = f"TTS error {response.status_code}: {response.text}"
            logger.error(error_msg)
            
            # Modo de fallback: audio silencioso
            logger.warning("Generando audio de fallback...")
            fallback_audio = generate_silent_audio()
            audio_base64 = base64.b64encode(fallback_audio).decode('utf-8')
            
            return {
                "audio": audio_base64,
                "text": request.text,
                "voice": request.voice,
                "format": "wav",
                "sample_rate": 24000,
                "duration_seconds": 2.0,
                "note": "TTS service unavailable. Using silent audio.",
                "status": "fallback",
                "timestamp": datetime.now().isoformat()
            }
            
    except requests.exceptions.Timeout:
        logger.error("⏱️ Timeout en TTS")
        raise HTTPException(status_code=504, detail="TTS service timeout")
        
    except requests.exceptions.ConnectionError:
        logger.error("🔌 Error de conexión TTS")
        raise HTTPException(status_code=503, detail="TTS service unreachable")
        
    except Exception as e:
        logger.error(f"🔥 Error en TTS: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"TTS processing error: {str(e)}")

# ================= FUNCIONES AUXILIARES =================
def generate_silent_audio(duration_seconds: float = 2.0) -> bytes:
    """Genera audio WAV silencioso como fallback"""
    import wave
    import io
    
    sample_rate = 24000
    num_frames = int(sample_rate * duration_seconds)
    
    # Crear WAV en memoria
    buffer = io.BytesIO()
    
    with wave.open(buffer, 'wb') as wav_file:
        wav_file.setnchannels(1)  # mono
        wav_file.setsampwidth(2)  # 16-bit
        wav_file.setframerate(sample_rate)
        
        # Generar silencio (valores 0 para 16-bit signed PCM)
        silent_data = b'\x00' * (num_frames * 2)  # 2 bytes por muestra
        wav_file.writeframes(silent_data)
    
    buffer.seek(0)
    return buffer.read()

# ================= MANTENER ENDPOINTS EXISTENTES =================
# (Los mantengo por compatibilidad con tu código actual)

workers_db = {}
worker_counter = 0

@app.post("/api/worker/register")
async def register_worker(worker: WorkerRegistration):
    """Registra un nuevo worker (PC con servicios AI)"""
    global worker_counter
    
    worker_id = f"worker_{worker_counter}"
    workers_db[worker_id] = {
        "id": worker_id,
        "name": worker.worker_name,
        "url": worker.worker_url,
        "auth_token": worker.auth_token,
        "registered_at": datetime.now().isoformat(),
        "last_seen": datetime.now().isoformat()
    }
    
    worker_counter += 1
    
    logger.info(f"👷 Worker registrado: {worker.worker_name} ({worker.worker_url})")
    
    return {
        "worker_id": worker_id,
        "status": "registered",
        "message": f"Worker {worker.worker_name} registrado exitosamente",
        "timestamp": datetime.now().isoformat()
    }

@app.get("/api/workers")
async def list_workers():
    """Lista todos los workers registrados"""
    return {
        "count": len(workers_db),
        "workers": workers_db,
        "timestamp": datetime.now().isoformat()
    }

# ================= INICIO DE LA APLICACIÓN =================
if __name__ == "__main__":
    import uvicorn
    
    # Mostrar información de configuración
    logger.info("=" * 50)
    logger.info("🚀 Luz Assistant Gateway iniciando...")
    logger.info(f"📱 Endpoints disponibles:")
    logger.info(f"   • POST /api/transcribe  (Whisper)")
    logger.info(f"   • POST /api/chat        (LLM)")
    logger.info(f"   • POST /api/tts         (TTS)")
    logger.info("=" * 50)
    logger.info("🔧 Configuración de servicios:")
    for service, url in SERVICES.items():
        logger.info(f"   • {service}: {url}")
    logger.info("=" * 50)
    
    # Obtener puerto de Render
    port = int(os.getenv("PORT", 8000))
    
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=port,
        log_level="info",
        access_log=True
    )
