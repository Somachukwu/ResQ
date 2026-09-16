@echo off
setlocal
title ResQ — Emergency Intelligence Platform

echo ======================================================================
echo    ResQ -- Responsive Emergency Systems Intelligence
echo    Engineering the emergency response Nigeria never had.
echo ======================================================================
echo.

cd /d "%~dp0"

:: Check if virtual environment exists
if exist "venv\Scripts\python.exe" (
    set "PYTHON_EXE=venv\Scripts\python.exe"
) else (
    echo [WARNING] venv not found, falling back to system Python...
    set "PYTHON_EXE=python"
)

echo [*] Initializing ResQ Local Server on port 5000...
echo [*] Dispatcher Command Center: http://localhost:5000/dispatcher
echo [*] Civilian Emergency Portal:  http://localhost:5000/civilian
echo [*] Responder Mission Brief:   http://localhost:5000/responder
echo.
echo [*] Launching web browser in 2 seconds...

:: Launch browser in background after short delay
start "" cmd /c "timeout /t 2 /nobreak >nul && start http://localhost:5000/dispatcher"

:: Start the Flask-SocketIO server
"%PYTHON_EXE%" app.py

if %ERRORLEVEL% NEQ 0 (
    echo.
    echo [ERROR] ResQ server stopped unexpectedly with error code %ERRORLEVEL%.
    pause
)

endlocal

