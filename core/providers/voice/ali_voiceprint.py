import os
import json
import time
import uuid
import base64
import hmac
import hashlib
import requests
import io
import wave
import logging
from config.logger import setup_logging

TAG = __name__
logger = setup_logging()

class AliVoiceprintRecognition:
    def __init__(self, config):
        # 更新API密钥配置
        self.app_key = config.get("app_key", "20483278")
        self.app_secret = config.get("app_secret", "26i8tV38XmlxldsxsXlYf6OBlBffoNy")
        self.app_code = config.get("app_code", "43916e46e5ef44fc8ece6ffefddccf36")  # 添加AppCode
    
        self.api_url = "f4691afba0ed40608f34771408caf23f-cn-hangzhou.alicloudapi.com"
        self.vpstore_id = None
        self.data_dir = config.get("data_dir", "voiceprint_data")
        self.user_map = {}  # 用户名到声纹ID的映射
        os.makedirs(self.data_dir, exist_ok=True)
        self.load_user_map()
        self.init_vpstore()
        logger.bind(tag=TAG).info("阿里云声纹识别模块初始化成功")

    def load_user_map(self):
        """加载用户映射"""
        map_file = os.path.join(self.data_dir, "user_map.json")
        if os.path.exists(map_file):
            with open(map_file, "r", encoding="utf-8") as f:
                self.user_map = json.load(f)
            logger.bind(tag=TAG).info(f"加载了{len(self.user_map)}个用户声纹映射")

    def save_user_map(self):
        """保存用户映射"""
        map_file = os.path.join(self.data_dir, "user_map.json")
        with open(map_file, "w", encoding="utf-8") as f:
            json.dump(self.user_map, f, ensure_ascii=False, indent=2)
        logger.bind(tag=TAG).info(f"保存了{len(self.user_map)}个用户声纹映射")

    def _convert_audio_to_wav(self, audio_data):
        """将音频数据转换为WAV格式"""
        # 处理音频格式
        if isinstance(audio_data, list):
            # 合并多个音频块
            combined = b''.join(audio_data)
        else:
            combined = audio_data
            
        # 确保是二进制
        if not isinstance(combined, bytes):
            logger.bind(tag=TAG).error(f"音频数据类型错误: {type(combined)}")
            return None
            
        # 转换为16kHz, 16位, 单声道WAV - 阿里云API要求
        out = io.BytesIO()
        with wave.open(out, 'wb') as wf:
            wf.setnchannels(1)  # 单声道
            wf.setsampwidth(2)  # 16位
            wf.setframerate(16000)  # 16kHz
            wf.writeframes(combined)
        return out.getvalue()

    def get_token(self):
        """获取API访问令牌"""
        # 尝试使用API权限获取接口获取令牌
        try:
            headers = {
                'Authorization': f'APPCODE {self.app_key}',
                'Content-Type': 'application/json'
            }
            
            response = requests.post(f"https://{self.api_url}/v1/user/login", headers=headers)
            
            if response.status_code == 200:
                result = response.json()
                if "token" in result:
                    return result["token"]
                    
            logger.bind(tag=TAG).error(f"获取Token失败: {response.text}")
            # 如果失败，回退到使用AppKey和AppSecret
            return self.app_key
        except Exception as e:
            logger.bind(tag=TAG).error(f"Token获取异常: {str(e)}")
            return self.app_key

    def init_vpstore(self):
        """初始化声纹库"""
        # 获取声纹库列表
        token = self.get_token()
        
        try:
            headers = {
                'Token': token,
                'Content-Type': 'application/json'
            }
            
            # 获取声纹库列表
            response = requests.get(f"https://{self.api_url}/v1/vpr/vpstores", headers=headers)
            
            if response.status_code == 200:
                result = response.json()
                vpstores = result.get("vpstores", [])
                
                # 检查是否已有声纹库
                if vpstores:
                    # 使用第一个声纹库
                    self.vpstore_id = vpstores[0].get("vpstore_id")
                    logger.bind(tag=TAG).info(f"使用已有声纹库: {self.vpstore_id}")
                    return
            
            # 如果没有声纹库，创建一个
            self.create_vpstore("xiaozhi_users")
        except Exception as e:
            logger.bind(tag=TAG).error(f"初始化声纹库异常: {str(e)}")

    def create_vpstore(self, name):
        """创建声纹库"""
        token = self.get_token()
        
        try:
            headers = {
                'Token': token,
                'Content-Type': 'application/json'
            }
            
            data = {
                "vpstore_name": name
            }
            
            # 创建声纹库
            response = requests.post(f"https://{self.api_url}/v1/vpr/create_vpstore", 
                                    headers=headers, 
                                    json=data)
            
            if response.status_code == 200:
                result = response.json()
                self.vpstore_id = result.get("vpstore_id")
                logger.bind(tag=TAG).info(f"成功创建声纹库: {self.vpstore_id}")
                return True
            else:
                logger.bind(tag=TAG).error(f"创建声纹库失败: {response.text}")
                return False
        except Exception as e:
            logger.bind(tag=TAG).error(f"创建声纹库异常: {str(e)}")
            return False

    def register_user(self, username, audio_data):
        """注册用户声纹"""
        logger.bind(tag=TAG).info(f"开始注册用户声纹: {username}")
        
        if not self.vpstore_id:
            logger.bind(tag=TAG).error("声纹库ID未初始化，无法注册")
            return False
        
        # 获取访问令牌
        token = self.get_token()
        
        # 转换音频格式
        wav_data = self._convert_audio_to_wav(audio_data)
        if not wav_data:
            logger.bind(tag=TAG).error("音频转换失败")
            return False
        
        # 首先上传音频文件
        file_id = self.upload_audio_file(token, wav_data)
        if not file_id:
            logger.bind(tag=TAG).error("音频文件上传失败")
            return False
        
        # 注册声纹
        try:
            headers = {
                'Token': token,
                'Content-Type': 'application/json'
            }
            
            data = {
                "vpstore_id": self.vpstore_id,
                "file_id": file_id
            }
            
            # 注册声纹
            response = requests.post(f"https://{self.api_url}/v1/vpr/register", 
                                    headers=headers, 
                                    json=data)
            
            if response.status_code == 200:
                # 保存用户名到文件ID的映射
                self.user_map[username] = file_id
                self.save_user_map()
                logger.bind(tag=TAG).info(f"用户声纹注册成功: {username} -> {file_id}")
                return True
            else:
                logger.bind(tag=TAG).error(f"用户声纹注册失败: {response.text}")
                return False
        except Exception as e:
            logger.bind(tag=TAG).error(f"注册用户声纹异常: {str(e)}")
            return False

    def upload_audio_file(self, token, wav_data):
        """上传音频文件"""
        try:
            headers = {
                'Token': token,
                'Content-Type': 'application/octet-stream',
                'File-Length': str(len(wav_data))
            }
            
            # 上传音频文件
            response = requests.post(f"https://{self.api_url}/v1/file/upload", 
                                    headers=headers, 
                                    data=wav_data)
            
            if response.status_code == 200:
                result = response.json()
                file_id = result.get("file_id")
                logger.bind(tag=TAG).info(f"音频文件上传成功: {file_id}")
                return file_id
            else:
                logger.bind(tag=TAG).error(f"音频文件上传失败: {response.text}")
                return None
        except Exception as e:
            logger.bind(tag=TAG).error(f"上传音频文件异常: {str(e)}")
            return None

    # def recognize_user(self, audio_data):
        """识别用户声纹"""
        logger.bind(tag=TAG).info("开始识别用户声纹")
        
        if not self.vpstore_id:
            logger.bind(tag=TAG).error("声纹库ID未初始化，无法识别")
            return None
        
        # 获取访问令牌
        token = self.get_token()
        
        # 转换音频格式
        wav_data = self._convert_audio_to_wav(audio_data)
        if not wav_data:
            logger.bind(tag=TAG).error("音频转换失败")
            return None
        
        # 首先上传音频文件
        file_id = self.upload_audio_file(token, wav_data)
        if not file_id:
            logger.bind(tag=TAG).error("音频文件上传失败")
            return None
        
        # 获取声纹列表
        voiceprint_ids = self.get_voiceprints()
        if not voiceprint_ids:
            logger.bind(tag=TAG).error("获取声纹列表失败")
            return None
        
        # 进行声纹比对
        try:
            headers = {
                'Token': token,
                'Content-Type': 'application/json'
            }
            
            data = {
                "file_id": file_id,
                "target_vpr_ids": voiceprint_ids
            }
            
            # 声纹比对
            response = requests.post(f"https://{self.api_url}/v1/vpr/cmp_voiceprints", 
                                    headers=headers, 
                                    json=data)
            
            if response.status_code == 200:
                result = response.json()
                if "result" in result and result["result"]:
                    # 获取最高相似度的结果
                    top_match = result["result"][0]
                    matched_file_id = top_match.get("file_id")
                    similarity = top_match.get("score", 0)
                    
                    # 查找对应的用户名
                    user_name = None
                    for name, fid in self.user_map.items():
                        if fid == matched_file_id:
                            user_name = name
                            break
                    
                    logger.bind(tag=TAG).info(f"声纹识别结果: {matched_file_id}, 相似度: {similarity}, 用户名: {user_name}")
                    
                    # 只有当相似度大于一定阈值时才认为识别成功
                    if similarity >= 70:  # 假设70分以上为有效匹配
                        return {
                            "user_name": user_name,
                            "similarity": similarity,
                            "file_id": matched_file_id
                        }
                
                logger.bind(tag=TAG).info("声纹识别未找到匹配")
                return None
            else:
                logger.bind(tag=TAG).error(f"声纹比对失败: {response.text}")
                return None
        except Exception as e:
            logger.bind(tag=TAG).error(f"识别用户声纹异常: {str(e)}")
            return None

    def get_voiceprints(self):
        """获取声纹列表"""
        if not self.vpstore_id:
            return []
        
        # 获取访问令牌
        token = self.get_token()
        
        try:
            headers = {
                'Token': token,
                'Content-Type': 'application/json'
            }
            
            # 获取声纹列表
            params = {
                'vpstore_id': self.vpstore_id,
                'limit': '100'  # 最多获取100个声纹
            }
            
            response = requests.get(f"https://{self.api_url}/v1/vpr/voiceprints", 
                                   headers=headers, 
                                   params=params)
            
            if response.status_code == 200:
                result = response.json()
                voiceprints = result.get("voiceprints", [])
                
                # 提取文件ID列表
                file_ids = [vp.get("file_id") for vp in voiceprints if vp.get("file_id")]
                return file_ids
            else:
                logger.bind(tag=TAG).error(f"获取声纹列表失败: {response.text}")
                return []
        except Exception as e:
            logger.bind(tag=TAG).error(f"获取声纹列表异常: {str(e)}")
            return []