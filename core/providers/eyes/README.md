# ESP32 视觉与语音处理服务

这个服务为ESP32摄像头和麦克风提供AI视觉识别和语音交互能力。服务通过集成Qwen2.5-VL视觉语言模型，可以接收ESP32传来的图像和语音，进行多模态分析，并返回语音回答。

## 功能特点

- 接收ESP32摄像头拍摄的图像
- 接收ESP32麦克风采集的用户语音（或已转换的文本）
- 使用Qwen2.5-VL多模态大模型进行图像内容理解
- 结合用户语音输入作为提示词，实现更精准的视觉分析
- 生成语音回复，发送回ESP32播放

## API接口

### 1. 处理视觉和语音数据

**端点**: `/vision_process`

**方法**: POST

**请求格式**:
```json
{
    "image": "base64编码的图像",
    "audio": "base64编码的音频(可选)",
    "text": "语音转文本结果(可选)"
}
```

**响应格式**:
```json
{
    "message": "Qwen模型的回答文本",
    "audio_url": "生成的TTS音频URL"
}
```

### 2. ESP32专用端点

**端点**: `/esp32_endpoint`

**方法**: POST

**参数**:
- `type`: 请求类型，可选值为`process`或`get_audio`

**用法**:
1. 当`type=process`时，功能与`/vision_process`相同
2. 当`type=get_audio`时，将直接返回生成的音频文件数据

**获取音频的额外参数**:
- `audio_url`: 之前请求中返回的音频URL

## 与ESP32集成示例

### ESP32发送图像和语音:

```cpp
// 准备HTTP POST请求
HTTPClient http;
http.begin("http://your-server-ip:5000/esp32_endpoint?type=process");
http.addHeader("Content-Type", "application/json");

// 构建请求体
String requestBody = "{\"image\":\"" + base64Image + "\",";
if (hasAudio) {
    requestBody += "\"audio\":\"" + base64Audio + "\",";
}
if (hasText) {
    requestBody += "\"text\":\"" + recognizedText + "\",";
}
requestBody += "}";

// 发送请求
int httpResponseCode = http.POST(requestBody);
if (httpResponseCode > 0) {
    String response = http.getString();
    // 解析JSON响应
    DynamicJsonDocument doc(1024);
    deserializeJson(doc, response);
    
    String message = doc["message"];
    String audioUrl = doc["audio_url"];
    
    // 获取音频文件
    http.begin("http://your-server-ip:5000/esp32_endpoint?type=get_audio&audio_url=" + audioUrl);
    int audioResponseCode = http.GET();
    if (audioResponseCode > 0) {
        // 处理音频数据并播放
        uint8_t* audioBuffer = http.getStream().readBytes(http.getSize());
        playAudio(audioBuffer, http.getSize());
    }
}
```

## 配置说明

服务需要配置以下参数:

1. `VLLM_API_URL`: Qwen2.5-VL模型服务的API地址
2. `TTS_API_URL`: 文本转语音服务的API地址
3. `VLLM_MODEL`: Qwen2.5-VL模型的路径
4. `AUDIO_FOLDER`: 生成的音频文件存储路径

## 与xiaozhi服务器集成

本服务已集成到xiaozhi智能助手系统中，作为视觉处理模块的一部分。当ESP32设备通过websocket连接到xiaozhi服务器时，可以使用专门的协议发送图像和语音进行处理。 