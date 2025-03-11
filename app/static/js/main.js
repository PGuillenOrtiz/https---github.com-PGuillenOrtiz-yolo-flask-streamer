console.log("Versión: 1.0.1"); // Para verificar que se cargó la nueva versión

const videoElement = document.getElementById('videoStream');

function startVideoStream() {
    const socket = new WebSocket('ws://localhost:5000/video_feed');

    socket.onmessage = function(event) {
        const image = new Image();
        image.src = URL.createObjectURL(event.data);
        image.onload = function() {
            videoElement.src = image.src;
        };
    };

    socket.onclose = function() {
        console.log('WebSocket connection closed');
    };
}

window.onload = function() {
    startVideoStream();
    updateStatus();
};

// Variables globales para el estado del PLC
let plcLastKnownStatus = false;
let plcStatusConfirmationCount = 0;
const PLC_STATUS_CONFIRMATION_THRESHOLD = 3; // Requiere 3 lecturas consecutivas para cambiar el estado

function updateStatus() {
    fetch('/status')
        .then(response => response.json())
        .then(data => {
            console.log("Datos recibidos:", data);
            
            // Actualizar estado PLC con histéresis para evitar parpadeo
            const plcStatus = document.getElementById('plc-status');
            if (plcStatus) {
                const currentStatus = data.opcua_connected;
                
                // Lógica de histéresis - solo cambia el estado después de varias confirmaciones
                if (currentStatus === plcLastKnownStatus) {
                    // Estado estable, mantener contador en 0
                    plcStatusConfirmationCount = 0;
                } else {
                    // Estado diferente del último conocido, incrementar contador
                    plcStatusConfirmationCount++;
                    
                    // Solo cambiar el estado visual después de superar el umbral
                    if (plcStatusConfirmationCount >= PLC_STATUS_CONFIRMATION_THRESHOLD) {
                        // Actualizar el estado visual
                        plcLastKnownStatus = currentStatus;
                        plcStatusConfirmationCount = 0;
                        
                        // Aplicar el cambio visual
                        if (currentStatus) {
                            plcStatus.innerHTML = '<span class="status-indicator connected"></span>Conectado';
                            plcStatus.className = 'status-value connected';
                        } else {
                            plcStatus.innerHTML = '<span class="status-indicator disconnected"></span>Desconectado';
                            plcStatus.className = 'status-value disconnected';
                        }
                    }
                    // Si no supera el umbral, mantener el estado visual anterior
                }
            }
            
            // Resto del código de actualización...
            // Actualizar contadores usando los datos de last_detection
            if (data.last_detection) {
                updateCounters(data.last_detection);
            }
        })
        .catch(err => {
            console.error('Error al actualizar estado:', err);
        });
}

// Actualizar con mayor frecuencia
setInterval(updateStatus, 2000);  // Cada 2 segundos en lugar de 5

// Ejecutar una vez al cargar
document.addEventListener('DOMContentLoaded', function() {
    updateStatus();
});