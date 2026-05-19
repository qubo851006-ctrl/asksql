@echo off
chcp 65001 >nul
setlocal EnableExtensions
title AskSQL Backend

set "ROOT_DIR=%~dp0"
if "%ROOT_DIR:~-1%"=="\" set "ROOT_DIR=%ROOT_DIR:~0,-1%"
set "BACKEND_DIR=%ROOT_DIR%\backend"
set "VENV_PY=%BACKEND_DIR%\.venv\Scripts\python.exe"
set "HOST=0.0.0.0"
set "PORT=8100"

echo.
echo ==========================================
echo   AskSQL 大屏问数后端启动
echo   项目目录：%ROOT_DIR%
echo   服务地址：http://服务器IP:%PORT%
echo ==========================================
echo.

if not exist "%BACKEND_DIR%\main.py" (
  echo [错误] 未找到后端入口：%BACKEND_DIR%\main.py
  pause
  exit /b 1
)

cd /d "%BACKEND_DIR%" || (
  echo [错误] 无法进入目录：%BACKEND_DIR%
  pause
  exit /b 1
)

if not exist ".env" (
  echo [错误] 未找到配置文件：%BACKEND_DIR%\.env
  echo.
  echo 请先复制 backend\.env.dashboard.example 为 backend\.env，
  echo 并填写 MariaDB 连接信息与 DICTIONARY_DIR 字典目录。
  echo.
  pause
  exit /b 1
)

set "DICTIONARY_DIR="
for /f "usebackq tokens=1,* delims==" %%A in (".env") do (
  if /I "%%A"=="DICTIONARY_DIR" set "DICTIONARY_DIR=%%B"
)
set "DICTIONARY_DIR=%DICTIONARY_DIR:"=%"

if "%DICTIONARY_DIR%"=="" (
  echo [错误] .env 中未配置 DICTIONARY_DIR
  pause
  exit /b 1
)

if not exist "%DICTIONARY_DIR%\dashboard_indicator_dictionary_utf8.tsv" (
  echo [错误] 未找到指标字典文件：
  echo %DICTIONARY_DIR%\dashboard_indicator_dictionary_utf8.tsv
  echo.
  echo 请确认 db_export_utf8_processed 目录已复制到服务器，
  echo 且 .env 里的 DICTIONARY_DIR 指向该目录。
  echo.
  pause
  exit /b 1
)

if not exist "%VENV_PY%" (
  echo [信息] 未发现虚拟环境，正在创建 .venv ...
  python -m venv .venv
  if errorlevel 1 (
    echo [错误] 创建虚拟环境失败，请确认服务器已安装 Python 并加入 PATH。
    pause
    exit /b 1
  )
)

echo [信息] 检查 Python 依赖 ...
"%VENV_PY%" -c "import fastapi, uvicorn, pymysql, dotenv" >nul 2>nul
if errorlevel 1 (
  echo [信息] 正在安装依赖 requirements.txt ...
  "%VENV_PY%" -m pip install -r requirements.txt
  if errorlevel 1 (
    echo [错误] 依赖安装失败。
    pause
    exit /b 1
  )
)

echo.
echo [信息] 启动后端服务：http://0.0.0.0:%PORT%
echo [信息] 局域网访问请使用：http://服务器IP:%PORT%/api/health
echo [信息] 关闭此窗口即可停止服务。
echo.

set "PYTHONUTF8=1"
"%VENV_PY%" -m uvicorn main:app --host %HOST% --port %PORT%

echo.
echo [信息] 服务已停止。
pause
