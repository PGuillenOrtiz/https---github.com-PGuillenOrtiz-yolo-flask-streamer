import cv2
import os
from typing import Dict, Tuple, Optional
from ultralytics import YOLO
import numpy as np
import logging
import threading
import time
import datetime
from concurrent.futures import ThreadPoolExecutor

# Importar biblioteca para OPC-UA
try:
    from opcua import Client, ua
    # Verificar que Client es una clase válida
    if not callable(Client):
        raise ImportError("Client class is not callable")
    OPCUA_AVAILABLE = True
except ImportError as e:
    OPCUA_AVAILABLE = False
    Client = None  # Definir Client como None para evitar NameError
    ua = None
    logger.error(f"La biblioteca opcua no está instalada o es incorrecta: {e}. La comunicación con el PLC no estará disponible.")

# Configuración de logging
logger = logging.getLogger(__name__)

# Variables globales para la cámara y detección
_camera_instance = None
_camera_lock = threading.RLock()
_background_detection_active = False
_latest_frame = None
_latest_frame_lock = threading.Lock()
_latest_detections = {}
_thread_pool = ThreadPoolExecutor(max_workers=5)

# Contadores para estadísticas de detección
_counter_pizza_sin_blister = 0
_counter_pizza_con_blister = 0
_counter_total = 0
_counters_lock = threading.Lock()

# Cliente OPC-UA global para mantener una conexión persistente
_opcua_client = None
_opcua_reconnect_thread = None
_opcua_should_reconnect = True  # Flag para controlar el hilo de reconexión
_thread_pool = ThreadPoolExecutor(max_workers=10)  # Pool de hilos compartido

