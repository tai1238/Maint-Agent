@echo off
rem Maint-Agent 一键演示启动：起服务 + 自动打开浏览器
cd /d %~dp0
echo [Maint-Agent] 正在启动演示服务...
start "Maint-Agent Server" cmd /k python webapp.py
timeout /t 2 /nobreak >nul
start http://127.0.0.1:7860
echo [Maint-Agent] 浏览器已打开 http://127.0.0.1:7860
echo 如页面未自动弹出，请手动访问该地址。演示前建议先运行: python reset_demo.py
pause
