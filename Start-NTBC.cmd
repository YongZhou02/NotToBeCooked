@echo off
cd /d "%~dp0"
"%~dp0apps\api\.venv\Scripts\python.exe" "%~dp0scripts\start_demo.py"
if errorlevel 1 pause
