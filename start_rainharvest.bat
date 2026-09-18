@echo off
cd /d "%~dp0"
start "RainHarvest Pro" cmd /k python app.py
timeout /t 3 /nobreak >nul
start "" "http://rainharvest.local:5000/"
