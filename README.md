# yolo-flask-streamer

This project integrates a YOLO (You Only Look Once) object detection model with a Flask web application to stream video detections in real-time. The application captures video frames, processes them for object detection, and displays the results on a web page accessible via the computer's IP address. It also communicates with PLCs using OPC-UA protocol for industrial automation integration.

## Project Structure

- **app/**: Contains the main application code.
  - **\_\_init\_\_.py**: Initializes the Flask application.
  - **routes.py**: Defines the routes for the web application.
  - **camera.py**: Handles video capture from the camera and includes OPC-UA client implementation.
  - **detector.py**: Contains the YOLO detection logic.
  - **utils.py**: Utility functions for various tasks.
  - **static/**: Contains static files such as CSS and JavaScript.
    - **css/**: Stylesheets for the web application.
    - **js/**: JavaScript files for client-side functionality.
  - **templates/**: Contains HTML templates for rendering web pages.
    - **index.html**: The main landing page of the application.
    - **video.html**: The page that displays the video stream with detections.

- **config.py**: Configuration settings for the Flask application, including OPC-UA connection parameters.
- **instance/**: Contains instance-specific configurations.
  - **config.py**: Configuration settings that can be overridden for different environments.
- **models/**: Directory for storing the YOLO model weights.
  - **yolo_weights.pt**: Pre-trained weights for the YOLO model.
- **run.py**: The entry point to run the Flask application.
- **requirements.txt**: Lists the Python packages required to run the application.

## Installation

1. Clone the repository:
   ```
   git clone <repository-url>
   cd yolo-flask-streamer
   ```

2. Install the required packages:
   ```
   pip install -r requirements.txt
   ```

3. Configure the application by editing the `config.py` file as needed.

## Docker Support

The application can be containerized using Docker. We use the official Ultralytics container image as a base and extend it with our application-specific requirements:

1. Build the Docker image:
```
docker build -t yolo-flask-streamer .
```

2. Run the container with proper device access for camera and GPU:
```
docker run --rm -it --gpus all --device /dev/video0:/dev/video0 yolo-flask-streamer
```

3. Access the application at `http://localhost:5000` or `http://<host-ip>:5000`.

For production environments, you may need to configure additional Docker volumes to persist configurations and model weights.

## Configuration

### OPC-UA Configuration

The application uses OPC-UA protocol for PLC communication. Configure the following settings in `config.py`:

```python
# OPC-UA Configuration
OPCUA_URL = "opc.tcp://192.168.9.20:4840"  # OPC-UA server URL
OPCUA_NODE_SIN_BLISTER = "ns=4;i=3"        # NodeId for pizza without blister
OPCUA_NODE_CON_BLISTER = "ns=4;i=4"        # NodeId for pizza with blister
```

### YOLO Configuration

Configure the following settings in `config.py` for YOLO detections:

```python
CONF_THRESHOLD = 0.5     # Confidence threshold for YOLO detections
PIZZA_CLASS_ID = 1       # Class ID for pizza in YOLO model
BLISTER_CLASS_ID = 0     # Class ID for blister in YOLO model
```

## Running the Application

To start the Flask application, run:
```
python run.py
```

The application will be accessible at http://<your-ip-address>:5000. Open this URL in a web browser to view the video stream with object detections.

How It Works
The application captures video frames from the configured video source.
Each frame is processed by the YOLO model to detect pizzas and blisters.
Based on detections:
If a pizza without blister is detected, a signal is sent via OPC-UA to the PLC.
If a pizza with blister is detected, a different signal is sent via OPC-UA.
The processed frames with detection overlays are streamed to the web interface.
Requirements
Python 3.6+
OpenCV
Flask
Ultralytics YOLO
python-opcua
NumPy
License
This project is licensed under the MIT License. See the LICENSE file for details.