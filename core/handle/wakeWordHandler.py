import os
import time
import json
import random
import asyncio
import subprocess
import tempfile
from config.logger import setup_logging
from core.utils.util import get_string_no_punctuation_or_emoji

TAG = __name__
logger = setup_logging()


class WakeWordHandler:
    def __init__(self, config):
        """初始化唤醒词处理器"""
        self.config = config
        self.wake_word_config = config.get("wake_word_response", {})
        self.enabled = self.wake_word_config.get("enabled", False)
        self.responses = self.wake_word_config.get("responses", [])
        self.audio_dir = self.wake_word_config.get("audio_dir", "wake_responses")
        self.random_response = self.wake_word_config.get("random_response", False)
        
        # 创建唤醒词和音频文件的映射
        self.wake_word_map = {}
        for response in self.responses:
            wake_word = response.get("wake_word", "").lower()
            audio_file = response.get("audio_file", "")
            if wake_word and audio_file:
                self.wake_word_map[wake_word] = audio_file
        
        # 扫描音频目录，找到所有音频文件
        self.available_audio_files = []
        
        # 音频数据缓存，预处理常用文件
        self.audio_cache = {}
        
        # 初始化扫描和预处理
        self.scan_audio_directory()
        self.preprocess_common_audio()
        
        # 检查配置是否有效
        if self.enabled:
            logger.bind(tag=TAG).info(f"唤醒词直接响应功能已启用，配置了{len(self.wake_word_map)}个唤醒词")
            logger.bind(tag=TAG).info(f"音频目录中找到{len(self.available_audio_files)}个音频文件")
            logger.bind(tag=TAG).info(f"预处理了{len(self.audio_cache)}个音频文件")
            
            if self.random_response:
                logger.bind(tag=TAG).info("已启用随机音频响应")
        else:
            logger.bind(tag=TAG).info("唤醒词直接响应功能未启用")
    
    def scan_audio_directory(self):
        """扫描音频目录，找到所有支持的音频文件"""
        audio_dir_path = os.path.join(os.getcwd(), self.audio_dir)
        if not os.path.exists(audio_dir_path):
            logger.bind(tag=TAG).warning(f"音频目录不存在: {audio_dir_path}")
            return
            
        # 支持的音频格式
        supported_extensions = ['.mp3', '.wav', '.ogg', '.flac']
        
        try:
            for file in os.listdir(audio_dir_path):
                file_path = os.path.join(audio_dir_path, file)
                if os.path.isfile(file_path):
                    _, ext = os.path.splitext(file)
                    if ext.lower() in supported_extensions:
                        # 不在扫描阶段验证，而是添加所有文件
                        self.available_audio_files.append(file_path)
                        logger.bind(tag=TAG).debug(f"找到音频文件: {file_path}")
        except Exception as e:
            logger.bind(tag=TAG).error(f"扫描音频目录时出错: {e}")
    
    def preprocess_common_audio(self):
        """预处理常用的音频文件，转换为WAV并缓存"""
        # 优先处理配置中指定的文件
        for wake_word, audio_file in self.wake_word_map.items():
            full_path = os.path.join(os.getcwd(), self.audio_dir, audio_file)
            if os.path.exists(full_path) and full_path not in self.audio_cache:
                try:
                    # 直接添加到缓存，延迟处理
                    self.audio_cache[full_path] = None
                    logger.bind(tag=TAG).debug(f"已将'{wake_word}'的音频文件添加到缓存队列: {full_path}")
                except Exception as e:
                    logger.bind(tag=TAG).error(f"预处理音频文件失败: {e}")

    def get_audio_data(self, audio_file, tts_component):
        """获取音频数据，优先使用缓存"""
        # 检查缓存
        if audio_file in self.audio_cache and self.audio_cache[audio_file] is not None:
            logger.bind(tag=TAG).debug(f"使用缓存的音频数据: {audio_file}")
            return self.audio_cache[audio_file]
        
        # 检查文件是否存在
        if not os.path.exists(audio_file):
            logger.bind(tag=TAG).error(f"音频文件不存在: {audio_file}")
            return None
        
        try:
            # 检查文件格式，如果不是WAV格式，先转换为WAV
            _, ext = os.path.splitext(audio_file)
            wav_file = audio_file
            converted_file = None
            
            start_time = time.time()  # 计时开始
            
            if ext.lower() != '.wav':
                logger.bind(tag=TAG).debug(f"转换音频格式: {audio_file}")
                converted_file = self.fast_convert_to_wav(audio_file)
                if converted_file:
                    wav_file = converted_file
                else:
                    logger.bind(tag=TAG).error(f"转换音频文件失败: {audio_file}")
                    return None
            
            # 使用TTS组件将音频文件转换为opus数据包
            opus_datas, duration = tts_component.wav_to_opus_data(wav_file)
            
            end_time = time.time()  # 计时结束
            logger.bind(tag=TAG).info(f"音频处理耗时: {end_time - start_time:.3f}秒")
            
            # 如果生成了临时文件，删除它
            if converted_file and os.path.exists(converted_file):
                try:
                    os.remove(converted_file)
                except Exception as e:
                    logger.bind(tag=TAG).error(f"删除临时文件失败: {e}")
            
            # 缓存处理结果
            self.audio_cache[audio_file] = (opus_datas, duration)
            
            return opus_datas, duration
        except Exception as e:
            logger.bind(tag=TAG).error(f"处理音频文件时出错: {e}")
            return None
    
    def fast_convert_to_wav(self, audio_file):
        """更快的音频转换方法，专注于速度而非完美品质"""
        _, ext = os.path.splitext(audio_file)
        if ext.lower() == '.wav':
            return audio_file
            
        # 为临时文件创建唯一的文件名
        temp_file = tempfile.mktemp(suffix='.wav')
        
        try:
            # 使用更高效的ffmpeg命令
            cmd = [
                'ffmpeg', 
                '-v', 'error',   # 只显示错误
                '-y',            # 覆盖输出文件
                '-i', audio_file, 
                '-ar', '24000',  # 采样率设置为与ESP32默认相同
                '-ac', '1',      # 单声道
                '-f', 'wav',
                '-acodec', 'pcm_s16le',  # 使用简单编码
                temp_file
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=2)
            if result.returncode != 0:
                logger.bind(tag=TAG).error(f"转换音频文件失败: {result.stderr}")
                return None
                
            return temp_file
        except subprocess.TimeoutExpired:
            logger.bind(tag=TAG).error("转换音频文件超时")
            return None
        except Exception as e:
            logger.bind(tag=TAG).error(f"转换音频文件时出错: {e}")
            return None

    async def is_wake_word(self, text):
        """检查文本是否为唤醒词"""
        if not self.enabled:
            return False, None
            
        # 移除标点和空格进行比较
        clean_text = get_string_no_punctuation_or_emoji(text).lower()
        
        # 检查是否在配置的唤醒词列表中
        for wake_word, audio_file in self.wake_word_map.items():
            clean_wake_word = get_string_no_punctuation_or_emoji(wake_word).lower()
            if clean_text == clean_wake_word or clean_text.find(clean_wake_word) != -1:
                # 如果启用了随机响应，则从可用音频文件中随机选择一个
                if self.random_response and self.available_audio_files:
                    random_audio = random.choice(self.available_audio_files)
                    logger.bind(tag=TAG).info(f"匹配到唤醒词: '{clean_text}'，随机选择音频: {random_audio}")
                    return True, random_audio
                
                # 否则使用配置中指定的音频文件
                full_path = os.path.join(os.getcwd(), self.audio_dir, audio_file)
                if os.path.exists(full_path):
                    logger.bind(tag=TAG).info(f"匹配到唤醒词: '{clean_text}'，使用配置音频: {full_path}")
                    return True, full_path
                # 如果配置的音频文件不存在，但有可用的随机音频，则使用随机音频
                elif self.available_audio_files:
                    random_audio = random.choice(self.available_audio_files)
                    logger.bind(tag=TAG).info(f"配置的音频文件不存在，随机选择: {random_audio}")
                    return True, random_audio
                else:
                    logger.bind(tag=TAG).error(f"唤醒词音频文件不存在，且没有可用的随机音频")
                    return True, None
                    
        return False, None

    async def handle_wake_word(self, conn, text, audio_file):
        """处理唤醒词，直接播放预设音频"""
        try:
            start_time = time.time()  # 开始计时

            # 在唤醒后尝试识别用户
            if hasattr(conn, 'voiceprint') and conn.voiceprint and hasattr(conn, 'last_audio_data'):
                logger.bind(tag=TAG).info("开始唤醒词声纹识别...")
                
                result = conn.voiceprint.recognize_user(conn.last_audio_data)
                
                if result and result.get("user_name"):
                    user_name = result.get("user_name")
                    similarity = result.get("similarity", 0)
                    
                    logger.bind(tag=TAG).info(f"声纹识别结果: {user_name}, 相似度: {similarity}")
                    
                    # 记录个性化问候
                    conn.personalized_greeting = f"嗨，{user_name}，很高兴再次见到你！有什么我可以帮你的吗？"
            
            # 发送STT状态消息，让设备显示识别到的文本
            await conn.websocket.send(json.dumps({
                "type": "stt",
                "text": text,
                "session_id": conn.session_id
            }))
            
            # 如果没有音频文件，尝试随机选择一个
            if not audio_file and self.available_audio_files:
                audio_file = random.choice(self.available_audio_files)
                logger.bind(tag=TAG).info(f"没有指定音频文件，随机选择: {audio_file}")
            elif not audio_file:
                logger.bind(tag=TAG).error(f"唤醒词'{text}'没有可用的音频文件")
                return False
                
            # 直接发送音频
            logger.bind(tag=TAG).info(f"唤醒词识别成功: '{text}'，使用音频: {audio_file}")
            
            # 获取音频数据（可能会从缓存获取）
            audio_data = self.get_audio_data(audio_file, conn.tts)
            if not audio_data:
                logger.bind(tag=TAG).error(f"无法获取音频数据: {audio_file}")
                return False
                
            opus_datas, _ = audio_data
                
            # 发送TTS开始消息
            await conn.websocket.send(json.dumps({
                "type": "tts", 
                "state": "start", 
                "session_id": conn.session_id
            }))
            
            # 发送句子开始消息
            await conn.websocket.send(json.dumps({
                "type": "tts", 
                "state": "sentence_start", 
                "text": "你好",
                "session_id": conn.session_id
            }))
            
            process_time = time.time() - start_time
            logger.bind(tag=TAG).info(f"音频处理耗时: {process_time:.3f}秒")
            
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
                "text": "你好",
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
            logger.bind(tag=TAG).error(f"处理唤醒词时出错: {e}")
            return False 