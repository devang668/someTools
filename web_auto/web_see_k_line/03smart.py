
"""
需求总结：
1. **同时监控多个固定屏幕区域**（比如 4~8 个）
2. **每个区域给一个名字**（比如：价格、挂单量、深度、资金费率...）
3. **区域内有干扰数字**（浅色/背景色），我们要只识别 **深色背景 + 白色数字**
4. **关键数字经常变化**（如 2999.23 → 2745.14），而干扰数字永远不变（如 3,150.00）
5. **如果本次识别“少了一个数字”或“识别异常”** → 自动使用上一次的有效值（防闪、防止漏识别）
6. **最终输出结构化数据**，方便你后期查询、绘图、报警

"""
import time
import base64
import requests
from PIL import Image, ImageGrab
from datetime import datetime
import json
import os

# ==================== 配置区（你只需要改这里） ====================

# 每个监控区域的配置：名字 + 坐标 + 要排除的干扰数字（永远不变的那些）
MONITOR_REGIONS = {
    "当前价格": {
        "bbox": (1274, 180, 1316, 422),        # 你原来的区域
        "exclude": ["3,150.00", "3,100.00", "3,050.00", "3,000.00", "2,950.00", "2,900.00", "2,850.00", "2,800.00"]
    },
    "指标区域": {
        "bbox": (1274, 424, 1317,573),
        "exclude": ["2,000", "1,800", "1,600"]
    },

}

"""
    "当前价格": {
        "bbox": (1275, 496, 1318, 553),        # 你原来的区域
        "exclude": ["3,150.00", "3,100.00", "3,050.00", "3,000.00", "2,950.00", "2,900.00", "2,850.00", "2,800.00"]
    },
    "指标区域": {
        "bbox": (1350, 600, 1420, 650),
        "exclude": ["2,000", "1,800", "1,600"]
    },
    "卖一量": {
        "bbox": (1350, 400, 1420, 450),
        "exclude": ["1,500", "1,200"]
    },
    # 继续添加你需要的区域...


"""

OCR_URL = "http://127.0.0.1:1224/api/ocr"
INTERVAL = 3                    # 每3秒检测一次
OUTPUT_FILE = "实时监控数据.json"   # 结构化数据（推荐）
LOG_FILE = "监控日志.txt"

# ==============================================================

# 全局存储：保存上一次的有效结果（用于补位）
last_valid_data = {name: "待识别" for name in MONITOR_REGIONS.keys()}

def capture_region(bbox):
    return ImageGrab.grab(bbox=bbox)

def image_to_base64(img):
    import io
    buffer = io.BytesIO()
    img.save(buffer, format='PNG')
    return base64.b64encode(buffer.getvalue()).decode()

def ocr_image(img):
    b64 = image_to_base64(img)
    try:
        resp = requests.post(OCR_URL, json={
            "base64": b64,
            "options": {"data.format": "text"}
        }, timeout=8)
        resp.raise_for_status()
        return resp.json().get("data", "").strip()
    except:
        return ""

def extract_number(text, exclude_list):
    """从OCR文本中提取最可能的“动态数字”"""
    if not text:
        return None
    
    lines = [line.strip() for line in text.replace(",", "").split("\n") if line.strip()]
    candidates = []
    
    for line in lines:
        line_clean = line.replace(",", "").replace(" ", "")
        if any(ex in line_clean for ex in exclude_list):
            continue
        # 过滤掉纯整数、带.00结尾的、太短的
        if "." in line_clean and not line_clean.endswith(".00"):
            if len(line_clean.replace(".", "").replace("-", "")) >= 4:
                candidates.append(line)
    
    # 返回最下面那个（通常是最新价格）
    return candidates[-1] if candidates else None

def monitor_once():
    global last_valid_data
    current_data = {}
    timestamp = datetime.now().strftime("%H:%M:%S")
    
    print(f"\n[{timestamp}] 正在识别...")
    
    for name, config in MONITOR_REGIONS.items():
        bbox = config["bbox"]
        exclude = config["exclude"]
        
        img = capture_region(bbox)
        text = ocr_image(img)
        
        number = extract_number(text, exclude)
        
        if number and number != "待识别":
            # 成功识别到动态数字 → 更新
            current_data[name] = number
            last_valid_data[name] = number
            print(f"  {name}: {number}  [新]")
        else:
            # 识别失败或被干扰 → 使用上一次的有效值
            fallback = last_valid_data[name]
            current_data[name] = fallback
            status = "漏识别" if fallback != "待识别" else "初始化"
            print(f"  {name}: {fallback}  [{status}，已补位]")
    
    # 保存结构化数据（追加到JSON数组）
    save_json_log(timestamp, current_data)
    save_text_log(timestamp, current_data)
    
    return current_data

def save_json_log(timestamp, data):
    entry = {"time": timestamp, **data}
    if os.path.exists(OUTPUT_FILE):
        with open(OUTPUT_FILE, "r", encoding="utf-8") as f:
            try:
                all_data = json.load(f)
            except:
                all_data = []
    else:
        all_data = []
    
    all_data.append(entry)
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(all_data, f, ensure_ascii=False, indent=2)

def save_text_log(timestamp, data):
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(f"[{timestamp}]\n")
        for k, v in data.items():
            f.write(f"  {k}: {v}\n")
        f.write("-" * 50 + "\n")

def main():
    print("极稳多区域监控已启动（支持干扰过滤 + 自动补位）")
    print("按 Ctrl+C 停止")
    print(f"数据保存：{OUTPUT_FILE}（推荐用Python绘图）")
    print(f"日志查看：{LOG_FILE}\n")
    
    # 清空日志
    open(LOG_FILE, 'w').close()
    
    try:
        while True:
            monitor_once()
            time.sleep(INTERVAL)
    except KeyboardInterrupt:
        print("\n监控已停止。数据已保存！")
        print(f"结构化数据：{OUTPUT_FILE}")
        print("可以用 pandas 直接读取绘图哦~")

if __name__ == "__main__":
    main()


"""  

### 输出示例（实时监控数据.json）
json
[
  {
    "time": "14:32:11",
    "当前价格": "2,745.14",
    "买一量": "1,234.56",
    "卖一量": "987.32"
  },
  {
    "time": "14:32:14",
    "当前价格": "2,745.34",
    "买一量": "1,234.56",
    "卖一量": "987.32"
  }
]
"""

