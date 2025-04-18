from core.providers.tts.base import TTSProviderBase
import aiohttp
import os
import uuid
from datetime import datetime
from config.logger import setup_logging

TAG = __name__
logger = setup_logging()

class TTSProvider(TTSProviderBase):
    def __init__(self, config, delete_audio_file=True):
        super().__init__(config, delete_audio_file)
        self.api_key = config.get('api_key')
        self.url = config.get('url', 'http://10.255.0.179:8101/v1/audio/speech')
        self.model = config.get('model', 'melotts')
        self.voice = config.get('voice', 'Chinese Female')
        self.response_format = config.get('response_format', 'mp3')

    def generate_filename(self, extension=None):
        if extension is None:
            extension = f".{self.response_format}"
        return os.path.join(self.output_file, f"tts-{TAG}{datetime.now().date()}@{uuid.uuid4().hex}{extension}")

    async def text_to_speak(self, text, output_file):
        """
        将文本转换为语音
        :param text: 要转换的文本
        :param output_file: 输出文件路径
        :return: 输出文件路径
        """
        headers = {
            "Authorization": f"Bearer {self.api_key}"
        }
        
        data = {
            "model": self.model,
            "voice": self.voice,
            "response_format": self.response_format,
            "input": text
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(self.url, headers=headers, json=data) as response:
                    if response.status == 200:
                        content = await response.read()
                        with open(output_file, 'wb') as f:
                            f.write(content)
                        logger.bind(tag=TAG).info(f"语音生成成功: {text}:{output_file}")
                        return output_file
                    else:
                        error_text = await response.text()
                        logger.bind(tag=TAG).error(f"TTS请求失败，状态码: {response.status}")
                        logger.bind(tag=TAG).error(f"错误信息: {error_text}")
                        return None
                
        except Exception as e:
            logger.bind(tag=TAG).error(f"TTS转换错误: {str(e)}")
            return None 