def generate_frames(camera):
    while True:
        success, frame = camera.read()
        if not success:
            break
        else:
            # Perform YOLO detection on the frame
            results = model.track(frame, conf=CONFIG['conf_threshold'])
            annotated_frame = results[0].plot()
            # Encode the frame in JPEG format
            ret, buffer = cv2.imencode('.jpg', annotated_frame)
            frame = buffer.tobytes()
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')