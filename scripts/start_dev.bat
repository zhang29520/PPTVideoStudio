@echo off
REM Windows 一键启动开发环境（需要已装 Python 3.10+ 与 Node 18+）
cd /d %~dp0backend
if not exist .venv (
  python -m venv .venv
  call .venv\Scripts\activate
  pip install -r requirements.txt
) else (
  call .venv\Scripts\activate
)
start "PVS-Backend" cmd /k python -m app.main
cd /d %~dp0desktop
if not exist node_modules npm install
start "PVS-Desktop" cmd /k npm run dev
echo PPTVideoStudio 开发环境已启动：后端 127.0.0.1:8000，桌面窗口稍后自动弹出
