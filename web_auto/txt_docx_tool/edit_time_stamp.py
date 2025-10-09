#!/usr/bin/env python3
# fix_timestamp_here.py
import re
import os
import json
from datetime import datetime

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

def ms2str(ms: int) -> str:
    """13 位毫秒时间戳 → 'YYYY-MM-DD HH:MM:SS'"""
    return datetime.fromtimestamp(ms / 1000).strftime('%Y-%m-%d %H:%M:%S')

def replace_ts_in_text(text: str) -> str:
    """正则替换所有 "timestamp": 13位数字"""
    def _repl(m):
        return f'"time": "{ms2str(int(m.group(1)))}"'
    return re.sub(r'"timestamp"\s*:\s*(\d{13})', _repl, text)

def process_file(file_path: str, save_path: str):
    """按类型读取 → 替换 → 写入新文件"""
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()

    ext = os.path.splitext(file_path)[1].lower()
    if ext == '.json':
        try:
            data = json.loads(content)
            # 再 dumps 成字符串，统一走文本替换
            content = json.dumps(data, ensure_ascii=False, indent=2)
        except json.JSONDecodeError:
            pass  # 非标准 JSON 直接当纯文本处理

    new_content = replace_ts_in_text(content)

    with open(save_path, 'w', encoding='utf-8') as f:
        f.write(new_content)

def main():
    targets = [f for f in os.listdir(SCRIPT_DIR)
               if f.lower().endswith(('.txt', '.md', '.json'))]

    for fname in targets:
        base, ext = os.path.splitext(fname)
        new_name = f"{base}_edited{ext}"
        src = os.path.join(SCRIPT_DIR, fname)
        dst = os.path.join(SCRIPT_DIR, new_name)

        # 跳过已生成的 *_edited 文件，防止重复处理
        if base.endswith('_edited'):
            continue

        process_file(src, dst)
        print(f"生成：{new_name}")

if __name__ == '__main__':
    main()
