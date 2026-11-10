@echo off
cd /d "%~dp0"

where python >nul 2>nul
if errorlevel 1 (
    echo Python was not found. Install Python 3.10+ from https://www.python.org/downloads/
    echo and tick "Add Python to PATH", or use BrokenLinkChecker.exe instead.
    goto :end
)

python -m pip install --quiet -r requirements.txt
if errorlevel 1 (
    echo.
    echo Installing the dependencies failed - see the error above.
    goto :end
)

rem app.py opens the browser itself once the server is accepting connections.
python app.py --open
echo.
echo The server has stopped. If this was unexpected, see the error above
echo ^(for example, port 5000 already in use: set PORT=5050 and run again^).

:end
pause
