@echo off
echo ===================================================
echo  Mercado Publico Anti-Fraude - Setup
echo ===================================================

echo.
echo [1/4] Instalando dependencias Python...
pip install -r backend\requirements.txt

echo.
echo [2/4] Instalando dependencias Node.js...
cd frontend
npm install
cd ..

echo.
echo [3/4] Ejecutando ETL (esto puede tomar varios minutos)...
python scripts\run_etl.py

echo.
echo [4/4] Ejecutando motor de deteccion de fraude...
python scripts\run_fraud_engine.py

echo.
echo ===================================================
echo  Setup completado!
echo  Para iniciar la plataforma ejecuta: start.bat
echo ===================================================
pause
