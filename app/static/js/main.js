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

// Añadir/modificar en main.js
function updateStatus() {
    console.log("Solicitando estado...");
    fetch('/status')
        .then(response => {
            if (!response.ok) {
                throw new Error('Error en la respuesta del servidor');
            }
            return response.json();
        })
        .then(data => {
            console.log("Respuesta completa:", data);
            console.log("Estado PLC:", data.plc_connected ? "Conectado" : "Desconectado");
            console.log("Estado recibido:", data);  // Añade esto para depuración
            
            // Actualizar estado de PLC
            const plcStatus = document.getElementById('plc-status');
            if (plcStatus) {
                if (data.plc_connected) {
                    plcStatus.textContent = 'Conectado';
                    plcStatus.className = 'status-value connected';
                    console.log("PLC marcado como conectado");
                } else {
                    plcStatus.textContent = 'Desconectado';
                    plcStatus.className = 'status-value disconnected';
                    console.log("PLC marcado como desconectado");
                }
            } else {
                console.error("No se encontró el elemento plc-status en el DOM");
            }
            
            // [resto del código sin cambios]
        })
        .catch(error => {
            console.error('Error al obtener estado:', error);
        });
}

// Actualizar con mayor frecuencia
setInterval(updateStatus, 2000);  // Cada 2 segundos en lugar de 5

// Ejecutar una vez al cargar
document.addEventListener('DOMContentLoaded', function() {
    updateStatus();
});