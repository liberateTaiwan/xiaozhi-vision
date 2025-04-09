# xiaozhi-vision
给小智融入视觉模块实现视觉大模型交互

# 你需要准备的硬件材料
2张Esp32s3开发板，1个uvc协议摄像模组，杜邦线若干

## 程序
# 小智烧录的程序（可直接去虾哥项目拉取[1](https://github.com/78/xiaozhi-esp32)）
1、cd 你本地小智代码的根目录
2、idf.py menuconfig

![image](https://github.com/user-attachments/assets/b84d3bf5-67f5-4261-a963-483dfcc1f726)

3、设置为WS协议，并修改后端地址为你自己的后端代码开放的ip和端口
4、idf.py set-target esp32s3
5、idf.py build flash monitor

# 后端服务的程序（可直接去[2](https://github.com/xinnan-tech/xiaozhi-esp32-server)）
1、先跑通该后端服务，出现ip和端口即可进行下一步
2、去火山引擎申请一个视觉大模型的key
3、修改config.yaml，添加视觉模块功能
4、修改处理函数，添加关键词检测
5、监测到关键词，调用视觉模型功能

# uvc-camera程序（可直接去[3](https://github.com/espressif/esp-iot-solution/tree/d09966201afeab0135aa741e8ad6ed5a1ed09b6a/examples/usb/host/usb_camera_mic_spk)）
1、将uvc摄像模组插入到另一块esp32s3开发板
2、烧录uvc-camera程序，进入monitor查看摄像头ip
3、手机打开wifi搜索到这个板子开放的热点，连接之后，进入该ip地址即可查看画面
4、修改程序网络模式为STA，让该板子连接到公共的wifi环境，需要保证自己的后端服务程序也在该网络下，与摄像板子处于同一个网络，即可！
