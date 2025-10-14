@echo off
echo 正在删除注册表项...
reg delete "HKEY_CLASSES_ROOT\BaiduNetdiskImageViewerAssociations" /f
reg delete "HKEY_CURRENT_USER\Software\Baidu\BaiduNetdiskImageViewer" /f
echo 正在删除程序文件...
rmdir /s /q "%APPDATA%\Baidu\BaiduNetdisk\module\ImageViewer"
echo 卸载完成！
pause