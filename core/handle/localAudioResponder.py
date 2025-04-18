import os
import json
import time
import asyncio
import random
from config.logger import setup_logging

TAG = __name__
logger = setup_logging()

class LocalAudioResponder:
    """本地音频响应器，在TTS服务不可用时提供快速响应"""
    
    def __init__(self, config=None):
        self.config = config or {}
        # 音频目录，默认使用wake_responses
        self.audio_dir = os.path.join(os.getcwd(), "wake_responses")
        # 缓存找到的音频文件
        self.available_audio_files = []
        # 扫描音频目录
        self.scan_audio_directory()
        
        logger.bind(tag=TAG).info(f"本地音频响应器已初始化，找到{len(self.available_audio_files)}个音频文件")
        
    def scan_audio_directory(self):
        """扫描音频目录，找到所有支持的音频文件"""
        if not os.path.exists(self.audio_dir):
            logger.bind(tag=TAG).warning(f"音频目录不存在: {self.audio_dir}")
            return
            
        # 支持的音频格式
        supported_extensions = ['.mp3', '.wav', '.ogg', '.flac']
        
        try:
            for file in os.listdir(self.audio_dir):
                file_path = os.path.join(self.audio_dir, file)
                if os.path.isfile(file_path):
                    _, ext = os.path.splitext(file)
                    if ext.lower() in supported_extensions:
                        self.available_audio_files.append(file_path)
                        logger.bind(tag=TAG).debug(f"找到音频文件: {file_path}")
        except Exception as e:
            logger.bind(tag=TAG).error(f"扫描音频目录时出错: {e}")
    
    def get_random_audio(self):
        """获取随机音频文件"""
        if not self.available_audio_files:
            return None
        return random.choice(self.available_audio_files)
    
    async def respond(self, conn, text):
        """使用本地音频文件响应"""
        try:
            # 获取随机音频文件
            audio_file = self.get_random_audio()
            if not audio_file:
                logger.bind(tag=TAG).error("没有可用的本地音频文件")
                return False
                
            # 发送STT状态消息，让设备显示识别到的文本
            await conn.websocket.send(json.dumps({
                "type": "stt",
                "text": text,
                "session_id": conn.session_id
            }))
            
            logger.bind(tag=TAG).info(f"使用本地音频响应: {audio_file}")
            
            # 发送TTS开始消息
            await conn.websocket.send(json.dumps({
                "type": "tts", 
                "state": "start", 
                "session_id": conn.session_id
            }))
            
            # 使用TTS组件将音频文件转换为opus数据包
            if not hasattr(conn.tts, "wav_to_opus_data"):
                logger.bind(tag=TAG).error("TTS组件没有wav_to_opus_data方法")
                return False
                
            try:
                opus_datas, _ = conn.tts.wav_to_opus_data(audio_file)
            except Exception as e:
                logger.bind(tag=TAG).error(f"转换音频文件失败: {e}")
                return False
            
            # 发送句子开始消息
            await conn.websocket.send(json.dumps({
                "type": "tts", 
                "state": "sentence_start", 
                "text": f"回复: {text[:10]}...",
                "session_id": conn.session_id
            }))
            
            # 发送音频数据
            frame_duration = 60  # 毫秒
            start_time = time.perf_counter()  # 使用高精度计时器
            play_position = 0  # 已播放的时长（毫秒）

            for opus_packet in opus_datas:
                if conn.client_abort:
                    break

                # 计算当前包的预期发送时间
                expected_time = start_time + (play_position / 1000)
                current_time = time.perf_counter()

                # 等待直到预期时间
                delay = expected_time - current_time
                if delay > 0:
                    await asyncio.sleep(delay)

                # 发送音频包
                await conn.websocket.send(opus_packet)
                play_position += frame_duration  # 更新播放位置
                
            # 发送句子结束消息
            await conn.websocket.send(json.dumps({
                "type": "tts", 
                "state": "sentence_end", 
                "text": f"回复: {text[:10]}...",
                "session_id": conn.session_id
            }))
            
            # 发送停止消息
            await conn.websocket.send(json.dumps({
                "type": "tts", 
                "state": "stop", 
                "session_id": conn.session_id
            }))
            
            # 重置ASR状态
            conn.asr_server_receive = True
            
            return True
            
        except Exception as e:
            logger.bind(tag=TAG).error(f"使用本地音频响应时出错: {e}")
            return False 