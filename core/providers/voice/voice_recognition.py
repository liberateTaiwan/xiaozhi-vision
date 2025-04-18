import os
from loguru import logger
import tempfile
from core.providers.voice.offline_infrence import load_model_manually, register_voice as offline_register, recognize_voice as offline_recognize

TAG = __name__

# 声纹模型初始化
try:
    MODEL_DICT = load_model_manually()
    if MODEL_DICT is None:
        logger.bind(tag=TAG).error("声纹识别模型加载失败")
        VOICE_RECOGNITION_AVAILABLE = False
    else:
        logger.bind(tag=TAG).info("声纹识别模型加载成功")
        VOICE_RECOGNITION_AVAILABLE = True
except Exception as e:
    logger.bind(tag=TAG).error(f"初始化声纹识别时出错: {e}")
    VOICE_RECOGNITION_AVAILABLE = False

def extract_name_from_intro(text):
    """从自我介绍中提取名字
    
    例如: "我是博哥" -> "博哥"
         "我叫张三" -> "张三"
    """
    text = text.strip()
    
    # 提取名字的逻辑
    prefixes = ["我是", "我叫", "我的名字是", "我名字叫"]
    for prefix in prefixes:
        if text.startswith(prefix):
            name = text[len(prefix):]
            return name.strip()
    
    # 如果没有找到前缀，返回整个文本（去掉标点符号）
    import re
    name = re.sub(r'[,.，。！？!?]', '', text)
    return name.strip()

def register_voice(name, audio_data):
    """注册声纹"""
    if not VOICE_RECOGNITION_AVAILABLE:
        return "声纹识别模块未能加载，无法注册声纹"
    
    try:
        # 保存临时音频文件
        temp_audio_path = tempfile.mktemp(suffix=".wav")
        with open(temp_audio_path, "wb") as f:
            f.write(audio_data)
        
        # 调用离线注册函数
        result = offline_register(MODEL_DICT, name, temp_audio_path)
        
        # 清理临时文件
        try:
            os.remove(temp_audio_path)
        except:
            pass
            
        return result
    except Exception as e:
        logger.bind(tag=TAG).error(f"注册声纹失败: {e}")
        return f"注册声纹失败: {str(e)}"

def recognize_voice(audio_data):
    """识别声纹"""
    if not VOICE_RECOGNITION_AVAILABLE:
        return "声纹识别模块未能加载，无法识别声纹"
    
    try:
        # 保存临时音频文件
        temp_audio_path = tempfile.mktemp(suffix=".wav")
        with open(temp_audio_path, "wb") as f:
            f.write(audio_data)
        
        # 调用离线识别函数
        result = offline_recognize(MODEL_DICT, temp_audio_path)
        
        # 清理临时文件
        try:
            os.remove(temp_audio_path)
        except:
            pass
            
        return result
    except Exception as e:
        logger.bind(tag=TAG).error(f"识别声纹失败: {e}")
        return f"识别声纹失败: {str(e)}"