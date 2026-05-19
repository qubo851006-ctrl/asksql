@echo off
chcp 65001 >nul
title AI 问数 - 后端服务
cd /d "%~dp0backend"
echo.
echo  ================================
echo   大屏问数 MVP 后端服务启动中...
echo   地址：http://localhost:8100
echo   关闭此窗口即可停止服务
echo  ================================
echo.
python -m uvicorn main:app --host 0.0.0.0 --port 8100
pause
