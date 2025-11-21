import cv2
import numpy as np
from PIL import ImageGrab
import time
import os

# 配置
COLOR_RANGES = {
    "red":  ((0, 120, 50), (10, 255, 255)),
    "green": ((40, 50, 50), (85, 255, 255)),
    "yellow": ((18, 100, 100), (35, 255, 255)),
    "purple": ((125, 30, 30), (155, 255, 255)),
    "blue": ((100, 80, 50), (130, 255, 255))
}
MIN_AREA = 60
LEFT_PAD_RATIO = 0.06  # ROI 向左扩展占屏宽比例
SAVE_ROI_DIR = "roi_samples"
os.makedirs(SAVE_ROI_DIR, exist_ok=True)

def grab_frame():
    img = ImageGrab.grab()
    frame = cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)
    return frame

def detect_color_blocks(frame):
    hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
    h, w = frame.shape[:2]
    blocks = []
    for name, (low, high) in COLOR_RANGES.items():
        mask = cv2.inRange(hsv, np.array(low), np.array(high))
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (3,3))
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel, iterations=1)
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel, iterations=1)
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        for cnt in contours:
            area = cv2.contourArea(cnt)
            if area < MIN_AREA:
                continue
            x,y,ww,hh = cv2.boundingRect(cnt)
            cx, cy = x + ww//2, y + hh//2
            blocks.append({"color": name, "rect": (x,y,ww,hh), "cx":cx, "cy":cy})
    return blocks

def crop_number_roi(frame, block):
    h, w = frame.shape[:2]
    cx, cy = block["cx"], block["cy"]
    # 左侧扩展
    left = max(0, int(cx - LEFT_PAD_RATIO * w))
    right = max(0, cx - 2)
    top = max(0, cy - int(block["rect"][3] * 1.0))
    bottom = min(h, cy + int(block["rect"][3] * 1.0))
    if right <= left:
        right = cx + 4
    roi = frame[top:bottom, left:right]
    return roi, (left, top, right, bottom)

# 主循环
idx = 0
while True:
    frame = grab_frame()
    blocks = detect_color_blocks(frame)
    for b in blocks:
        roi, bbox = crop_number_roi(frame, b)
        # 保存 ROI 以便离线调参或训练数字识别模型
        fn = f"{SAVE_ROI_DIR}/{idx}_{b['color']}.png"
        cv2.imwrite(fn, roi)
        idx += 1
        cv2.rectangle(frame, (bbox[0], bbox[1]), (bbox[2], bbox[3]), (0,255,0), 1)
        cv2.putText(frame, b['color'], (bbox[0], bbox[1]-6), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255,255,255),1)
    cv2.imshow("det", frame)
    if cv2.waitKey(1) & 0xFF == ord('q'):
        break
    time.sleep(0.5)
cv2.destroyAllWindows()
