# /opt/xiaozhi/xiaozhi-esp32-wb/core/vision/vision_model.py
from volcenginesdkarkruntime import Ark
import base64
import cv2
import os

class VisionModel:
    def __init__(self, config):
        self.config = config
        vision_config = config.get("vision", {})
        self.client = Ark(
            base_url="https://ark.cn-beijing.volces.com/api/v3",
            api_key=vision_config.get("api_key", "你的API")
        )
        self.model = vision_config.get("model", "doubao-1-5-vision-pro-32k-250115")

    def encode_image(self, image_path):
        with open(image_path, "rb") as image_file:
            return base64.b64encode(image_file.read()).decode('utf-8')

    def analyze_image(self, image_path, user_question="描述一下这个图片"):
        base64_image = self.encode_image(image_path)
        
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": user_question},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/jpeg;base64,{base64_image}"
                            },
                        },
                    ],
                }
            ],
        )
        
        return response.choices[0].message.content