@echo off
cd /d C:\Users\user\firdavs-ai-agent
rmdir /s /q memory_db 2>nul
call venv\Scripts\activate.bat
venv\Scripts\python.exe main.py
pause