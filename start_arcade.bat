
@echo off
title ARCADE - Start All Services

set ROOT=C:\Users\Administrator\Desktop\game

echo Starting ARCADE services...

echo Starting Django backend...
start "ARCADE Backend" cmd /k "cd /d %ROOT%\backend && %ROOT%\venv\Scripts\activate && python manage.py runserver 0.0.0.0:8000"

timeout /t 3 /nobreak >nul

echo Starting Mouse Bridge...
start "ARCADE Mouse Bridge" cmd /k "cd /d %ROOT%\windows_detector && %ROOT%\venv\Scripts\activate && python mouse_event_bridge.py"

timeout /t 3 /nobreak >nul

echo Starting Game Engine...
start "ARCADE Game Engine" cmd /k "cd /d %ROOT%\backend && %ROOT%\venv\Scripts\activate && python manage.py run_game"

timeout /t 3 /nobreak >nul

echo Starting React Frontend...
start "ARCADE Frontend" cmd /k "cd /d %ROOT%\frontend && npm run dev -- --host 0.0.0.0"

echo.
echo All ARCADE services have been launched.
echo Frontend: http://localhost:5173
echo Backend:  http://localhost:8000
echo Mouse Bridge: http://localhost:8765/health
pause
