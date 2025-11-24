' 获取当前VBScript文件的完整路径
strScriptPath = WScript.ScriptFullName

' 提取路径中的目录部分
Set objFSO = CreateObject("Scripting.FileSystemObject")
strScriptDir = objFSO.GetParentFolderName(strScriptPath)

' 拼接同目录下的bat文件路径
strBatPath = objFSO.BuildPath(strScriptDir, "start_server.bat")

' 弹出提示窗口，3秒后自动关闭
Set ws = CreateObject("Wscript.Shell")
ws.Popup "正在启动服务器...", 3, "提示", 0 ' 0表示只有"确定"按钮

' 运行bat文件（隐藏窗口）
ws.Run """" & strBatPath & """ /start", 0