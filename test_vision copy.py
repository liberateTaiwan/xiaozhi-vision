# python test_vision.py captured_images/1.png "描述一下这个图片"
import sys
import os
import base64
from volcenginesdkarkruntime import Ark
import imghdr

def encode_image(image_path):
    """将图片转换为base64编码"""
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

def analyze_image_with_ark(image_path, query="描述一下这个图片"):
    """使用Ark SDK直接调用多模态模型分析图片"""
    # 初始化Ark客户端
    client = Ark(
        # 此为默认路径，可根据业务所在地域进行配置
        base_url="https://ark.cn-beijing.volces.com/api/v3",
        # API Key
        api_key="换成你的key，我这里用的火山引擎的豆包视觉大模型的key",  # 请替换为您的实际API密钥
    )
    
    # 将图片转换为base64
    base64_image, image_format = encode_image(image_path)
    
    print(f"图片格式: {image_format}")
    data_url = f"data:image/{image_format};base64,{base64_image}"

    try:
        # 创建请求
        response = client.chat.completions.create(
            # 指定模型
            model="doubao-1-5-vision-pro-32k-250115",
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": query},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": data_url
                            },
                        },
                    ],
                }
            ],
        )

        # 打印并返回结果
        result = response.choices[0].message.content
        print(f"查询: {query}")
        print(f"结果: {result}")
        return result
    except Exception as e:
        print(f"错误: {str(e)}")
        print(f"尝试使用替代方法...")
        
        # 尝试使用替代方法
        try:
            response = client.chat.completions.create(
                # 指定模型
                model="doubao-1-5-vision-pro-32k-250115",
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": query},
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
            
            result = response.choices[0].message.content
            print(f"查询: {query}")
            print(f"结果: {result}")
            return result
        except Exception as e2:
            print(f"替代方法也失败: {str(e2)}")
            return f"无法处理图片: {str(e2)}"

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("用法: python test_vision.py <图片路径> [查询问题]")
        sys.exit(1)
    
    image_path = sys.argv[1]
    
    if not os.path.exists(image_path):
        print(f"错误: 找不到图片文件: {image_path}")
        sys.exit(1)
    
    query = sys.argv[2] if len(sys.argv) > 2 else "描述一下这个图片"
    
    analyze_image_with_ark(image_path, query) 