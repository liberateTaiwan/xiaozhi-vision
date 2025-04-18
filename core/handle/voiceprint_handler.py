import logging
import threading
from core.providers.aliyun_voiceprint import AliyunVoiceprintProvider

class VoiceprintHandler:
    def __init__(self):
        self.voiceprint_provider = AliyunVoiceprintProvider()
        self.is_registering = False
        self.current_user_id = None
        self.registration_audio = []
        
    def start_registration(self, user_id):
        """开始声纹注册流程"""
        logging.info(f"开始声纹注册流程，用户ID: {user_id}")
        self.is_registering = True
        self.current_user_id = user_id
        self.registration_audio = []
        
        # 返回提示信息，告知用户开始采集声音
        return "请您清晰地说一段话，我将记住您的声音特征。"
        
    def add_registration_audio(self, audio_data):
        """添加声纹注册的音频数据"""
        if not self.is_registering:
            return None
            
        self.registration_audio.append(audio_data)
        logging.info(f"采集声纹样本 {len(self.registration_audio)}/3")
        
        if len(self.registration_audio) >= 3:
            # 在单独线程中处理注册，避免阻塞主线程
            threading.Thread(target=self._process_registration).start()
            return "声音采集完成，正在处理..."
        else:
            return f"已采集{len(self.registration_audio)}段声音，请继续说话..."
    
    def _process_registration(self):
        """处理声纹注册"""
        try:
            logging.info("开始处理声纹注册...")
            # 合并音频数据
            combined_audio = self._combine_audio(self.registration_audio)
            
            # 调用阿里云API进行声纹注册
            result = self.voiceprint_provider.register_voiceprint(
                self.current_user_id, 
                combined_audio
            )
            
            logging.info(f"声纹注册完成: {result}")
            # 通知用户注册成功
            # 此处需要实现向用户发送成功消息的逻辑
        except Exception as e:
            logging.error(f"声纹注册失败: {e}")
            # 通知用户注册失败
            # 此处需要实现向用户发送失败消息的逻辑
        finally:
            self.is_registering = False
            self.current_user_id = None
            self.registration_audio = []
    
    def _combine_audio(self, audio_chunks):
        """合并多段音频数据"""
        # 实现音频合并逻辑
        # 这里是简化示例，实际实现需要根据音频格式调整
        return b''.join(audio_chunks) 