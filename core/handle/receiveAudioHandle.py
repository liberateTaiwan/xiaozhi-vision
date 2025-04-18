from config.logger import setup_logging
import time
import re
import os
import cv2
import random
from core.utils.util import remove_punctuation_and_length, get_string_no_punctuation_or_emoji
from core.handle.sendAudioHandle import send_stt_message
import os
import time
import json
import logging
from core.handle.voiceprint_handler import VoiceprintHandler

TAG = __name__
logger = setup_logging()

# 初始化声纹处理器
voiceprint_handler = VoiceprintHandler()

# 多模态关键词
VISION_KEYWORDS = [
    "看看这个", "看看这张图", "看看图片", "分析图片", "识别图片", 
    "这是什么", "图像分析", "图片分析", "用眼睛看看", "使用相机",
    "打开相机", "用眼睛看", "用你的眼睛", "拍照", "帮我看一下",
    "图像识别", "给我描述", "帮我描述", "照相", "拍张照片",
    "用摄像头", "摄像头", "相机", "照片", "图片内容", "图中"
]

async def handleAudioMessage(conn, audio):
    if not conn.asr_server_receive:
        logger.bind(tag=TAG).debug(f"前期数据处理中，暂停接收")
        return
    if conn.client_listen_mode == "auto":
        have_voice = conn.vad.is_vad(conn, audio)
    else:
        have_voice = conn.client_have_voice

    # 如果本次没有声音，本段也没声音，就把声音丢弃了
    if have_voice == False and conn.client_have_voice == False:
        await no_voice_close_connect(conn)
        conn.asr_audio.clear()
        return
    conn.client_no_voice_last_time = 0.0
    conn.asr_audio.append(audio)
    # 如果本段有声音，且已经停止了
    if conn.client_voice_stop:
        conn.client_abort = False
        conn.asr_server_receive = False
        # 音频太短了，无法识别
        if len(conn.asr_audio) < 3:
            conn.asr_server_receive = True
        else:
            # 先提取文本，争取快速处理
            start_time = time.time()  # 计时开始
            text, file_path = await conn.asr.speech_to_text(conn.asr_audio, conn.session_id)

            # 保存音频用于声纹处理
            if hasattr(conn, 'voiceprint') and conn.voiceprint:
                conn.last_audio_data = conn.asr_audio.copy()

            # 处理用户名回答（如果在声纹注册流程中）
            if hasattr(conn, 'is_registering_voiceprint') and conn.is_registering_voiceprint:
                # 提取用户名
                user_name = text.replace("我叫", "").replace("我是", "").replace("叫我", "").strip()
                
                if len(user_name) > 0:
                    logger.bind(tag=TAG).info(f"注册声纹用户名: {user_name}")
                    
                    # 调用API注册声纹
                    success = conn.voiceprint.register_user(user_name, conn.registration_audio)
                    
                    if success:
                        response = f"我已经记住你了，{user_name}。下次见到你我会认出你的。"
                    else:
                        response = "抱歉，声纹注册失败，请稍后再试。"
                    
                    # 发送响应并清除状态
                    conn.first_sentence = response
                    await send_stt_message(conn, response)
                    conn.is_registering_voiceprint = False
                    conn.registration_audio = None  # 清除保存的音频
                    conn.asr_server_receive = True
                    conn.asr_audio.clear()
                    conn.reset_vad_states()
                    return  # 结束处理，不继续执行
                
            # 优先检查是否为唤醒词
            is_wake_word, audio_file = await conn.wake_word_handler.is_wake_word(text)
            if is_wake_word:
                logger.bind(tag=TAG).info(f"【唤醒】检测到唤醒词: {text}")
                handled = await conn.wake_word_handler.handle_wake_word(conn, text, audio_file)
                if handled:
                    conn.asr_audio.clear()
                    conn.reset_vad_states()
                    return
            
            # 检查是否是多模态请求关键词
            if any(keyword in text for keyword in VISION_KEYWORDS):
                logger.bind(tag=TAG).info(f"检测到多模态请求关键词: {text}")
                
                # 尝试捕获图像
                await handle_vision_request(conn, text)
                conn.asr_server_receive = True
                conn.asr_audio.clear()
                conn.reset_vad_states()
                return
            
            # 不是唤醒词或处理失败，继续正常流程
            text_len, text_without_punctuation = remove_punctuation_and_length(text)
            if await conn.music_handler.handle_music_command(conn, text_without_punctuation):
                conn.asr_server_receive = True
                conn.asr_audio.clear()
                return
            if text_len <= conn.max_cmd_length and await handleCMDMessage(conn, text_without_punctuation):
                return
            if text_len > 0:
                await startToChat(conn, text)
            else:
                conn.asr_server_receive = True
        conn.asr_audio.clear()
        conn.reset_vad_states()


