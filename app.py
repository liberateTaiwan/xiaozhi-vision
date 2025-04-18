import asyncio
from config.logger import setup_logging
from config.settings import load_config, check_config_file
from core.websocket_server import WebSocketServer
from manager.http_server import WebUI
from aiohttp import web
from core.utils.util import get_local_ip, check_ffmpeg_installed
from core.providers.voice.voice_recognition import register_voice, recognize_voice, extract_name_from_intro, VOICE_RECOGNITION_AVAILABLE
import os
import tempfile
from loguru import logger
import base64
import time
import json
from core.vision.vision_model import VisionModel

TAG = __name__

# 添加的功能函数
def extract_name_from_text(text, llm):
    """从用户介绍中提取名字"""
    # 使用大模型提取名字
    prompt = f"从以下文本中提取人名：'{text}'。只返回人名，不要其他文字。"
    response = llm.generate(prompt)
    # 清理并返回结果
    name = response.strip()
    return name

async def handle_voice_command(text, audio_data, llm, tts_engine, session_state):
    """处理声纹相关的特殊命令"""
    # 检查声纹识别是否可用
    if not VOICE_RECOGNITION_AVAILABLE and ("我是" in text or "我叫" in text or "我是谁" in text):
        response = "声纹识别功能未能加载，请检查系统设置。"
        audio_response = await tts_engine.synthesize(response)
        return {
            "type": "voice_command",
            "command": "voice_recognition_unavailable",
            "text": response,
            "audio": audio_response
        }
    
    text = text.lower().strip()
    
    # 保存临时音频文件
    if audio_data is None:
        return None  # 没有音频数据，不处理声纹命令
    
    # 用户自我介绍，注册声纹
    if ("我是" in text or "我叫" in text) and len(text) < 20:  # 限制长度，避免处理长句子
        # 提取名字
        name = extract_name_from_intro(text)
        if not name:
            # 如果无法提取名字，请求用户重试
            response = "抱歉，我没听清您的名字，请再说一次？"
            audio_response = await tts_engine.synthesize(response)
            return {
                "type": "voice_command",
                "command": "name_extraction_failed",
                "text": response,
                "audio": audio_response
            }
        
        # 注册声纹
        register_result = register_voice(name, audio_data)
        logger.bind(tag=TAG).info(f"注册声纹结果: {register_result} for name: {name}")
        
        # 返回注册结果
        response = f"您好，{name}。{register_result}"
        audio_response = await tts_engine.synthesize(response)
        
        return {
            "type": "voice_command",
            "command": "register_complete",
            "text": response,
            "audio": audio_response
        }
    
    # 用户询问身份，识别声纹
    elif "我是谁" in text:
        # 识别声纹
        result = recognize_voice(audio_data)
        audio_response = await tts_engine.synthesize(result)
        
        return {
            "type": "voice_command",
            "command": "identify",
            "text": result,
            "audio": audio_response
        }
    
    # 不是特殊命令，返回None
    return None
    
    # 检查是否在等待用户名字
    if session_state.get("mode") == "waiting_for_name" and text and temp_audio_path:
        # 提取名字
        name = extract_name_from_text(text, llm)
        
        # 注册声纹
        register_result = register_voice(name, temp_audio_path)
        logger.bind(tag=TAG).info(f"注册声纹结果: {register_result} for name: {name}")
        
        # 重置状态
        session_state["mode"] = "normal"
        session_state.pop("temp_audio_path", None)
        
        # 返回注册结果
        response = f"{register_result}"
        audio_response = await tts_engine.synthesize(response)
        
        return {
            "type": "voice_command",
            "command": "register_complete",
            "text": response,
            "audio": audio_response
        }
    
    # 不是特殊命令，返回None
    return None

# 添加视觉API路由处理函数
async def handle_vision_api(request):
    """
    处理视觉API请求
    POST请求需要包含:
    {
        "image": "base64编码的图片",
        "query": "问题内容"
    }
    """
    try:
        # 加载配置
        config = load_config()
        
        # 检查视觉功能是否启用
        if not config.get("vision", {}).get("enabled", False):
            return web.json_response({
                "success": False,
                "message": "视觉功能未启用"
            }, status=400)
            
        # 解析请求数据
        data = await request.json()
        
        if "image" not in data or "query" not in data:
            return web.json_response({
                "success": False,
                "message": "请求格式错误，需要image和query字段"
            }, status=400)
            
        # 准备图像数据
        image_data = data["image"]
        if "base64," in image_data:
            image_data = image_data.split("base64,")[1]
        
        # 获取视觉配置
        vision_config = config.get("vision", {})
        save_dir = vision_config.get("image", {}).get("save_dir", "captured_images")
        os.makedirs(save_dir, exist_ok=True)
        
        # 保存图像
        timestamp = int(time.time())
        image_path = f"{save_dir}/vision_api_{timestamp}.jpg"
        with open(image_path, "wb") as f:
            f.write(base64.b64decode(image_data))
        
        # 初始化视觉模型
        vision_model = VisionModel(config)
        
        # 分析图像
        query = data["query"]
        analysis_result = vision_model.analyze_image(image_path, query)
        
        # 返回结果
        return web.json_response({
            "success": True,
            "query": query,
            "result": analysis_result
        })
        
    except Exception as e:
        logger.bind(tag=TAG).error(f"视觉API请求处理错误: {str(e)}")
        return web.json_response({
            "success": False,
            "message": f"处理请求时出错: {str(e)}"
        }, status=500)

async def main():
    check_config_file()
    check_ffmpeg_installed()
    logger = setup_logging()
    config = load_config()
    
    # 检查声纹识别是否可用
    if not VOICE_RECOGNITION_AVAILABLE:
        logger.bind(tag=TAG).warning("声纹识别功能未能加载，某些功能将不可用")

    # 创建视觉API
    app = web.Application()
    app.add_routes([
        web.post('/api/vision', handle_vision_api)
    ])
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', 8112)
    await site.start()
    logger.bind(tag=TAG).info("视觉API服务已启动，监听端口: 8112")

    # 启动 WebSocket 服务器
    ws_server = WebSocketServer(config)
    # 将声纹识别处理函数传递给WebSocketServer
    ws_server.register_voice_command_handler(handle_voice_command)
    ws_task = asyncio.create_task(ws_server.start())

    # 启动 WebUI 服务器
    webui_runner = None
    if config['manager'].get('enabled', False):
        server_config = config["manager"]
        host = server_config["ip"]
        port = server_config["port"]
        try:
            webui = WebUI()
            runner = web.AppRunner(webui.app)
            await runner.setup()
            site = web.TCPSite(runner, host, port)
            await site.start()
            webui_runner = runner
            local_ip = get_local_ip()
            logger.bind(tag=TAG).info(f"WebUI server is running at http://{local_ip}:{port}")
        except Exception as e:
            logger.bind(tag=TAG).error(f"Failed to start WebUI server: {e}")

    try:
        # 等待 WebSocket 服务器运行
        await ws_task
    finally:
        # 清理 WebUI 服务器
        if webui_runner:
            await webui_runner.cleanup()


if __name__ == "__main__":
    asyncio.run(main())