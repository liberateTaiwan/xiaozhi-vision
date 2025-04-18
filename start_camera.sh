#!/bin/bash

# 安装必要的依赖
echo "正在安装必要的依赖..."
pip install flask flask-socketio eventlet python-socketio opencv-python numpy

# 启动视频流服务器
echo "正在启动视频流服务器..."
python camera_app.py --port 8008

# 您可以使用以下命令在后台运行服务器
# nohup python camera_app.py --port 8008 > camera_log.txt 2>&1 & 