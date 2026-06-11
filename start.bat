@echo off
cd /d C:\Users\User\Desktop\project\teacher-analytics

echo Installing dependencies...
pip install -r requirements.txt

echo Starting Flask server...
start /min python app/server.py

echo Waiting for server to start...
timeout /t 3 /nobreak >nul

echo Opening browser...
start http://127.0.0.1:5000

echo Project is running. Close the server window to stop.