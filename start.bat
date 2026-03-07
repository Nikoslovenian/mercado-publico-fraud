@echo off
echo ===================================================
echo  Mercado Publico Anti-Fraude - Iniciando...
echo ===================================================

echo.
echo Iniciando backend (FastAPI en puerto 8000)...
start "Backend API" cmd /k "cd /d %~dp0backend && python -m uvicorn main:app --reload --port 8000"

timeout /t 3 /nobreak > nul

echo Iniciando frontend (React en puerto 5173)...
start "Frontend React" cmd /k "cd /d %~dp0frontend && npm run dev"

timeout /t 3 /nobreak > nul

echo.
echo ===================================================
echo  Plataforma lista!
echo  Abrir en navegador: http://localhost:5173
echo ===================================================
start "" "http://localhost:5173"
