#Tesseract-OCR

# C:\Users\Administrator\AppData\Local\Programs\Tesseract-OCR
# 已经添加了环境变量


import pytesseract
from PIL import Image

def OCR_demo():
    # 导入OCR安装路径，如果设置了系统环境，就可以不用设置了
    # pytesseract.pytesseract.tesseract_cmd = r"D:\Program Files\Tesseract-OCR\tesseract.exe"
    # 打开要识别的图片

    image = Image.open('Snipaste_2025-11-21_15-19-27.jpg')
    # 使用pytesseract调用image_to_string方法进行识别，传入要识别的图片，lang='chi_sim'是设置为中文识别，
    text = pytesseract.image_to_string(image, lang='chi_sim')

    print(text)


if __name__ == '__main__':
    OCR_demo()
