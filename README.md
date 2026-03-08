# Mercado Público Anti-Fraude (V1.0) 🇨🇱

Plataforma de inteligencia operativa y auditoría diseñada para detectar automáticamente patrones de corrupción, colusión, sobreprecios y conflictos de interés en el sistema de compras públicas de Chile (Mercado Público / ChileCompra), cruzando datos con el SII, InfoLobby, RES y Contraloría.

---

## 🛠 Instalación Rápida (Recomendado para Auditores)

Para revisar el Dashboard y explorar los algoritmos, siga los siguientes pasos para levantar la plataforma en su entorno local:

### 1. Clonar el Repositorio
Descargue este código a su computadora:
```bash
git clone https://github.com/Nikoslovenian/mercado-publico-fraud.git
cd mercado-publico-fraud
```

### 2. Cargar Base de Datos Transaccional (Alertas Pre-calculadas)
Por razones de seguridad y límites de transferencia (los archivos en crudo pesan más de 1 GB), la matriz de inteligencia y las alertas históricas están comprimidas en el repositorio.

Antes de arrancar la aplicación, debe "reconstituir" la base de datos de alertas `mercado_publico.db`:

#### Windows (PowerShell/CMD)
1. Ingrese a la carpeta `data/`.
2. Extraiga el contenido del archivo `alerts.zip`. Se generará un archivo llamado `alerts.sql`.
3. Abra una terminal en esta misma carpeta y ejecute el siguiente comando para generar la base operativa:
```cmd
sqlite3 mercado_publico.db < database_schema.sql
sqlite3 mercado_publico.db < alerts.sql
```

#### macOS/Linux
```bash
cd data/
unzip alerts.zip
sqlite3 mercado_publico.db < database_schema.sql
sqlite3 mercado_publico.db < alerts.sql
cd ..
```

*(Nota: Si no tiene `sqlite3` instalado, puede usar cualquier visualizador gratuito como [DB Browser for SQLite](https://sqlitebrowser.org/) para crear una nueva base de datos llamada `mercado_publico.db` y allí ejecutar los archivos `.sql`).*

***

## 🚀 Despliegue de la Plataforma

Existen dos vías para ejecutar el motor de inteligencia y su respectivo panel visual. Ambas asumen que usted ya completó el Paso 2 de cargar sus datos de inteligencia en la carpeta `/data`.

### Opción A: Despliegue Oficial en Contenedor (Recomendado)
Para evitar problemas de librerías o dependencias de Python/Node.js, el proyecto está completamente dockerizado.  Debe tener instalado **Docker Desktop** o interactuar con `docker-compose`.

Haga doble clic en el archivo adjunto:
- 🟢 **`deploy.bat`** (En Windows).

O usando terminal directamente:
```bash
docker-compose build
docker-compose up -d
```
Luego **abra su navegador** en: `http://localhost/` o `http://localhost:80`

### Opción B: Despliegue de Desarrollo (Entorno Nativo)
Si usted es desarrollador y desea depurar los heurísticos matemáticos dentro de `backend/fraud/` y carece de Docker.

#### Levantar API / Backend (FastAPI x Python):
```bash
cd backend
python -m venv venv
venv\Scripts\activate   # (En Windows) ó "source venv/bin/activate" (en Mac/Linux)
pip install -r requirements.txt
python main.py
```

#### Levantar Dashboard / SOC Visual (React x Vite):
En otra terminal simultánea:
```bash
cd frontend
npm install
npm run dev
```
Luego **abra su navegador** en: `http://localhost:5173/`

***

## 🚨 ¿Qué patrones ilícitos documenta el sistema?
El motor de inteligencia en `backend/` mapea más de 20 heurísticas de riesgo operativo. Las principales son:
*   **FRAC (Fraccionamiento de Compras):** Identifica divisiones millonarias para evadir el umbral legal de resoluciones y Licitación Pública (100 a 1000 UTM).
*   **PREC (Sobreprecios):** Evaluación estadística multivariada de compras contra el precio de mercado histórico.
*   **CONF (Conflictos de Interés):** Cruces registrales entre encargados de finanzas y directorios/representantes del proveedor.
*   **GEOG (Anomalías Geográficas):** Direccionamiento de procesos de zonas distantes hacia empresas letrero sin delegaciones.
*   **SHLL (Fantasmas/Ad-Hoc):** Adjudicación a empresas a semanas de iniciar actividades comerciales en el SII según categoría de giro.
*   **LOBBY:** Triangulación de reuniones extraoficiales y otorgamiento de licitaciones o tratos directos.

Todas las alertas son generizadas en Reportes/Minutas Ejecutivas procesadas desde el archivo de configuración base de algoritmos en `/backend/fraud`.
