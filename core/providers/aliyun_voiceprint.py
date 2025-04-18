import logging
import time
import json
from aliyunsdkcore.client import AcsClient
from aliyunsdkcore.acs_exception.exceptions import ClientException, ServerException
from aliyunsdkcore.request import CommonRequest

class AliyunVoiceprintProvider:
    def __init__(self):
        # 从配置文件或环境变量加载
        self.access_key_id = "204832784"
        self.access_key_secret = "26i8tV38XmlxpIdsxsXiYf6OBIBffoNy"
        self.region_id = "cn-shanghai"
        
        self.client = AcsClient(
            self.access_key_id, 
            self.access_key_secret, 
            self.region_id
        )
    
    def register_voiceprint(self, user_id, audio_data):
        """注册声纹"""
        logging.info(f"调用阿里云API注册声纹: 用户ID {user_id}")
        
        try:
            request = CommonRequest()
            request.set_domain("nls-meta.cn-shanghai.aliyuncs.com")
            request.set_version("2019-02-28")
            request.set_action_name("CreateVoiceprintEnrollment")
            
            # 设置请求参数
            request.add_query_param("InstanceId", "YOUR_INSTANCE_ID")
            request.add_query_param("UserId", user_id)
            request.add_query_param("AudioFormat", "wav")
            
            # 音频数据需要进行Base64编码
            import base64
            encoded_audio = base64.b64encode(audio_data).decode('utf-8')
            request.add_body_params("AudioData", encoded_audio)
            
            # 发送请求，设置超时时间
            response = self.client.do_action_with_exception(request, timeout=30)
            result = json.loads(response.decode('utf-8'))
            
            if result.get("Success"):
                logging.info(f"声纹注册成功: {result}")
                return result
            else:
                error_msg = f"声纹注册API返回失败: {result}"
                logging.error(error_msg)
                raise Exception(error_msg)
                
        except (ClientException, ServerException) as e:
            error_msg = f"阿里云API调用异常: {e}"
            logging.error(error_msg)
            raise Exception(error_msg)
        except Exception as e:
            error_msg = f"声纹注册发生未知错误: {e}"
            logging.error(error_msg)
            raise Exception(error_msg)
    
    def verify_voiceprint(self, user_id, audio_data):
        """验证声纹"""
        logging.info(f"调用阿里云API验证声纹: 用户ID {user_id}")
        
        try:
            request = CommonRequest()
            request.set_domain("nls-meta.cn-shanghai.aliyuncs.com")
            request.set_version("2019-02-28")
            request.set_action_name("VerifyVoiceprint")
            
            # 设置请求参数
            request.add_query_param("InstanceId", "YOUR_INSTANCE_ID")
            request.add_query_param("UserId", user_id)
            request.add_query_param("AudioFormat", "wav")
            
            # 音频数据需要进行Base64编码
            import base64
            encoded_audio = base64.b64encode(audio_data).decode('utf-8')
            request.add_body_params("AudioData", encoded_audio)
            
            # 发送请求
            response = self.client.do_action_with_exception(request, timeout=30)
            result = json.loads(response.decode('utf-8'))
            
            logging.info(f"声纹验证结果: {result}")
            return result
                
        except Exception as e:
            logging.error(f"声纹验证错误: {e}")
            raise e 