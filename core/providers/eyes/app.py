from flask import Flask, request, jsonify
import requests
import base64
import time
import os
import json
from loguru import logger

TAG = __name__

app = Flask(__name__, static_folder='static')

# API 配置
VLLM_API_URL = 'http://127.0.0.1:8000/v1/chat/completions'
TTS_API_URL = 'http://127.0.0.1:9880'
VLLM_MODEL = "/home/king/project/qwenVL/Qwen/Qwen2.5-VL/model/Qwen2.5-VL-3B-Instruct"
AUDIO_FOLDER = "./static/audio"

# 确保音频存放目录存在
os.makedirs(AUDIO_FOLDER, exist_ok=True)

@app.route('/')
def index():
    return app.send_static_file('index2.html')

@app.route('/vision_process', methods=['POST'])
def vision_process():
    """
    处理ESP32发送的图像和音频
    
    请求体格式：
    {
        "image": "base64编码的图像",
        "audio": "base64编码的音频", 
        "text": "音频转文字结果（可选）"
    }
    """
    try:
        data = request.get_json()
        
        # 获取图像和音频数据
        base64_image = data.get('image')
        base64_audio = data.get('audio')
        
        # 文本可以由ESP32本地ASR提供，也可以为空
        prompt = data.get('text', '')
        
        # 如果没有提供文本，则使用默认提示词
        if not prompt or prompt.strip() == '':
            prompt = "请描述这个画面中你看到了什么"
        
        logger.bind(tag=TAG).info(f"收到ESP32请求，提示词：{prompt}")
        
        # 构建发送给VLLM的请求数据
        vllm_request_data = {
            "model": VLLM_MODEL,
            "messages": [{"role": "user", "content": [
                {"type": "text", "text": prompt},
                {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"}}
            ]}],
            "max_tokens": 1024,
            "temperature": 0.5
        }

        # 发送请求到VLLM服务
        response = requests.post(VLLM_API_URL, json=vllm_request_data, headers={'Authorization': 'Bearer test'})
        response.raise_for_status()
        vllm_result = response.json()
        message = vllm_result['choices'][0]['message']['content']
        
        logger.bind(tag=TAG).info(f"VLLM返回结果：{message}")

        # 生成TTS音频
        audio_url = generate_audio(message)
        
        # 返回处理结果
        return jsonify({
            "message": message,
            "audio_url": audio_url
        })

    except Exception as e:
        logger.bind(tag=TAG).error(f"处理ESP32请求失败: {str(e)}")
        return jsonify({"error": str(e)}), 500

def generate_audio(text):
    """生成TTS音频并返回URL"""
    try:
        # 调用TTS API生成音频
        tts_response = requests.get(f"{TTS_API_URL}?text={text}&text_language=zh")
        if tts_response.status_code == 200:
            # 生成唯一的音频文件名
            audio_filename = f"vision_response_{int(time.time())}.wav"
            audio_path = os.path.join(AUDIO_FOLDER, audio_filename)

            # 保存音频文件
            with open(audio_path, "wb") as f:
                f.write(tts_response.content)

            audio_url = f"/static/audio/{audio_filename}"
            return audio_url
        else:
            logger.bind(tag=TAG).error(f"TTS服务返回错误: {tts_response.status_code}")
            return None
    except Exception as e:
        logger.bind(tag=TAG).error(f"生成音频失败: {str(e)}")
        return None

@app.route('/esp32_endpoint', methods=['POST'])
def esp32_endpoint():
    """
    接收ESP32发送的图像和音频数据，并返回处理结果和音频URL
    
    该接口支持两种使用场景：
    1. ESP32直接发送图像+音频，需要完整处理
    2. ESP32只请求音频文件，返回音频数据而非URL
    """
    # 获取请求类型
    request_type = request.args.get('type', 'process')
    
    if request_type == 'process':
        # 完整处理请求
        result = vision_process()
        return result
    
    elif request_type == 'get_audio':
        # 仅获取音频文件
        audio_url = request.args.get('audio_url')
        if not audio_url:
            return jsonify({"error": "Missing audio_url parameter"}), 400
        
        try:
            # 从audio_url中提取文件名
            audio_filename = os.path.basename(audio_url)
            audio_path = os.path.join(AUDIO_FOLDER, audio_filename)
            
            # 检查文件是否存在
            if not os.path.exists(audio_path):
                return jsonify({"error": "Audio file not found"}), 404
                
            # 读取音频文件并返回
            with open(audio_path, "rb") as f:
                audio_data = f.read()
            
            # 返回音频数据
            return audio_data, 200, {
                'Content-Type': 'audio/wav',
                'Content-Disposition': f'attachment; filename={audio_filename}'
            }
        except Exception as e:
            return jsonify({"error": f"Error retrieving audio: {str(e)}"}), 500

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)