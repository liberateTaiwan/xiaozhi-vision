# xiaozhi-vision
给小智融入视觉模块实现视觉大模型交互

# 你需要准备的硬件材料
2张Esp32s3开发板，1个uvc协议摄像模组，杜邦线若干

## 程序
# 小智烧录的程序（可直接去[虾哥项目](https://github.com/78/xiaozhi-esp32)）
1、cd 你本地小智代码的根目录

2、idf.py menuconfig

![image](https://github.com/user-attachments/assets/b84d3bf5-67f5-4261-a963-483dfcc1f726)

3、设置为WS协议，并修改后端地址为你自己的后端代码开放的ip和端口

![a7afcd6008795552e9755122b8865b0c](https://github.com/user-attachments/assets/47da60e3-ec17-4004-9f28-f0a7f8bfd0a3)

4、idf.py set-target esp32s3

5、idf.py build flash monitor

# 后端服务的程序（可直接去[大佬开源的后端服务](https://github.com/xinnan-tech/xiaozhi-esp32-server)）
1、先跑通该后端服务，出现ip和端口即可进行下一步
![dcbf56e19b566e3480fec4872dada9ad](https://github.com/user-attachments/assets/d46e51ea-8f84-4763-a003-b1750a2915dc)

2、去火山引擎申请一个视觉大模型的key

3、修改config.yaml，添加视觉模块功能

4、修改处理函数，设置请求体，修改后端逻辑，添加关键词检测
client = Ark(
        # 此为默认路径，您可根据业务所在地域进行配置
        base_url="https://ark.cn-beijing.volces.com/api/v3",
        # 从环境变量中获取您的 API Key。此为默认方式，您可根据需要进行修改
        api_key="你的API",
    )
    
    #原图片转base64
    base64_image = encode_image(image_path)


    response = client.chat.completions.create(
        # 指定您创建的方舟推理接入点 ID，此处已帮您修改为您的推理接入点 ID
        model="doubao-1-5-vision-pro-32k-250115",
        messages=[
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": "描述一下这个图片"},
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


    print(response.choices[0].message.content)
    
    return ActionResponse(Action.RESPONSE, None, response.choices[0].message.content)，
5、监测到关键词，调用视觉模型功能

# uvc-camera程序（可直接去[乐鑫官方的示例例程代码](https://github.com/espressif/esp-iot-solution/tree/d09966201afeab0135aa741e8ad6ed5a1ed09b6a/examples/usb/host/usb_camera_mic_spk)）
1、将uvc摄像模组插入到另一块esp32s3开发板

2、烧录uvc-camera程序，进入monitor查看摄像头ip

3、手机打开wifi搜索到这个板子开放的热点，连接之后，进入该ip地址即可查看画面
![image](https://github.com/user-attachments/assets/ae1997ce-ef8e-45ca-a7a2-c2834becc990)

4、修改程序网络模式由AP为STA，让该板子连接到公共的wifi环境，需要保证自己的后端服务程序也在该网络下，与摄像板子处于同一个网络，即可！
AP：开放热点，你只有连上摄像模块所在板子开放的热点，你才能访问画面
STA：摄像板子和访问终端在一个网段，终端就可以访问摄像画面
内网穿透：由于摄像板子只能链接2.4G网络，可能与后端服务所在网络不在一起，需要将摄像板子开放的IP及端口映射到公网，再由后端服务器访问其公网IP以获取画面
