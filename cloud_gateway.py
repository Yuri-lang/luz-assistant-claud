import requests
import time
import socket
from datetime import datetime

class WorkerConnector:
    def __init__(self):
        self.cloud_url = "https://luz-assistant.onrender.com"
        self.local_url = "http://localhost:5000"  # app.py usa 5000
        self.worker_id = None
        
    def register_worker(self):
        """Registrar tu PC en la nube"""
        try:
            print("🔄 Registrando worker...")
            
            # Obtener IP local
            local_ip = self._get_local_ip()
            worker_url = f"http://{local_ip}:5000"
            
            response = requests.post(
                f"{self.cloud_url}/api/worker/register",
                json={
                    "worker_url": worker_url,
                    "worker_name": f"PC-{socket.gethostname()}",
                    "auth_token": "luz123"
                },
                timeout=10
            )
            
            if response.status_code == 200:
                data = response.json()
                self.worker_id = data.get('worker_id')
                print(f"✅ Worker registrado: {self.worker_id}")
                print(f"🔗 Worker URL: {worker_url}")
                print(f"☁️  Cloud URL: {self.cloud_url}")
                return True
            else:
                print(f"❌ Error: {response.status_code}")
                print(f"📄 Respuesta: {response.text}")
                return False
                
        except Exception as e:
            print(f"❌ Error: {e}")
            return False
    
    def _get_local_ip(self):
        """Obtener IP local"""
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
            s.close()
            return ip
        except:
            return "localhost"
    
    def start(self):
        """Iniciar conexión"""
        print("\n" + "="*50)
        print("🚀 LUZ ASSISTANT WORKER CONNECTOR")
        print("="*50)
        
        print("\n📋 PRERREQUISITOS:")
        print("1. Tu app.py debe estar corriendo en otra ventana")
        print("2. Debe escuchar en: http://localhost:5000")
        print("3. Verifica con: curl http://localhost:5000/health")
        
        input("\n👉 Presiona Enter cuando app.py esté corriendo...")
        
        # Verificar que app.py esté corriendo
        try:
            response = requests.get("http://localhost:5000/health", timeout=5)
            if response.status_code == 200:
                print("✅ app.py local está funcionando")
            else:
                print("❌ app.py no responde correctamente")
                return
        except:
            print("❌ app.py no está corriendo en puerto 5000")
            return
        
        print("\n🔗 Conectando a la nube...")
        if self.register_worker():
            print("\n" + "="*50)
            print("🎉 ¡CONEXIÓN EXITOSA!")
            print("="*50)
            print(f"📡 Cloud Gateway: {self.cloud_url}")
            print(f"💻 Tu PC (Worker): http://localhost:5000")
            print(f"🆔 Worker ID: {self.worker_id}")
            print("\n📱 Los usuarios pueden usar la app Android con:")
            print(f"   URL: {self.cloud_url}")
            print("\n⏰ Manteniendo conexión activa...")
            print("="*50)
            
            # Mantener conexión activa
            counter = 0
            while True:
                time.sleep(30)  # Esperar 30 segundos
                counter += 1
                print(f"💓 Conectado ({counter}) - {datetime.now().strftime('%H:%M:%S')}")
                
                # Cada 5 minutos, re-registrar
                if counter % 10 == 0:
                    print("🔄 Re-registrando worker...")
                    self.register_worker()
                    
        else:
            print("\n❌ No se pudo conectar a la nube")
            print("💡 Solución:")
            print("1. Verifica tu conexión a internet")
            print("2. Asegúrate que https://luz-assistant.onrender.com esté online")
            print("3. Revisa los logs de Render.com")

if __name__ == "__main__":
    connector = WorkerConnector()
    try:
        connector.start()
    except KeyboardInterrupt:
        print("\n👋 Conexión terminada por usuario")
    except Exception as e:
        print(f"\n💥 Error crítico: {e}")


