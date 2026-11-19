@echo off
cd /d "%~dp0"
"%CD%\python\python.exe" -s "%CD%\launcher\start.py" "%CD%"
pause
