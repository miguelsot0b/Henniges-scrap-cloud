# scrapprod-cloud

Automatiza descargas desde Plex Cloud y actualiza archivos CSV en Google Drive para uso con Power Query.

## Qué hace
- Inicia sesión en Plex Cloud (Chromium headless) y descarga 2 reportes:
  - Producción (mes actual) -> `aug25.csv`, etc.
  - Scrap (semana actual) -> `W43Y2025.csv`, etc.
- Tras cada descarga, combina el CSV nuevo con un archivo en Google Drive reemplazando completamente todas las filas de las fechas coincidentes (merge por fecha) y sube el resultado al mismo archivo en Drive.
- Por defecto ejecuta una sola pasada; puedes habilitar bucle con la variable `LOOP=true`.
- Los CSV se guardan por defecto en la carpeta raíz del proyecto (junto a este README).

Además, puedes activar un modo de simulación para probar el merge sin subir a Drive.

## Configuración

1) Dependencias (Windows PowerShell)

```powershell
python -m pip install -r requirements.txt
# (Solo local) Instalar navegadores de Playwright si usas tu máquina
python -m playwright install chromium
```

2) Variables de entorno con archivo .env
- Copia `.env.example` a `.env` y completa los valores (incluida PLEX_PASSWORD si te resulta más simple).
- El script carga `.env` automáticamente (python-dotenv) cuando existe.

Ejemplo rápido (`.env`):
```
GOOGLE_APPLICATION_CREDENTIALS=C:\\secrets\\gdrive-sa.json
DRIVE_PRODUCTION_FILE_ID=1AbCDEFghijkProdFileId   # o pega el enlace compartido; se detecta el ID
DRIVE_SCRAP_FILE_ID=1XyZscrApFileId               # o pega el enlace compartido; se detecta el ID
PRODUCTION_DATE_COLUMN=Date
SCRAP_DATE_COLUMN=Report Date
NORMALIZE_DATE=true
PLEX_USERNAME=usuario@empresa
PLEX_PASSWORD=tu-contraseña

# Deja estas rutas vacías para guardar en la raíz del proyecto
PRODUCTION_SAVE_DIR=
SCRAP_SAVE_DIR=

# Modo simulación (no sube a Drive) y carpeta de previews (por defecto, raíz)
DRY_RUN=true
DRY_RUN_OUTPUT_DIR=
```

2.1) Contraseña de Plex
- Puedes colocar `PLEX_PASSWORD` en tu `.env` (más simple) o definirla como variable de entorno de usuario.

Notas:
- Para `DRIVE_*_FILE_ID` ahora puedes pegar el ID o el enlace de Google Drive; el script extrae el ID automáticamente.
- Si una columna de fecha tiene espacios (p. ej., `Report Date`), ponla tal cual, sin comillas.

3) Google Cloud / Service Account
- Crea un proyecto en Google Cloud y habilita la API de Google Drive.
- Crea una Service Account y genera una **clave JSON**.
- Comparte el archivo de Drive (destino CSV) con el email de la Service Account con permiso de Editor.
  - Localmente lo más simple es usar `GOOGLE_APPLICATION_CREDENTIALS` con la ruta al archivo. Opcionalmente, también soporta `GOOGLE_CREDENTIALS_JSON` o `GOOGLE_CREDENTIALS_B64` si prefieres variables de entorno.

## Cómo funciona el merge por fecha
- Se descarga el CSV actual de Drive.
- Se leen todas las fechas del CSV nuevo.
- Se eliminan del CSV de Drive todas las filas cuya fecha esté en el nuevo CSV.
- Se agregan todas las filas del nuevo CSV al final y se sube el resultado al mismo archivo en Drive.
- Si `NORMALIZE_DATE=true`, se intenta parsear fechas comunes y comparar por `YYYY-MM-DD`. Si no se puede parsear, se compara por texto exacto.

## Notas
- Los selectores y rutas de descarga de Plex están acoplados al entorno actual. Ajusta si cambian en Plex.
- Las credenciales de Plex están en el script; considera moverlas a variables de entorno por seguridad.
- Si no configuras `DRIVE_*_FILE_ID`, el script omitirá la actualización en Drive.

## Ejecución
Ejecución local (una sola pasada):
```powershell
python .\plex_downloader.py
```

Para automatizar en Windows, usa el Programador de Tareas (opcional). Si deseas un loop continuo, define `LOOP=true` y `WAIT_TIME` (segundos).

### Modo simulación (DRY_RUN)
- Cuando `DRY_RUN=true`, el script NO sube a Drive.
- En su lugar, escribe un CSV combinado de preview en la carpeta indicada (por defecto, raíz):
  - `preview-production.csv`
  - `preview-scrap.csv`
- También verás en logs un resumen: cantidad de fechas afectadas, filas removidas y filas nuevas.

Si no defines `PRODUCTION_SAVE_DIR` ni `SCRAP_SAVE_DIR`, los archivos se guardarán en la carpeta raíz del proyecto.
