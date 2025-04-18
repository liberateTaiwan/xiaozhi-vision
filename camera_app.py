# /opt/xiaozhi/xiaozhi-esp32-wb/camera_app.py
from flask import Flask, request, jsonify, render_template, Response
import os
import time
import cv2
import numpy as np
from core.vision.vision_model import VisionModel
from config.settings import load_config

app = Flask(__name__)
config = load_config()

# 初始化视觉模型
vision_model = VisionModel(config) if config.get("vision", {}).get("enabled", False) else None

# 使用配置中的保存目录
UPLOAD_FOLDER = config.get("vision", {}).get("image", {}).get("save_dir", "captured_images")
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

# 保存最新的图像
latest_image = None

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/upload', methods=['POST'])
def upload_image():
    global latest_image
    
    try:
        image_data = request.data
        nparr = np.frombuffer(image_data, np.uint8)
        image = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        
        if image is not None:
            latest_image = image
            
            # 保存图像
            timestamp = int(time.time())
            filename = f"{UPLOAD_FOLDER}/image_{timestamp}.jpg"
            cv2.imwrite(filename, image)
            
            # 获取用户问题
            user_question = request.args.get('question', '描述一下这个图片')
            
            # 如果视觉模型可用，进行图像分析
            analysis_result = None
            if vision_model:
                analysis_result = vision_model.analyze_image(filename, user_question)
            
            return jsonify({
                "status": "success",
                "message": "图像接收成功",
                "analysis": analysis_result
            })
        else:
            return jsonify({"status": "error", "message": "图像解码失败"}), 400
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/latest_image')
def get_latest_image():
    def generate():
        global latest_image
        while True:
            if latest_image is not None:
                _, jpeg = cv2.imencode('.jpg', latest_image)
                yield (b'--frame\r\n'
                       b'Content-Type: image/jpeg\r\n\r\n' + jpeg.tobytes() + b'\r\n')
            time.sleep(0.1)
    
    return Response(generate(), mimetype='multipart/x-mixed-replace; boundary=frame')