import threading
import time
import logging
import requests

# Configuración de logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("phantom_client.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

def phantom_client():
    """
    Cliente fantasma que mantiene activa la detección 
    conectándose periódicamente al endpoint de video
    """
    url = "http://192.168.9.30:8080"
    
    # Primero activamos la detección
    logger.info("Iniciando cliente fantasma...")
    
    try:
        # Activar detección
        response = requests.post(f"{url}/start_detection")
        if response.status_code == 200:
            logger.info("Detección activada correctamente")
        else:
            logger.error(f"Error al activar detección: HTTP {response.status_code}")
    
        # Conectar al stream de video y mantener la conexión
        while True:
            try:
                logger.info("Conectando al stream de video...")
                # Hacer una conexión al stream pero no procesar los datos
                response = requests.get(f"{url}/video_feed", stream=True)
                
                # Leer algunos bytes para mantener la conexión activa
                for chunk in response.iter_content(chunk_size=1024):
                    if chunk:
                        # Procesamos unos pocos chunks y luego reconectamos
                        # para evitar consumir demasiada memoria/ancho de banda
                        break
                
                logger.info("Reconectando...")
                time.sleep(5)  # Esperar antes de reconectar
                
            except Exception as e:
                logger.error(f"Error de conexión: {e}")
                time.sleep(10)  # Esperar más tiempo si hay error
    
    except KeyboardInterrupt:
        logger.info("Cliente fantasma detenido manualmente")
    except Exception as e:
        logger.error(f"Error inesperado: {e}")

if __name__ == "__main__":
    phantom_client()