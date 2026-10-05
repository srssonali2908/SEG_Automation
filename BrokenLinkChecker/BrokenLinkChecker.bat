@echo off
cd /d "%~dp0"
python -m pip install --quiet -r requirements.txt
start "" http://127.0.0.1:5000
python app.py
pause
