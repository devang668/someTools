@echo off
echo ����ɾ��ע�����...
reg delete "HKEY_CLASSES_ROOT\BaiduNetdiskImageViewerAssociations" /f
reg delete "HKEY_CURRENT_USER\Software\Baidu\BaiduNetdiskImageViewer" /f
echo ����ɾ�������ļ�...
rmdir /s /q "%APPDATA%\Baidu\BaiduNetdisk\module\ImageViewer"
echo ж����ɣ�
pause