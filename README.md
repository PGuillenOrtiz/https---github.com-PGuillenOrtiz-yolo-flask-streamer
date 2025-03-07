# yolo-flask-streamer

This project integrates a YOLO (You Only Look Once) object detection model with a Flask web application to stream video detections in real-time. The application captures video frames, processes them for object detection, and displays the results on a web page accessible via the computer's IP address.

## Project Structure

- **app/**: Contains the main application code.
  - **\_\_init\_\_.py**: Initializes the Flask application.
  - **routes.py**: Defines the routes for the web application.
  - **camera.py**: Handles video capture from the camera.
  - **detector.py**: Contains the YOLO detection logic.
  - **plc_client.py**: Manages communication with the PLC (Programmable Logic Controller).
  - **utils.py**: Utility functions for various tasks.
  - **static/**: Contains static files such as CSS and JavaScript.
    - **css/**: Stylesheets for the web application.
    - **js/**: JavaScript files for client-side functionality.
  - **templates/**: Contains HTML templates for rendering web pages.
    - **index.html**: The main landing page of the application.
    - **video.html**: The page that displays the video stream with detections.

- **config.py**: Configuration settings for the Flask application.
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

3. Configure the application by editing the `instance/config.py` file as needed.

## Running the Application

To start the Flask application, run:
```
python run.py
```

The application will be accessible at `http://<your-ip-address>:5000`. Open this URL in a web browser to view the video stream with object detections.

## Usage

- Navigate to the main page to start the video stream.
- The application will display detected objects in real-time, highlighting them on the video feed.

## License

This project is licensed under the MIT License. See the LICENSE file for details.