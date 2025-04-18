# xiaozhi-vision

这里首先 先感谢小智后端服务开源作者【xinnan-tech】🌹，鞠躬，感谢其开源精神，受其精神感染，我决定将增加视觉功能的后端服务版本也开源于此
开进版本使得小智系统支持语音与视频交互，具备更强的感知能力和智能交互体验。
献花：🌹🌹🌹开源项目**xiaozhi-vision** 【https://github.com/xinnan-tech/xiaozhi-esp32-server 】 🌹🌹🌹

## 🚀 项目亮点

- ✨ **视觉感知模块**：接入视觉大模型，实现对视频流和图像内容的识别、理解和响应。
- 🗣️ **语音与视频联动**：实现语音指令触发视频分析，以及视频内容生成语音反馈。
- 🎯 **模块化设计**：基于原有“小智后端服务”架构，模块解耦，易于扩展和集成。
- 📡 **多模态交互**：支持图像、视频、语音等多模态输入输出，为未来智能终端提供接口基础。

## 📂 操作指南
1、确保你能正常拉取视频流，请使用以下代码检测拉流功能：
```
import cv2
import os

cap = cv2.VideoCapture("你的摄像板子暴露的IP+端口")  # 如果你的摄像板子和后端服务处于不同的内网，请使用花生壳内网穿透将该IP映射到公网，服务器从公网拉取视频流

if not cap.isOpened():
    print("无法打开视频流")
    exit()

os.makedirs("frames", exist_ok=True)

max_frames = 2
frame_index = 0

while True:
    ret, frame = cap.read()
    if not ret:
        break

    # 计算循环编号（1 到 10）
    file_id = (frame_index % max_frames) + 1
    filename = f"frames/frame_{file_id:02d}.jpg"

    cv2.imwrite(filename, frame)
    print(f"保存 {filename}")

    frame_index += 1

```

2、其余模块我已写好，你直接使用config.yaml，在里面修改你的视觉大模型的api_kay
这里我使用的是火山引擎的豆包视觉大模型，传送带：【https://www.volcengine.com/ 】
修改位置：
![image](https://github.com/user-attachments/assets/5d4fd4b9-fa80-48d9-a356-3a823ee5d92f)
![image](https://github.com/user-attachments/assets/91fe1c31-dffd-4b45-be9e-d6a439468de9)

3、启动后端服务：python app.py，打印出以下信息说明成功
![image](https://github.com/user-attachments/assets/91723d11-6d50-4642-84af-696b5d3303da)