class OPCUAClient:
    """
    Clase para gestionar la comunicación con el PLC usando OPC-UA de forma persistente.
    Se conecta al servidor OPC-UA una sola vez y se utiliza la conexión para todas las operaciones.
    """
    def __init__(self, config):
        # Verificar disponibilidad antes de usar Client
        if not OPCUA_AVAILABLE:
            logger.error("OPC UA no disponible, inicialización fallida")
            self.client = None
            self.connected = False
            return
        
        self.url = config.get('OPCUA_URL', 'opc.tcp://192.168.9.20:4840')
        self.node_sin_blister_id = config.get('OPCUA_NODE_SIN_BLISTER', 'ns=4;i=3')
        self.node_con_blister_id = config.get('OPCUA_NODE_CON_BLISTER', 'ns=4;i=4')
        self.client = Client(self.url)
        self.node_sin_blister = None
        self.node_con_blister = None
        self.connected = False
        self.lock = threading.Lock()
        self.reconnect_interval = 5  # Intentar reconectar cada 5 segundos
        self.last_connection_attempt = 0  # Timestamp del último intento de conexión
        
        # Iniciar thread de reconexión automática
        self.start_reconnect_thread()
    
    def start_reconnect_thread(self):
        """Inicia un thread que monitorea y restablece la conexión con el servidor OPC-UA"""
        global _opcua_reconnect_thread
        global _opcua_should_reconnect
        
        if _opcua_reconnect_thread is None or not _opcua_reconnect_thread.is_alive():
            _opcua_should_reconnect = True
            _opcua_reconnect_thread = threading.Thread(
                target=self._reconnect_loop,
                daemon=True
            )
            _opcua_reconnect_thread.start()
            logger.info("Thread de reconexión OPC-UA iniciado")
        
    def _reconnect_loop(self):
        """Loop en background que intenta reconectar periódicamente si se pierde la conexión"""
        global _opcua_should_reconnect
        
        logger.info("Thread de reconexión OPC-UA iniciado")
        consecutive_failures = 0
        
        while _opcua_should_reconnect:
            try:
                # Si no está conectado, intentar conectar
                if not self.connected:
                    # Reiniciar completamente el cliente después de varios fallos
                    if consecutive_failures > 10:
                        logger.warning("Múltiples fallos consecutivos. Recreando cliente OPC-UA...")
                        try:
                            self.client.disconnect()
                        except:
                            pass
                        self.client = Client(self.url)
                        consecutive_failures = 0
                    
                    success = self.connect(force=True)
                    if success:
                        consecutive_failures = 0
                    else:
                        consecutive_failures += 1
                # Si está conectado, verificar que la conexión sigue activa
                elif self.connected:
                    if self.check_connection():
                        consecutive_failures = 0
                    else:
                        consecutive_failures += 1
                        logger.warning(f"La conexión al servidor OPC-UA parece estar caída ({consecutive_failures} fallos)")
                
                # Ajustar intervalo según número de fallos (backoff exponencial limitado)
                wait_time = min(self.reconnect_interval * (1 + consecutive_failures * 0.2), 30)
                time.sleep(wait_time)
            except Exception as e:
                logger.error(f"Error en thread de reconexión OPC-UA: {e}")
                consecutive_failures += 1
                time.sleep(self.reconnect_interval)
                
    def check_connection(self):
        """Verifica si la conexión sigue activa"""
        try:
            # Intentar una operación simple para verificar conexión
            if self.client and hasattr(self.client, "uaclient") and self.client.uaclient:
                try:
                    # Leer un atributo del servidor para verificar la conexión
                    self.client.get_namespace_array()
                    return True
                except Exception:
                    logger.warning("Conexión OPC-UA inactiva, marcando como desconectado")
                    self.connected = False
                    return False
            else:
                self.connected = False
                return False
        except Exception:
            self.connected = False
            return False
        
    def connect(self, force=False):
        """Establece la conexión si no está ya conectada."""
        with self.lock:
            # Si ya está conectado y no es forzado, salir
            if self.connected and not force:
                return True
            
            # Limitar frecuencia de intentos
            current_time = time.time()
            if not force and current_time - self.last_connection_attempt < self.reconnect_interval:
                return self.connected
                
            self.last_connection_attempt = current_time
            
            # Intentar desconectar primero si ya estaba conectado
            try:
                self.client.disconnect()
            except Exception:
                pass
            
            # Intentar conectar
            try:
                logger.info(f"Intentando conectar al servidor OPC-UA en {self.url}...")
                self.client.connect()
                
                # Obtener los nodos
                try:
                    self.node_sin_blister = self.client.get_node(self.node_sin_blister_id)
                    self.node_con_blister = self.client.get_node(self.node_con_blister_id)
                    
                    logger.info(f"Nodo sin blister: {self.node_sin_blister.nodeid}")
                    logger.info(f"Nodo con blister: {self.node_con_blister.nodeid}")
                    
                    self.connected = True
                    logger.info(f"✓ Conexión OPC-UA establecida con {self.url}")
                    return True
                except Exception as e:
                    logger.error(f"Error al obtener nodos OPC-UA: {e}")
                    self.connected = False
                    try:
                        self.client.disconnect()
                    except:
                        pass
                    return False
            except Exception as e:
                logger.error(f"✗ Error al conectar con servidor OPC-UA: {e}")
                self.connected = False
                return False

    def disconnect(self):
        """Cierra la conexión si está abierta."""
        with self.lock:
            if self.connected:
                try:
                    self.client.disconnect()
                    self.connected = False
                    logger.info("Conexión con el servidor OPC-UA cerrada.")
                except Exception as e:
                    logger.error(f"Error al desconectar del servidor OPC-UA: {e}")
                    self.connected = False

    def write_value(self, node, value: bool):
        """Escribe un valor booleano en un nodo OPC-UA"""
        with self.lock:
            if not self.connected:
                self.connect()
                if not self.connected:
                    logger.warning(f"No se pudo escribir valor: OPC-UA no conectado")
                    return False
            
            try:
                dv = ua.DataValue(ua.Variant(value, ua.VariantType.Boolean))
                node.set_attribute(ua.AttributeIds.Value, dv)
                return True
            except Exception as e:
                logger.error(f"Error al escribir valor en nodo OPC-UA: {e}")
                self.connected = False
                return False
    
    def write_pizza_sin_blister(self, value: bool):
        """Escribe en el nodo correspondiente a pizza sin blister"""
        return self.write_value(self.node_sin_blister, value)
    
    def write_pizza_con_blister(self, value: bool):
        """Escribe en el nodo correspondiente a pizza con blister"""
        return self.write_value(self.node_con_blister, value)
    
    def generate_pulse_pizza_sin_blister(self):
        """Genera un pulso en el nodo de pizza sin blister sin bloquear el hilo principal"""
        global _thread_pool
        
        # Usar el pool de hilos en lugar de crear uno nuevo cada vez
        _thread_pool.submit(self._execute_pulse_pizza_sin_blister)
        return True  # Siempre retorna True para no bloquear el flujo

    def _execute_pulse_pizza_sin_blister(self):
        """Método interno para ejecutar el pulso"""
        try:
            if not self.connected:
                logger.info("Intentando reconectar al OPC-UA antes de enviar pulso...")
                self.connect(force=True)
            
            # Intentar enviar pulso aunque la conexión falle
            try:
                if self.write_pizza_sin_blister(True):
                    time.sleep(0.1)  # Pequeña pausa para el flanco
                    self.write_pizza_sin_blister(False)
                    logger.info("✅ Pulso pizza sin blister enviado correctamente")
                else:
                    logger.warning("⚠️ No se pudo enviar pulso pizza sin blister")
            except Exception as e:
                logger.error(f"❌ Error al enviar pulso pizza sin blister: {e}")
        except Exception as e:
            logger.error(f"❌ Error en thread de pulso: {e}")

    def generate_pulse_pizza_con_blister(self):
        """Genera un pulso en el nodo de pizza con blister sin bloquear el hilo principal"""
        global _thread_pool
        
        # Usar el pool de hilos en lugar de crear uno nuevo cada vez
        _thread_pool.submit(self._execute_pulse_pizza_con_blister)
        return True  # Siempre retorna True para no bloquear el flujo

    def _execute_pulse_pizza_con_blister(self):
        """Método interno para ejecutar el pulso"""
        try:
            if not self.connected:
                logger.info("Intentando reconectar al OPC-UA antes de enviar pulso...")
                self.connect(force=True)
            
            # Intentar enviar pulso aunque la conexión falle
            try:
                if self.write_pizza_con_blister(True):
                    time.sleep(0.1)  # Pequeña pausa para el flanco
                    self.write_pizza_con_blister(False)
                    logger.info("✅ Pulso pizza con blister enviado correctamente")
                else:
                    logger.warning("⚠️ No se pudo enviar pulso pizza con blister")
            except Exception as e:
                logger.error(f"❌ Error al enviar pulso pizza con blister: {e}")
        except Exception as e:
            logger.error(f"❌ Error en thread de pulso: {e}")

