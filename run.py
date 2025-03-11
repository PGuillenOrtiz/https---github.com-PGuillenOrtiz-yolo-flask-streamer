from flask import Flask, render_template, Response, jsonify
from app.camera import generate_frames, VideoCamera
from config import Config
import logging
import threading
import time
import atexit
from app.camera import cleanup

app = Flask(__name__, template_folder='app/templates')
app.config.from_object(Config)

# Configuración de logging
logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

# Shared state object to control detection
class SharedState:
    detection_enabled = True  # Cambiado a True por defecto
    last_detection = {"pizza": False, "blister": False, "timestamp": None}

shared_state = SharedState()

# Inicializar la cámara y el proceso de detección al arrancar
camera_instance = None

def initialize_detection():
    """Inicializa la cámara y activa la detección automáticamente"""
    global camera_instance
    logger.info("Inicializando sistema de detección...")
    camera_instance = VideoCamera(app.config)
    shared_state.detection_enabled = True
    logger.info("Sistema de detección inicializado")

# Iniciar en un thread separado para no bloquear el arranque
threading.Thread(target=initialize_detection, daemon=True).start()

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/video_feed')
def video_feed():
    logger.info(f"Video feed requested, detection_enabled={shared_state.detection_enabled}")
    return Response(generate_frames(app.config, shared_state), mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route('/start_detection', methods=['POST'])
def start_detection():
    shared_state.detection_enabled = True
    logger.info("Detection started")
    logger.info(f"detection_enabled={shared_state.detection_enabled}")
    return jsonify(success=True)

@app.route('/stop_detection', methods=['POST'])
def stop_detection():
    shared_state.detection_enabled = False
    logger.info("Detection stopped")
    logger.info(f"detection_enabled={shared_state.detection_enabled}")
    return jsonify(success=True)

@app.route('/status', methods=['GET'])
def status():
    """Endpoint para verificar el estado de la detección y PLC"""
    from app.camera import _counter_pizza_sin_blister, _counter_pizza_con_blister, _counter_total
    
    # Asegurarse de que todos los campos necesarios estén presentes
    detection_data = shared_state.last_detection.copy()
    
    # Forzar la actualización de los contadores desde las variables globales
    detection_data["counter_sin_blister"] = _counter_pizza_sin_blister
    detection_data["counter_con_blister"] = _counter_pizza_con_blister
    detection_data["counter_total"] = _counter_total
    
    # Calcular porcentajes
    total = detection_data["counter_total"] if detection_data["counter_total"] > 0 else 1
    detection_data["porcentaje_sin_blister"] = (detection_data["counter_sin_blister"] / total) * 100
    detection_data["porcentaje_con_blister"] = (detection_data["counter_con_blister"] / total) * 100
    
    # Verificar estado de conexión OPC-UA
    from app.camera import _opcua_client
    opcua_connected = _opcua_client and _opcua_client.connected if _opcua_client else False
    
    return jsonify({
        "detection_enabled": shared_state.detection_enabled,
        "last_detection": detection_data,
        "plc_signals": {
            "bit0_pizza_sin_blister": detection_data.get("pizza", False) and not detection_data.get("blister", False),
            "bit1_pizza_con_blister": detection_data.get("pizza", False) and detection_data.get("blister", False)
        },
        "opcua_connected": opcua_connected,
        "system_status": "active" if camera_instance is not None else "initializing"
    })

# Añadir o modificar la ruta para el estado de detección

@app.route('/api/detection_status', methods=['GET'])
def detection_status():
    """Devuelve el estado actual de la detección"""
    return jsonify({
        "detection_enabled": shared_state.detection_enabled,
        "last_detection": shared_state.last_detection,
    })

# Añadir esta ruta a tu archivo run.py

@app.route('/api/reset_counters', methods=['POST'])
def api_reset_counters():
    """Resetea los contadores de detección"""
    from app.camera import reset_counters
    reset_counters()
    return jsonify({"success": True, "message": "Contadores reiniciados"})

# Registrar función de limpieza al salir
atexit.register(cleanup)

# Solo ejecutar esto si se llama directamente, no cuando se importa
if __name__ == '__main__':
    app.run(host='192.168.9.30', port=5000, threaded=True, debug=False)