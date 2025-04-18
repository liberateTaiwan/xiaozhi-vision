from config.logger import setup_logging
import openai
import base64
import os
import imghdr
from core.providers.llm.base import LLMProviderBase
from volcenginesdkarkruntime import Ark

TAG = __name__
logger = setup_logging()


class LLMProvider(LLMProviderBase):
    def __init__(self, config):
        self.model_name = config.get("model_name")
        self.api_key = config.get("api_key")
        if 'base_url' in config:
            self.base_url = config.get("base_url")
        else:
            self.base_url = config.get("url")
        if "你" in self.api_key:
            logger.bind(tag=TAG).error("你还没配置LLM的密钥，请在配置文件中配置密钥，否则无法正常工作")
            
        # 常规OpenAI客户端 - 用于纯文本请求
        self.client = openai.OpenAI(api_key=self.api_key, base_url=self.base_url)
        
        # 火山引擎Ark客户端 - 用于多模态请求
        self.ark_client = Ark(
            base_url=self.base_url,
            api_key=self.api_key
        )
        
        # 图片相关配置
        vision_config = config.get("vision", {})
        self.image_folder = vision_config.get("image_folder", "captured_images")
        # 确保图片文件夹存在
        if not os.path.exists(self.image_folder):
            os.makedirs(self.image_folder, exist_ok=True)
        self.is_multimodal = config.get("is_multimodal", False)

    def encode_image(self, image_path):
        """将图片转换为base64编码，并检测正确的格式"""
        with open(image_path, "rb") as image_file:
            image_data = image_file.read()
            # 检测图片格式
            image_format = imghdr.what(None, image_data)
            if not image_format:
                image_format = image_path.split('.')[-1].lower()
            
            # 确保格式正确
            if image_format == 'jpg':
                image_format = 'jpeg'
            
            base64_image = base64.b64encode(image_data).decode('utf-8')
            return base64_image, image_format

    def response(self, session_id, dialogue, image_path=None):
        try:
            # 获取最后一条用户消息
            user_messages = [msg for msg in dialogue if msg["role"] == "user"]
            if not user_messages:
                logger.bind(tag=TAG).error("对话历史中没有用户消息")
                yield "对话历史中没有用户消息，无法生成回复"
                return
            
            last_user_msg = user_messages[-1]
            user_query = last_user_msg["content"]
            
            # 如果提供了图片路径且模型支持多模态
            if image_path and self.is_multimodal and os.path.exists(image_path):
                logger.bind(tag=TAG).info(f"处理多模态请求，图片路径: {image_path}")
                
                try:
                    # 使用Ark SDK直接调用多模态模型
                    base64_image, image_format = self.encode_image(image_path)
                    data_url = f"data:image/{image_format};base64,{base64_image}"
                    
                    logger.bind(tag=TAG).info(f"图片格式: {image_format}, 发送多模态请求...")
                    
                    # 构建对话历史
                    ark_messages = []
                    for msg in dialogue:
                        if msg["role"] == "system":
                            ark_messages.append({
                                "role": "system",
                                "content": msg["content"]
                            })
                    
                    # 添加最后一条包含图片的用户消息
                    ark_messages.append({
                        "role": "user",
                        "content": [
                            {"type": "text", "text": user_query},
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": data_url
                                }
                            }
                        ]
                    })
                    
                    logger.bind(tag=TAG).debug(f"多模态请求消息: {ark_messages}")
                    
                    # 使用Ark客户端发送请求
                    response = self.ark_client.chat.completions.create(
                        model=self.model_name,
                        messages=ark_messages
                    )
                    
                    # 获取完整响应并一次性返回
                    full_response = response.choices[0].message.content
                    logger.bind(tag=TAG).info(f"多模态模型返回内容: {full_response[:100]}...")
                    
                    # 每个字符逐个输出以支持流式响应
                    for char in full_response:
                        yield char
                        
                except Exception as e:
                    error_msg = f"多模态请求错误: {str(e)}"
                    logger.bind(tag=TAG).error(error_msg)
                    yield error_msg
                    return
            else:
                # 常规文本请求使用OpenAI客户端
                responses = self.client.chat.completions.create(
                    model=self.model_name,
                    messages=dialogue,
                    stream=True
                )
                
                is_active = True
                for chunk in responses:
                    try:
                        # 检查是否存在有效的choice且content不为空
                        delta = chunk.choices[0].delta if getattr(chunk, 'choices', None) else None
                        content = delta.content if hasattr(delta, 'content') else ''
                    except IndexError:
                        content = ''
                    if content:
                        # 处理标签跨多个chunk的情况
                        if '<think>' in content:
                            is_active = False
                            content = content.split('<think>')[0]
                        if '</think>' in content:
                            is_active = True
                            content = content.split('</think>')[-1]
                        if is_active:
                            yield content

        except Exception as e:
            error_msg = f"生成响应错误: {str(e)}"
            logger.bind(tag=TAG).error(error_msg)
            yield error_msg