class VideoCamera:
    def __init__(self, config):
        self.config = config
        global _camera_instance
        global _camera_lock
        global _background_detection_active
        global _opcua_client
        
        # Inicializar la conexión OPC-UA con sistema de reconexión
        if _opcua_client is None:
            logger.info("Inicializando cliente OPC-UA con reconexión automática")
            _opcua_client = OPCUAClient(config)
            # El cliente ahora maneja su propia reconexión automática
        
        with _camera_lock:
            if _camera_instance is None:
                logger.info("Inicializando cámara compartida")
                _camera_instance = cv2.VideoCapture(config['VIDEO_SOURCE'])
                if not _camera_instance.isOpened():
                    logger.error("Error abriendo la cámara")
                else:
                    # Iniciar el proceso de detección en segundo plano
                    self.start_background_detection_thread(config)
        
        self.cap = _camera_instance
        self.model = self.initialize_model()
        self.previous_red = False  # Para detectar flanco de subida
        self.previous_green = False  # Para detectar flanco de subida
        self.frame_lock = threading.Lock()

    def start_background_detection_thread(self, config):
        """Avvia un thread dedicato per il rilevamento in background"""
        global _background_detection_active
        _background_detection_active = True  # Imposta a True prima di avviare il thread
        logger.info("Avvio thread di rilevamento in background")
        bg_thread = threading.Thread(
            target=self.background_detection_loop,
            args=(config,),
            daemon=True
        )
        bg_thread.start()
        
    def background_detection_loop(self, config):
        """Loop continuo que realiza detección incluso sin clientes conectados"""
        logger.info("Proceso de detección en segundo plano iniciado")
        model = self.initialize_model()
        
        if not model:
            logger.error("No se pudo inicializar el modelo para detección en segundo plano")
            return
        
        global _latest_detections
        global _latest_frame
        global _latest_frame_lock
        global _opcua_client
        global _counter_pizza_sin_blister
        global _counter_pizza_con_blister
        global _counter_total
        global _counters_lock
        
        previous_red = False
        previous_green = False
        iteration_count = 0
        
        while _background_detection_active:
            try:
                # Capturar frame
                with _camera_lock:
                    ret, frame = _camera_instance.read()
                
                if not ret:
                    logger.error("Error al capturar frame en proceso de fondo")
                    time.sleep(1)
                    continue
                
                # Detectar objetos
                results = model.track(frame, conf=config['CONF_THRESHOLD'])
                annotated_frame = results[0].plot()
                
                # Dibujar área verde
                area_coords = self.draw_green_box(annotated_frame)
                
                # Analizar detecciones
                detections = {'pizza': False, 'blister': False, 'conf_pizza': 0.0, 'conf_blister': 0.0}
                boxes = results[0].boxes
                
                for box in boxes:
                    cls = int(box.cls[0].item()) if box.cls is not None else -1
                    conf = float(box.conf[0].item()) if box.conf is not None else 0.0
                    conf_percent = round(conf * 100, 1)  # Convertir a porcentaje con 1 decimal
                    coords = box.xyxy[0].cpu().numpy()
                    
                    if self.is_inside_area(coords, area_coords):
                        if cls == config['PIZZA_CLASS_ID']:
                            detections['pizza'] = True
                            detections['conf_pizza'] = conf_percent
                        elif cls == config['BLISTER_CLASS_ID']:
                            detections['blister'] = True
                            detections['conf_blister'] = conf_percent
                
                # Actualizar estado para PLC basado en el código que funciona
                if detections['pizza'] and not detections['blister']:
                    # Caso: pizza sin blister - punto rojo
                    self.draw_dot(annotated_frame, config['RED_DOT_POSITION'], 
                                 config['RED_DOT_RADIUS'], config['RED_DOT_COLOR'])
                    
                    # Detectar flanco de subida: de False a True
                    if not previous_red and _opcua_client:
                        logger.info("¡FLANCO DETECTADO! Generando pulso para pizza sin blister")
                        _opcua_client.generate_pulse_pizza_sin_blister()
                        
                        # Actualizar contadores
                        with _counters_lock:
                            _counter_pizza_sin_blister += 1
                            _counter_total += 1
                    
                    previous_red = True
                    previous_green = False
                
                elif detections['pizza'] and detections['blister']:
                    # Caso: pizza con blister - punto verde
                    self.draw_dot(annotated_frame, config['GREEN_DOT_POSITION'], 
                                 config['GREEN_DOT_RADIUS'], config['GREEN_DOT_COLOR'])
                    
                    # Detectar flanco de subida para pizza con blister
                    if not previous_green and _opcua_client:
                        logger.info("¡FLANCO DETECTADO! Generando pulso para pizza con blister")
                        _opcua_client.generate_pulse_pizza_con_blister()
                        
                        # Actualizar contadores
                        with _counters_lock:
                            _counter_pizza_con_blister += 1
                            _counter_total += 1
                            print(_counter_pizza_con_blister)
                    
                    previous_red = False
                    previous_green = True
                
                else:
                    # No hay detecciones relevantes
                    previous_red = False
                    previous_green = False
                
                # Actualizar estado global
                _latest_detections = detections
                
                # Guardar último frame procesado para clientes
                with _latest_frame_lock:
                    _, jpeg = cv2.imencode('.jpg', annotated_frame)
                    _latest_frame = jpeg.tobytes()
                
                # Define opcua_connected FUERA del bloque condicional
                opcua_connected = _opcua_client and _opcua_client.connected if _opcua_client else False
                
                # AÑADIR ESTE CÓDIGO para calcular los porcentajes (sin dibujar en pantalla)
                total = _counter_total if _counter_total > 0 else 1  # Evitar división por cero
                porcentaje_sin_blister = (_counter_pizza_sin_blister / total) * 100
                porcentaje_con_blister = (_counter_pizza_con_blister / total) * 100

                # Actualizar estado compartido
                timestamp = datetime.datetime.now().isoformat()
                
                logger.debug(f"Actualizando shared_state con: pizza={detections['pizza']}, blister={detections['blister']}, " +
                             f"contadores=[{_counter_pizza_sin_blister}/{_counter_pizza_con_blister}/{_counter_total}], " +
                             f"porcentajes=[{porcentaje_sin_blister:.1f}/{porcentaje_con_blister:.1f}]")

                if hasattr(self, 'shared_state') and self.shared_state:
                    self.shared_state.last_detection = {
                        "pizza": detections['pizza'],
                        "blister": detections['blister'],
                        "conf_pizza": detections['conf_pizza'],
                        "conf_blister": detections['conf_blister'],
                        "opcua_connected": opcua_connected,
                        "counter_sin_blister": _counter_pizza_sin_blister,
                        "counter_con_blister": _counter_pizza_con_blister,
                        "counter_total": _counter_total,
                        "porcentaje_sin_blister": porcentaje_sin_blister,
                        "porcentaje_con_blister": porcentaje_con_blister,
                        "timestamp": timestamp
                    }
                
                # Mostrar menos logs para no saturar
                iteration_count += 1
                if iteration_count % 10 == 0:
                    logger.info(f"BG Detection: Pizza={detections['pizza']}({detections['conf_pizza']}%), "
                               f"Blister={detections['blister']}({detections['conf_blister']}%), "
                               f"OPCUA={opcua_connected}, "
                               f"Estadísticas=[{_counter_pizza_sin_blister}/{_counter_pizza_con_blister}]")
                
                # Pausa breve para no saturar el sistema
                time.sleep(0.05)
                
            except Exception as e:
                logger.error(f"Error en proceso de detección de fondo: {e}")
                time.sleep(1)
    
    # El resto de métodos se mantienen igual
    def initialize_model(self) -> Optional[YOLO]:
        """Inicializa el modelo YOLO."""
        try:
            model_path = self.config['BASE_DIR'] / 'models' / 'yolo_weights.pt'
            engine_path = self.config['BASE_DIR'] / 'models' / 'yolo_weights_engine.engine'
            
            # Verificar si existe el archivo del modelo
            if not os.path.exists(model_path):
                logger.error(f"No se encontró el modelo en {model_path}")
                return None
                
            model = YOLO(model_path)
            logger.info(f"Modelo YOLO cargado desde {model_path}")
            # Si existe una versión optimizada, usarla
            if (os.path.exists(engine_path)):
                logger.info(f"Usando modelo optimizado desde {engine_path}")
                return YOLO(engine_path)
            return model
        except Exception as e:
            logger.error(f"Error al cargar el modelo: {e}")
            return None
    
    def draw_green_box(self, frame) -> Tuple[int, int, int, int]:
        """
        Dibuja un recuadro verde en el centro del frame.
        Devuelve las coordenadas del área: (x1, y1, x2, y2)
        """
        h, w = frame.shape[:2]
        x1, y1 = w // 2 - 260, h // 2 - 165
        x2, y2 = w // 2 + 160, h // 2 + 165
        cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)
        return x1, y1, x2, y2
    
    def draw_dot(self, frame, position: Tuple[int, int], radius: int, color: Tuple[int, int, int]):
        """Dibuja un punto de color en la posición especificada."""
        cv2.circle(frame, position, radius, color, -1)
    
    def is_inside_area(self, box: list, area: Tuple[int, int, int, int]) -> bool:
        """
        Verifica si un box (lista [x1, y1, x2, y2]) se encuentra completamente dentro del área.
        """
        bx1, by1, bx2, by2 = box
        ax1, ay1, ax2, ay2 = area
        return bx1 >= ax1 and by1 >= ay1 and bx2 <= ax2 and by2 <= ay2
    
    def get_detection_flags(self, results, area_coords, shared_state=None) -> Dict[str, bool]:
        """
        Recorre las detecciones y establece flags si se encuentra 'pizza' y/o 'blister'
        dentro del área definida.
        """
        flags = {'pizza': False, 'blister': False, 'conf_pizza': 0.0, 'conf_blister': 0.0}
        boxes = results[0].boxes

        for box in boxes:
            cls = int(box.cls[0].item()) if box.cls is not None else -1
            conf = float(box.conf[0].item()) if box.conf is not None else 0.0
            conf_percent = round(conf * 100, 1)  # Convertir a porcentaje con 1 decimal
            coords = box.xyxy[0].cpu().numpy()
            
            if self.is_inside_area(coords, area_coords):
                if cls == self.config['PIZZA_CLASS_ID']:
                    flags['pizza'] = True
                    flags['conf_pizza'] = conf_percent
                elif cls == self.config['BLISTER_CLASS_ID']:
                    flags['blister'] = True
                    flags['conf_blister'] = conf_percent
        
        # Actualizar el estado compartido si se proporcionó
        if shared_state:
            # Agregar estado del PLC
            opcua_connected = _opcua_client and _opcua_client.connected if _opcua_client else False
            shared_state.last_detection = {
                "pizza": flags['pizza'],
                "blister": flags['blister'],
                "conf_pizza": flags['conf_pizza'],
                "conf_blister": flags['conf_blister'],
                "opcua_connected": opcua_connected,
                "timestamp": datetime.datetime.now().isoformat()
            }
        
        return flags
    
    def get_frame(self, detection_enabled: bool, shared_state=None):
        """
        Devuelve el último frame procesado por el thread de fondo
        o procesa uno nuevo si la detección de fondo no está activa
        """
        self.shared_state = shared_state  # Guardar referencia al estado compartido
        
        global _latest_frame
        global _latest_frame_lock
        
        if detection_enabled and _background_detection_active:
            # Usar el frame ya procesado por el thread de fondo
            with _latest_frame_lock:
                if _latest_frame is not None:
                    return _latest_frame
        
        # Si no hay detección en segundo plano o está deshabilitada,
        # capturar y procesar frame normalmente
        with self.frame_lock:
            ret, frame = self.cap.read()
        
        if not ret:
            blank_image = np.zeros((480, 640, 3), np.uint8)
            _, jpeg = cv2.imencode('.jpg', blank_image)
            return jpeg.tobytes()
        
        if not detection_enabled or not self.model:
            _, jpeg = cv2.imencode('.jpg', frame)
            return jpeg.tobytes()
        
        # Procesar frame con detección
        results = self.model.track(frame, conf=self.config['CONF_THRESHOLD'])
        annotated = results[0].plot()
        area_coords = self.draw_green_box(annotated)
        detections = self.get_detection_flags(results, area_coords, shared_state)
        
        if detections['pizza'] and not detections['blister']:
            self.draw_dot(annotated, self.config['RED_DOT_POSITION'], 
                         self.config['RED_DOT_RADIUS'], self.config['RED_DOT_COLOR'])
        elif detections['pizza'] and detections['blister']:
            self.draw_dot(annotated, self.config['GREEN_DOT_POSITION'], 
                         self.config['GREEN_DOT_RADIUS'], self.config['GREEN_DOT_COLOR'])
        
        _, jpeg = cv2.imencode('.jpg', annotated)
        return jpeg.tobytes()

