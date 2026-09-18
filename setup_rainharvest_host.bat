@echo off
setlocal
set "HOSTS=%SystemRoot%\System32\drivers\etc\hosts"
findstr /R /C:"^[ ]*127\.0\.0\.1[ ]*rainharvest\.local" "%HOSTS%" >nul 2>&1
if %errorlevel%==0 (
    echo rainharvest.local is already configured.
    pause
    exit /b 0
)

net session >nul 2>&1
if not %errorlevel%==0 (
    echo Requesting administrator permission to update the Windows hosts file...
    powershell -NoProfile -Command "Start-Process -FilePath '%~f0' -Verb RunAs"
    exit /b 0
)

>>"%HOSTS%" echo 127.0.0.1 rainharvest.local
echo Added rainharvest.local to the Windows hosts file.
echo You can now open: http://rainharvest.local:5000/
pause
