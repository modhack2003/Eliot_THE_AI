@echo off
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0install.ps1" %*
set "eliot_result=%ERRORLEVEL%"
pause
exit /b %eliot_result%
