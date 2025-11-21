import cv2
print(cv2.__version__)
# 简单读取显示（若 headless 则跳过）
img = cv2.imread("some_image.png")
print(img.shape if img is not None else "read failed")
