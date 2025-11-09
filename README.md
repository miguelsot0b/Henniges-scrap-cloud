# Henniges Scrap & Production Cloud Automation

Automatiza la descarga de reportes desde Plex Cloud y sincroniza los datos con Google Drive para análisis en Power Query/Excel/Power BI.

## 🎯 Funcionalidades

- **Automatización de Plex Cloud**: Login automatizado con Playwright (Chromium headless)
- **Descarga de 2 reportes diarios**:
  - **Production**: Reporte mensual (formato: `nov25.csv`, `dec25.csv`, etc.)
  - **Scrap**: Reporte semanal (formato: `W45Y2025.csv`, `W46Y2025.csv`, etc.)
- **Sincronización inteligente con Google Drive**:
  - Merge por fecha: Reemplaza registros de fechas coincidentes
  - Preserva datos históricos de otras fechas
  - Limpieza automática de BOM (Byte Order Mark) y saltos de línea dentro de celdas
- **Power Query Ready**: Links directos de descarga para Excel/Power BI
- **Modo simulación (DRY_RUN)**: Prueba el merge sin modificar Drive

## 📋 Requisitos

- Python 3.13+
- Windows PowerShell
- Cuenta de Google Cloud con Service Account
- Credenciales de Plex Cloud

## 🚀 Instalación

### 1. Clonar el repositorio

```powershell
git clone https://github.com/miguelsot0b/Henniges-scrap-cloud.git
cd Henniges-scrap-cloud
```

### 2. Instalar dependencias

```powershell
python -m pip install -r requirements.txt
python -m playwright install chromium
```

### 3. Configurar variables de entorno

Crea un archivo `.env` en la raíz del proyecto:

```env
# Google Cloud Service Account
GOOGLE_APPLICATION_CREDENTIALS=henniges-ea459ee8daab.json

# IDs de archivos en Google Drive
DRIVE_PRODUCTION_FILE_ID=https://drive.google.com/file/d/1EhVdt8n6eIjJF0afLm5irDZQv2CDRi7w/view
DRIVE_SCRAP_FILE_ID=https://drive.google.com/file/d/1gVbCYSpTNtWE25ZHOPHzDBnkucLIaDN9/view

# Columnas de fecha en los CSV
PRODUCTION_DATE_COLUMN=Date
SCRAP_DATE_COLUMN=Report Date

# Normalización de fechas (recomendado: true)
NORMALIZE_DATE=true

# Credenciales de Plex
PLEX_USERNAME=tu.usuario
PLEX_PASSWORD=tu-contraseña

# Directorios de descarga (opcional, vacío = raíz del proyecto)
PRODUCTION_SAVE_DIR=
SCRAP_SAVE_DIR=

# Modo simulación (no sube a Drive)
DRY_RUN=false
DRY_RUN_OUTPUT_DIR=
```

### 4. Configurar Google Cloud Service Account

