#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
@author: 'Guohan'
@file: main.py
@time: 1/7/2025 上午 12:33
@functions：please note ..
"""

import msoffcrypto
import io
import openpyxl
import itertools
import time


def crack_excel_password(file_path):
    # 定义密码前缀和后缀
    prefix = 'Cgg@51'
    known_digits = '88'

    # 初始化计数器和开始时间
    total_attempts = 0
    start_time = time.time()

    print(f"开始破解Excel文件: {file_path}")

    # 生成所有可能的后两位数字组合（8800-8899）
    for digits in itertools.product('0123456789', repeat=2):
        # 构建完整的密码
        password = prefix + known_digits + ''.join(digits)
        total_attempts += 1

        try:
            # 使用msoffcrypto尝试解密文件
            with open(file_path, 'rb') as f:
                file = msoffcrypto.OfficeFile(f)
                file.load_key(password=password)  # 尝试加载密码

                # 创建临时缓冲区
                decrypted = io.BytesIO()
                file.decrypt(decrypted)  # 尝试解密

                # 如果解密成功，尝试用openpyxl打开
                decrypted.seek(0)  # 重置缓冲区指针
                wb = openpyxl.load_workbook(decrypted)

                # 如果成功打开，打印密码并返回
                elapsed_time = time.time() - start_time
                print(f"\n密码已找到! 正确密码是: {password}")
                print(f"尝试次数: {total_attempts}")
                print(f"耗时: {elapsed_time:.2f}秒")
                return password

        except msoffcrypto.exceptions.InvalidKeyError:
            # 如果密码错误，继续尝试
            print(f"尝试 {total_attempts}: 密码 {password} 错误", end='\r')
        except Exception as e:
            # 处理其他异常
            print(f"\n发生错误: {str(e)}")
            return None

    # 如果所有组合都尝试失败
    elapsed_time = time.time() - start_time
    print(f"\n所有可能的密码都已尝试，但未找到正确密码。")
    print(f"总尝试次数: {total_attempts}")
    print(f"耗时: {elapsed_time:.2f}秒")
    return None


if __name__ == "__main__":
    # 请替换为你的Excel文件路径
    file_path = "12.xlsx"
    crack_excel_password(file_path)