async def handleCMDMessage(conn, text):
    cmd_exit = conn.cmd_exit
    for cmd in cmd_exit:
        if text == cmd:
            logger.bind(tag=TAG).info("识别到明确的退出命令".format(text))
            await conn.close()
            return True
    return False


async def startToChat(conn, text):
    # 此函数实际上已经不再需要唤醒词检测，因为我们在handleAudioMessage中已经处理了
    # 但为了确保向下兼容，保留原有逻辑
    is_wake_word, audio_file = await conn.wake_word_handler.is_wake_word(text)
    if is_wake_word:
        handled = await conn.wake_word_handler.handle_wake_word(conn, text, audio_file)
        if handled:
            return
    
    # 不是唤醒词或处理失败，走正常流程
    await send_stt_message(conn, text)
    conn.executor.submit(conn.chat, text)


async def no_voice_close_connect(conn):
    if conn.client_no_voice_last_time == 0.0:
        conn.client_no_voice_last_time = time.time() * 1000
    else:
        no_voice_time = time.time() * 1000 - conn.client_no_voice_last_time
        close_connection_no_voice_time = conn.config.get("close_connection_no_voice_time", 120)
        if no_voice_time > 1000 * close_connection_no_voice_time:
            conn.client_abort = False
            conn.asr_server_receive = False
            prompt = '时间过得真快，我都好久没说话了。请你用十个字左右话跟我告别，以"再见"或"拜拜"为结尾'
            # 使用startToChat处理
            await startToChat(conn, prompt)