1. Crea un proyecto en [Google Cloud Console](https://console.cloud.google.com)
2. Habilita la **Google Drive API**
3. Crea una **Service Account**
4. Genera una clave JSON y guárdala como `henniges-ea459ee8daab.json`
5. **Comparte los archivos de Google Drive** con el email de la Service Account (permiso: Editor)
   - Email: `plex-drive-sync@henniges.iam.gserviceaccount.com`

## 🔧 Uso

### Ejecución básica (una sola vez)

```powershell
python plex_downloader.py
```

### Modo simulación (sin subir a Drive)

Cambia en `.env`:
```env
DRY_RUN=true
```

Esto generará archivos de preview:
- `preview-production.csv`
- `preview-scrap.csv`

### Automatización con Windows Task Scheduler

1. Abre **Programador de tareas**
2. Crea una nueva tarea básica
3. Configura la acción:
   - Programa: `python.exe`
   - Argumentos: `C:\ruta\al\proyecto\plex_downloader.py`
   - Directorio inicial: `C:\ruta\al\proyecto`
4. Configura la frecuencia (diaria recomendada)

### Despliegue en Render (Recomendado para Producción)

Para ejecutar en la nube de forma automática y sin servidor local:

1. Lee la guía completa: **[DEPLOY_RENDER.md](./DEPLOY_RENDER.md)**
2. Configura un Cron Job en Render
3. Define las variables de entorno
4. ¡Listo! Se ejecutará automáticamente

**Ventajas de Render:**
- ✅ Gratis (400 horas/mes)
- ✅ Sin servidor local 24/7
- ✅ Logs centralizados
- ✅ Notificaciones de errores
- ✅ Deploy automático desde GitHub

## 📊 Integración con Power Query

Los archivos en Google Drive están configurados para descarga directa. Usa estos links en Power Query:

### Production
```
https://drive.google.com/uc?export=download&id=1EhVdt8n6eIjJF0afLm5irDZQv2CDRi7w
```

### Scrap
```
https://drive.google.com/uc?export=download&id=1gVbCYSpTNtWE25ZHOPHzDBnkucLIaDN9
```

### Código M para Power Query (ejemplo Production)

```m
let
    Source = Csv.Document(
        Web.Contents("https://drive.google.com/uc?export=download&id=1EhVdt8n6eIjJF0afLm5irDZQv2CDRi7w"),
        [Delimiter=",", Encoding=65001, QuoteStyle=QuoteStyle.Csv]
    ),
    #"Promoted Headers" = Table.PromoteHeaders(Source, [PromoteAllScalars=true]),
    
    // Preservar Revision como texto (evita "01" → 1)
    #"Revision as Text" = Table.TransformColumns(
        #"Promoted Headers",
        {{"Revision", each Text.From(_, "en-US"), type text}}
    ),
    
    // Crear columna Part-Revision
    #"Part-Revision Merged" = Table.AddColumn(
        #"Revision as Text",
        "Part-Revision",
        each if [Revision] = "" or [Revision] = null 
             then [Part No] 
             else [Part No] & "-" & [Revision],
        type text
    )
in
    #"Part-Revision Merged"
```

## 🔍 Cómo funciona el merge por fecha

1. **Descarga**: Obtiene el archivo actual de Google Drive
2. **Análisis**: Lee todas las fechas del archivo nuevo descargado
3. **Limpieza**: 
   - Elimina BOM (U+FEFF) que causa duplicación de columnas
   - Limpia saltos de línea dentro de celdas CSV
4. **Merge**:
   - Elimina del archivo de Drive todas las filas con fechas coincidentes
   - Agrega todas las filas del archivo nuevo
   - Preserva el resto de datos históricos
5. **Normalización**: Si `NORMALIZE_DATE=true`, convierte fechas a formato ISO (YYYY-MM-DD) para comparación

### Formatos de fecha soportados

- `11/6/2025, 2:32 PM` (con timestamp y AM/PM)
- `11/6/2025` (solo fecha)
- `2025-11-06` (ISO)
- `06/11/2025` (día/mes/año)
- Y más variantes con/sin hora

## 📁 Estructura del proyecto

```
Henniges-scrap-cloud/
├── plex_downloader.py          # Script principal de automatización
├── google_drive_utils.py       # Funciones de Google Drive API
├── requirements.txt            # Dependencias Python
├── .env                        # Configuración (NO SUBIR A GIT)
├── .gitignore                  # Archivos ignorados
├── henniges-*.json             # Credenciales (NO SUBIR A GIT)
├── README.md                   # Este archivo
├── nov25.csv                   # Descarga temporal Production
├── W45Y2025.csv               # Descarga temporal Scrap
├── preview-production.csv      # Preview DRY_RUN (opcional)
├── preview-scrap.csv          # Preview DRY_RUN (opcional)
└── __pycache__/               # Cache Python
```

## 🛠️ Scripts auxiliares

### `fix_csv_linebreaks.py`
Limpia saltos de línea dentro de celdas CSV que rompen la estructura:

```powershell
python fix_csv_linebreaks.py "input.csv" "output.csv"
```

### `search_cost.py`
Busca registros específicos en archivos CSV:

```powershell
python search_cost.py "archivo.csv" "término_búsqueda"
```

### `diagnose_duplicates.py`
Diagnostica duplicados en archivos CSV:

```powershell
python diagnose_duplicates.py
```

## 🐛 Problemas conocidos y soluciones

### Production se duplica

**Causa**: Las fechas incluyen timestamp (`11/6/2025, 2:32 PM`) y no se normalizan correctamente.

**Solución**: Ya implementado el soporte para formato con hora. Asegúrate de tener `NORMALIZE_DATE=true`.

### Scrap pierde datos

**Causa**: BOM (U+FEFF) o saltos de línea dentro de celdas causan que CSV se lea mal.

**Solución**: Ya implementada limpieza automática con `_clean_csv_line_breaks()`.

### Columna "Revision" se convierte en número

**Causa**: Power Query auto-detecta tipo de dato y "01" se convierte en 1.

**Solución**: Usa `Text.From()` en Power Query (ver código M arriba).

### Upload a Drive falla con "Couldn't load user"

**Causa**: Timeout o archivo muy grande sin resumable upload.

**Solución**: Ya implementado `resumable=True` para archivos > 5MB con chunks de 1MB.

## 📝 Logging y debugging

El script usa timestamps en formato `[HH:MM:SS]` para todos los mensajes:

```
[22:49:13] Starting automated Plex download script
[Drive 22:49:42] Procesando actualización de Drive...
[Drive 22:49:44] Descargado archivo existente: 80636 filas
[Drive 22:49:49] → Archivo nuevo tiene 5205 filas con 2967 fechas únicas
[Drive 22:49:53] → Resultado merge: 39467 viejas mantenidas + 1778 nuevas = 41245 total
[Drive 22:50:02] ✓ Upload exitoso confirmado
```

## 🔐 Seguridad

⚠️ **NUNCA SUBAS A GITHUB**:
- Archivos `.json` de credenciales
- Archivo `.env` con contraseñas
- Archivos CSV con datos sensibles

El `.gitignore` ya está configurado para proteger estos archivos.

## 📞 Soporte

Para reportar problemas o solicitar características:
- GitHub Issues: https://github.com/miguelsot0b/Henniges-scrap-cloud/issues
- Contacto: miguel.soto@henniges.com

## 📜 Licencia

Uso interno Henniges Automotive únicamente.

---

**Última actualización**: Noviembre 2025  
**Versión**: 1.0.0  
**Autor**: Miguel Soto
