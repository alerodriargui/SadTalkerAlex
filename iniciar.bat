@echo off
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo Ejecuta primero instalar.ps1
  pause
  exit /b 1
)
".venv\Scripts\python.exe" app.py --open
pause
