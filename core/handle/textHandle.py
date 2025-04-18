from config.logger import setup_logging
import json
import os
import time
import base64
from core.handle.abortHandle import handleAbortMessage
from core.handle.helloHandle import handleHelloMessage
from core.handle.receiveAudioHandle import startToChat
from core.handle.iotHandle import handleIotDescriptors

TAG = __name__
logger = setup_logging()


async def handleTextMessage(conn, message):
    """处理文本消息"""
    logger.bind(tag=TAG).info(f"收到文本消息：{message}")
    try:
        msg_json = json.loads(message)
        if isinstance(msg_json, int):
            await conn.websocket.send(message)
            return
        if msg_json["type"] == "hello":
            await handleHelloMessage(conn)
        elif msg_json["type"] == "abort":
            await handleAbortMessage(conn)
        elif msg_json["type"] == "listen":
            if "mode" in msg_json:
                conn.client_listen_mode = msg_json["mode"]
                logger.bind(tag=TAG).debug(f"客户端拾音模式：{conn.client_listen_mode}")
            if msg_json["state"] == "start":
                conn.client_have_voice = True
                conn.client_voice_stop = False
            elif msg_json["state"] == "stop":
                conn.client_have_voice = True
                conn.client_voice_stop = True
            elif msg_json["state"] == "detect":
                conn.asr_server_receive = False
                conn.client_have_voice = False
                conn.asr_audio.clear()
                if "text" in msg_json:
                    await startToChat(conn, msg_json["text"])
        elif msg_json["type"] == "iot":
            if "descriptors" in msg_json:
                await handleIotDescriptors(conn, msg_json["descriptors"])
        elif msg_json["type"] == "vision":
            # 处理带有图像的消息
            if "image" in msg_json and "text" in msg_json:
                # 保存图像
                vision_config = conn.config.get("vision", {})
                save_dir = vision_config.get("image", {}).get("save_dir", "captured_images")
                # 确保目录存在
                os.makedirs(save_dir, exist_ok=True)
                
                # 将base64图像保存到文件
                image_data = msg_json["image"]
                # 去除可能的base64前缀
                if "base64," in image_data:
                    image_data = image_data.split("base64,")[1]
                
                timestamp = int(time.time())
                image_path = f"{save_dir}/image_{timestamp}.jpg"
                
                try:
                    # 解码并保存图像
                    with open(image_path, "wb") as f:
                        f.write(base64.b64decode(image_data))
                    
                    logger.bind(tag=TAG).info(f"已保存图像: {image_path}")
                    
                    # 调用处理带图像的对话
                    await startToChatWithImage(conn, msg_json["text"], image_path)
                except Exception as e:
                    logger.bind(tag=TAG).error(f"处理图像错误: {e}")
                    await conn.websocket.send(message)
            else:
                logger.bind(tag=TAG).error("缺少必要的图像或文本字段")
                await conn.websocket.send(message)
    except json.JSONDecodeError:
        await conn.websocket.send(message)


async def startToChatWithImage(conn, text, image_path):
    """启动带图像的聊天"""
    await send_stt_message(conn, text)
    conn.executor.submit(conn.chat, text, image_path)


# 从receiveAudioHandle.py导入send_stt_message函数
from core.handle.sendAudioHandle import send_stt_message