def generate_frames(config, shared_state):
    """
    Genera frames para streaming, compatible con múltiples clientes.
    Cada cliente recibe su propia transmisión, pero comparten la misma cámara física.
    """
    client_id = threading.get_ident()  # Identificador único para este cliente
    logger.info(f"Nuevo cliente conectado (ID: {client_id}), detection_enabled={shared_state.detection_enabled}")
    
    camera = VideoCamera(config)
    
    try:
        while True:
            frame = camera.get_frame(shared_state.detection_enabled, shared_state)
            if frame is None:
                break
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')
    except Exception as e:
        logger.error(f"Error en stream del cliente {client_id}: {e}")
    finally:
        logger.info(f"Cliente desconectado (ID: {client_id})")

# Función para limpiar recursos al finalizar
def cleanup():
    """Limpia recursos globales al finalizar la aplicación"""
    global _camera_instance
    global _opcua_client
    global _opcua_should_reconnect
    global _thread_pool
    
    logger.info("Limpiando recursos antes de finalizar...")
    
    # Detener thread de reconexión
    _opcua_should_reconnect = False
    
    # Apagar el pool de hilos
    try:
        _thread_pool.shutdown(wait=False)
    except:
        pass
    
    # Desconectar OPC-UA
    if _opcua_client:
        try:
            _opcua_client.disconnect()
        except:
            pass
    
    # Liberar cámara
    if _camera_instance:
        try:
            _camera_instance.release()
        except:
            pass

def reset_counters():
    """Reinicia los contadores de detección"""
    global _counter_pizza_sin_blister
    global _counter_pizza_con_blister
    global _counter_total
    global _counters_lock
    
    with _counters_lock:
        _counter_pizza_sin_blister = 0
        _counter_pizza_con_blister = 0
        _counter_total = 0
    
    logger.info("Contadores de detección reiniciados")
    return True