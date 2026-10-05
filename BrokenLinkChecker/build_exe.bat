@echo off
rem Builds dist\BrokenLinkChecker.exe (no Python needed to run the result).
cd /d "%~dp0"
python -m pip install --quiet -r requirements.txt pyinstaller || goto :error
python -m PyInstaller --noconfirm --clean --onefile --windowed --name BrokenLinkChecker gui.py || goto :error
echo.
echo Built: %~dp0dist\BrokenLinkChecker.exe
pause
exit /b 0

:error
echo.
echo Build failed.
pause
exit /b 1
