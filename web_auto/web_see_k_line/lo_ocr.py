import time
import base64
import os
import requests
from PIL import ImageGrab
from datetime import datetime

# ==================== 配置区域 ====================

# 你要监控的屏幕区域（左, 上, 右, 下）
# 你给的是 (1275,496) 到 (1318,553)
LEFT, TOP, RIGHT, BOTTOM = 1273, 491, 1316, 555

# OCR 本地服务地址（你之前用的那个）
OCR_URL = "http://127.0.0.1:1224/api/ocr"

# 结果保存文件
OUTPUT_FILE = "监控结果.txt"

# 每隔多少秒截图一次
INTERVAL = 3

# ================================================

def capture_screen_region():
    """截取屏幕指定区域"""
    bbox = (LEFT, TOP, RIGHT, BOTTOM)
    screenshot = ImageGrab.grab(bbox=bbox)
    return screenshot

def image_to_base64(img):
    """PIL 图片转 base64 字符串（不带 data: 前缀）"""
    import io
    buffer = io.BytesIO()
    img.save(buffer, format='PNG')
    return base64.b64encode(buffer.getvalue()).decode('utf-8')

def ocr_text(base64_str):
    """调用你的本地 OCR 服务"""
    payload = {
        "base64": base64_str,
        "options": {
            "data.format": "text"
        }
    }
    try:
        resp = requests.post(OCR_URL, json=payload, timeout=10)
        resp.raise_for_status()
        text = resp.json().get("data", "").strip()
        return text
    except Exception as e:
        return f"[OCR错误: {e}]"

def append_result(text):
    """追加写入结果文件，带时间戳"""
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open(OUTPUT_FILE, "a", encoding="utf-8") as f:
        f.write(f"[{now}] 识别结果：\n{text}\n")
        f.write("-" * 50 + "\n")
    print(f"[{now}]\n{text}\n")

def main():
    print(f"开始监控屏幕区域 ({LEFT},{TOP}) → ({RIGHT},{BOTTOM})")
    print(f"每 {INTERVAL} 秒识别一次，结果追加到 {OUTPUT_FILE}")
    print("按 Ctrl+C 停止监控\n")
    print("-" * 60)

    # 清空旧文件（可选，第一次运行时）
    if os.path.exists(OUTPUT_FILE):
        open(OUTPUT_FILE, 'w').close()

    try:
        while True:
            # 1. 截图
            img = capture_screen_region()
            
            # 2. 转 base64
            b64 = image_to_base64(img)
            
            # 3. OCR 识别
            text = ocr_text(b64)
            
            # 4. 保存并打印
            append_result(text if text else "无内容")
            
            # 5. 等待下一次
            time.sleep(INTERVAL)
            
    except KeyboardInterrupt:
        print("\n监控已停止。结果已保存到：", OUTPUT_FILE)

if __name__ == "__main__":
    main()