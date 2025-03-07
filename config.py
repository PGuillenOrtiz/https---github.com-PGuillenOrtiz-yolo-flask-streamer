from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent

class Config:
    SECRET_KEY = 'your_secret_key_here'
    DEBUG = True
    VIDEO_SOURCE = 0  # Change this to the appropriate video source (e.g., camera index or video file path)
    CONF_THRESHOLD = 0.5  # Confidence threshold for YOLO detections
    PLC_IP = '192.168.9.20'  # Replace with your PLC IP
    PLC_RACK = 0
    PLC_SLOT = 1
    PLC_DB = 15
    PLC_BYTE = 0
    PLC_BIT = 0
    WINDOW_NAME = 'YOLO Video Stream'
    RED_DOT_POSITION = (50,50)
    RED_DOT_RADIUS = 15
    RED_DOT_COLOR = (0, 0, 255)  # Red in BGR
    GREEN_DOT_POSITION = (50, 50)
    GREEN_DOT_RADIUS = 15
    GREEN_DOT_COLOR = (0, 255, 0)  # Green in BGR
    PIZZA_CLASS_ID = 1
    BLISTER_CLASS_ID = 0
    BASE_DIR = BASE_DIR  # Add BASE_DIR to the configuration

class ProductionConfig(Config):
    DEBUG = False

class DevelopmentConfig(Config):
    DEBUG = True