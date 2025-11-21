import requests
import json
import base64
import os
from datetime import datetime

def ocr_image(image_path):
    """对单张图片进行 OCR"""
    with open(image_path, "rb") as img_file:
        base64_string = base64.b64encode(img_file.read()).decode('utf-8')
    
    url = "http://127.0.0.1:1224/api/ocr"
    data = {
        "base64": base64_string,
        "options": {"data.format": "text"}
    }
    
    try:
        response = requests.post(url, json=data, timeout=30)
        response.raise_for_status()
        return response.json().get('data', '识别失败')
    except Exception as e:
        return f"错误: {e}"

def batch_ocr(folder_path):
    """批量处理并保存结果"""
    jpg_files = [f for f in os.listdir(folder_path) if f.lower().endswith('.jpg')]
    
    # 保存结果
    results = []
    for jpg_file in jpg_files:
        file_path = os.path.join(folder_path, jpg_file)
        print(f"正在处理: {jpg_file}")
        text = ocr_image(file_path)
        results.append({"文件名": jpg_file, "识别结果": text})
    
    # 保存为 JSON
    with open('ocr_results.json', 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    
    # 保存为 TXT
    with open('ocr_results.txt', 'w', encoding='utf-8') as f:
        for item in results:
            f.write(f"文件: {item['文件名']}\n")
            f.write(f"结果: {item['识别结果']}\n")
            f.write("-" * 50 + "\n")
    
    print("结果已保存到 ocr_results.json 和 ocr_results.txt")

if __name__ == '__main__':
    folder_path = os.getcwd()
    batch_ocr(folder_path)
    print('处理完毕！')