async def handle_vision_request(conn, text):
    """处理多模态请求，捕获图像并发送给大模型"""
    try:
        # 获取配置中的图像保存目录
        vision_config = conn.config.get("vision", {})
        save_dir = vision_config.get("image", {}).get("save_dir", "captured_images")
        os.makedirs(save_dir, exist_ok=True)
        
        # 尝试使用OpenCV捕获图像
        cap = None
        image_captured = False
        try:
            # 尝试不同的视频源
            video_sources = [
                "https://2724710us1nn.vicp.fun/stream",  # ESP32摄像头流
                # "rtsp://admin:admin@192.168.1.100:554/live",  # 通用RTSP流
                # "http://localhost:8080/video"  # 移动设备摄像头
            ]
            
            for source in video_sources:
                logger.bind(tag=TAG).info(f"尝试打开视频源: {source}")
                cap = cv2.VideoCapture(source)
                if cap.isOpened():
                    logger.bind(tag=TAG).info(f"成功打开视频源: {source}")
                    
                    # 尝试读取3次，以便获取更稳定的图像
                    for _ in range(3):
                        ret, frame = cap.read()
                        if ret:
                            break
                        time.sleep(0.5)
                    
                    if ret:
                        # 保存图像
                        timestamp = int(time.time())
                        image_path = f"{save_dir}/image_{timestamp}.jpg"
                        cv2.imwrite(image_path, frame)
                        logger.bind(tag=TAG).info(f"已保存图像: {image_path}")
                        
                        # 向用户反馈
                        await send_stt_message(conn, "我已经拍摄了一张照片，正在分析...")
                        
                        # 调用多模态模型分析图像
                        await startToChatWithImage(conn, text, image_path)
                        image_captured = True
                        print("我拿到视频流图片了！")
                        break
                    else:
                        logger.bind(tag=TAG).warning(f"无法从视频源 {source} 读取图像")
                        cap.release()
                        cap = None
            
            # 如果无法捕获图像，尝试使用最近的图片
            if not image_captured:
                # 如果无法打开摄像头，使用现有的图片
                existing_images = [os.path.join(save_dir, f) for f in os.listdir(save_dir) 
                                  if f.endswith(('.jpg', '.jpeg', '.png'))]
                
                # 按照文件修改时间排序
                if existing_images:
                    existing_images.sort(key=lambda x: os.path.getmtime(x), reverse=True)
                    # 使用最新的图像
                    image_path = existing_images[0]
                    await send_stt_message(conn, f"我无法使用摄像头，但我可以分析这张最近的图片。")
                    # 发送图片分析请求
                    await startToChatWithImage(conn, text, image_path)
                    return
                else:
                    await send_stt_message(conn, "抱歉，我无法访问摄像头，也没有找到任何现有图片。")
                    return
        finally:
            if cap and cap.isOpened():
                cap.release()
                
    except Exception as e:
        logger.bind(tag=TAG).error(f"处理多模态请求出错: {e}")
        await send_stt_message(conn, f"处理图像时出现错误: {str(e)}")


async def startToChatWithImage(conn, text, image_path):
    """启动带图像的聊天"""
    # 检查图片是否存在
    if not os.path.exists(image_path):
        logger.bind(tag=TAG).error(f"图片文件不存在: {image_path}")
        await send_stt_message(conn, "抱歉，无法找到要分析的图片。")
        return
        
    logger.bind(tag=TAG).info(f"开始多模态聊天，图片路径: {image_path}, 查询: {text}")
    await send_stt_message(conn, text)
    conn.executor.submit(conn.chat, text, image_path)


def process_audio_command(text, audio_data):
    """处理音频命令"""
    text = text.strip()
    
    # 处理声纹注册命令
    if "记住我" in text:
        logging.info(f"触发声纹注册命令: {text}")
        # 添加以下代码来避免卡住
        try:
            # 记录详细日志
            logging.info("声纹注册功能尚未完全实现，返回提示信息")
            
            # 向用户返回一个友好提示
            from core.utils.audio_utils import text_to_speech
            response_text = "抱歉，声纹识别功能正在开发中，暂时无法使用。"
            audio_path = text_to_speech(response_text)
            
            # 如果有发送音频给用户的函数，调用它
            # send_audio_to_user(audio_path)
            
            # 或者如果有直接发送文本的函数
            # send_text_to_user(response_text)
            
            # 这一行非常重要，确保函数正常返回，不会卡住
            return
        except Exception as e:
            # 记录错误并继续正常流程
            logging.error(f"处理声纹注册命令异常: {e}")
            return
        
    # 处理声纹验证命令
    if "验证我" in text:
        logging.info(f"触发声纹验证命令: {text}")
        # 实现声纹验证逻辑
        return True
        
    # 如果正在声纹注册过程中
    if voiceprint_handler.is_registering:
        response = voiceprint_handler.add_registration_audio(audio_data)
        if response:
            send_text_to_user(response)
        return True
        
    return False  # 不是声纹相关命令

# 在主处理函数中集成
def handle_audio(audio_data, text):
    """主音频处理函数"""
    try:
        # 处理特殊命令
        if process_audio_command(text, audio_data):
            return
            
        # 继续处理常规对话
        # ... existing code ...
    except Exception as e:
        logging.error(f"音频处理异常: {e}")
        # 发送错误提示给用户
        send_text_to_user("抱歉，处理您的请求时出现了问题")
