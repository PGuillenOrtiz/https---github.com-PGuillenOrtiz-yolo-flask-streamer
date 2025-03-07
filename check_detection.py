import requests
import time
import json
import logging

# Configuración de logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("detection_monitor.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

def check_detection_status():
    """Verifica el estado de detección cada 5 segundos y lo registra"""
    url = "http://192.168.9.30:8080/status"
    
    logger.info("Iniciando monitoreo de detección...")
    
    while True:
        try:
            response = requests.get(url)
            if response.status_code == 200:
                data = response.json()
                
                # Extraer datos
                detection_enabled = data.get("detection_enabled", False)
                last_detection = data.get("last_detection", {})
                pizza_detected = last_detection.get("pizza", False)
                blister_detected = last_detection.get("blister", False)
                timestamp = last_detection.get("timestamp", None)
                
                # Registrar estado
                logger.info(f"Detección activa: {detection_enabled}")
                logger.info(f"Última detección: Pizza: {pizza_detected}, Blister: {blister_detected}")
                logger.info(f"Timestamp: {timestamp}")
                logger.info("-" * 50)
                
            else:
                logger.error(f"Error al obtener estado: HTTP {response.status_code}")
        
        except Exception as e:
            logger.error(f"Error de conexión: {e}")
        
        # Esperar 5 segundos antes de verificar nuevamente
        time.sleep(2)

if __name__ == "__main__":
    check_detection_status()