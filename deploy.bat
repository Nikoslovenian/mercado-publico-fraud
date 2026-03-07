@echo off
echo ===================================================
echo  Mercado Publico Anti-Fraude - Deployment en PROD
echo ===================================================
echo.
echo Iniciando el entorno de produccion mediante Docker Compose...
echo Compilando imagenes (esto tomara un momento)...
echo.

docker-compose build
if %errorlevel% neq 0 (
    echo [ERROR] Fallo en la construccion de la imagen Docker.
    pause
    exit /b %errorlevel%
)

echo.
echo ===================================================
echo  Desplegando componentes en background (Daemon)
echo ===================================================
docker-compose up -d

echo.
echo Contenedores levantados correctamente:
docker-compose ps

echo.
echo EL DASHBOARD (SOC) DEBERIA ESTAR DISPONIBLE EN EL PUERTO 80 (FRONTEND) Y EL API EN EL PUERTO 8000.
echo Abre tu navegador y dirígete a: http://localhost/
echo.
echo Para detener la plataforma ejecuta: docker-compose down
pause
