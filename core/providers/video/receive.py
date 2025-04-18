import cv2
import os

cap = cv2.VideoCapture("https://2724710us1nn.vicp.fun/stream")

if not cap.isOpened():
    print("无法打开视频流")
    exit()

os.makedirs("frames", exist_ok=True)

max_frames = 10
frame_index = 0

while True:
    ret, frame = cap.read()
    if not ret:
        break

    # 计算循环编号（1 到 10）
    file_id = (frame_index % max_frames) + 1
    filename = f"/opt/xiaozhi/xiaozhi-esp32-wb/core/providers/video/frames/frame_{file_id:02d}.jpg"

    cv2.imwrite(filename, frame)
    print(f"保存 {filename}")

    frame_index += 1
