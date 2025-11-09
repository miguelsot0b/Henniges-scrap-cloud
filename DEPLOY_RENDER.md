# 🚀 Guía de Despliegue en Render

Esta guía te ayudará a desplegar el proyecto en Render como un Cron Job automatizado.

## 📋 Prerequisitos

1. Cuenta en [Render.com](https://render.com) (gratis)
2. Repositorio de GitHub conectado
3. Archivo JSON de credenciales de Google Cloud
4. Credenciales de Plex

## 🔧 Paso 1: Preparar credenciales de Google Cloud

Las credenciales deben convertirse a Base64 para almacenarlas como variable de entorno.

### En Windows PowerShell:

```powershell
$bytes = [IO.File]::ReadAllBytes("henniges-ea459ee8daab.json")
$base64 = [Convert]::ToBase64String($bytes)
$base64 | Set-Clipboard
Write-Host "✓ Base64 copiado al portapapeles"
```

### En Linux/Mac:

```bash
cat henniges-ea459ee8daab.json | base64 -w 0 | pbcopy
echo "✓ Base64 copiado al portapapeles"
```

**Guarda este valor**, lo necesitarás en el Paso 3.

## 🌐 Paso 2: Crear Cron Job en Render

1. Ve a [Render Dashboard](https://dashboard.render.com/)
2. Click en **"New +"** → **"Cron Job"**
3. Conecta tu repositorio de GitHub:
   - Repository: `miguelsot0b/Henniges-scrap-cloud`
   - Branch: `main`

## ⚙️ Paso 3: Configurar el Cron Job

### Build & Deploy

- **Name**: `henniges-scrap-production-sync`
- **Region**: Oregon (o el más cercano)
- **Branch**: `main`
- **Runtime**: Python 3
- **Build Command**:
  ```bash
  pip install -r requirements.txt && playwright install chromium
  ```
- **Start Command**:
  ```bash
  bash start.sh
  ```

### Schedule

Elige cuándo quieres que se ejecute:

- **Diario a las 8 AM UTC** (2 AM México): `0 8 * * *`
- **Diario a las 2 PM UTC** (8 AM México): `0 14 * * *`
- **Cada 12 horas**: `0 */12 * * *`
- **Lunes a Viernes a las 8 AM UTC**: `0 8 * * 1-5`

**Formato**: Usa [Crontab Guru](https://crontab.guru/) para ayuda.

### Plan

- **Starter** (Gratis): Suficiente para este proyecto
- Límite: 400 horas compute/mes

## 🔐 Paso 4: Variables de Entorno

En la sección **Environment** del Cron Job, agrega estas variables:

### Variables REQUERIDAS (Secret):

| Variable | Valor | Descripción |
|----------|-------|-------------|
| `PLEX_USERNAME` | `tu.usuario` | Tu usuario de Plex |
| `PLEX_PASSWORD` | `tu-contraseña` | Tu contraseña de Plex |
| `GOOGLE_CREDENTIALS_B64` | `eyJ0eXBlIjoi...` | Base64 del JSON (del Paso 1) |
| `DRIVE_PRODUCTION_FILE_ID` | `1EhVdt8n6e...` | ID del archivo Production en Drive |
| `DRIVE_SCRAP_FILE_ID` | `1gVbCYSpT...` | ID del archivo Scrap en Drive |

### Variables de configuración:

| Variable | Valor | Descripción |
|----------|-------|-------------|
| `PRODUCTION_DATE_COLUMN` | `Date` | Columna de fecha en Production |
| `SCRAP_DATE_COLUMN` | `Report Date` | Columna de fecha en Scrap |
| `NORMALIZE_DATE` | `true` | Normalizar fechas (recomendado) |
| `DRY_RUN` | `false` | Modo simulación (false para producción) |

### Variables técnicas (opcional):

| Variable | Valor | Descripción |
|----------|-------|-------------|
| `PYTHON_VERSION` | `3.13.0` | Versión de Python |
| `PLAYWRIGHT_BROWSERS_PATH` | `/opt/render/.cache/ms-playwright` | Cache de Playwright |

## 🎯 Paso 5: Deploy

1. Click en **"Create Cron Job"**
2. Render instalará las dependencias automáticamente
3. El primer build puede tardar 5-10 minutos

## 📊 Paso 6: Verificar ejecución

### Logs en tiempo real

1. Ve a tu Cron Job en el Dashboard
2. Click en **"Logs"**
3. Deberías ver:

```
=====================================
Henniges Scrap & Production Sync
=====================================

✓ Variables de entorno verificadas
✓ Credenciales de Google decodificadas

Iniciando descarga automatizada...

[08:00:15] Starting automated Plex download script
[08:00:15] === Starting new download cycle ===
[08:00:15] Logging into Plex...
...
[08:02:30] === Download cycle completed in 135.2 seconds ===

=====================================
✓ Ejecución completada exitosamente
=====================================
```

### Historial de ejecuciones

En la pestaña **"Jobs"** puedes ver:
- Todas las ejecuciones pasadas
- Duración de cada una
- Logs completos
- Errores (si los hubo)

## 🔔 Paso 7: Notificaciones (Opcional)

Render puede enviarte notificaciones por email si la ejecución falla:

1. Ve a **Settings** → **Notifications**
2. Activa **"Failed Job Run"**
3. Agrega tu email

## 🛠️ Troubleshooting

### Error: "Chromium not found"

**Solución**: Verifica que el Build Command incluya:
```bash
playwright install chromium
```

### Error: "Invalid credentials"

**Solución**: 
1. Verifica que `GOOGLE_CREDENTIALS_B64` esté completo (sin saltos de línea)
2. Prueba decodificarlo localmente:
   ```bash
   echo "$GOOGLE_CREDENTIALS_B64" | base64 -d
   ```
   Debe producir un JSON válido.

### Error: "Login failed"

**Solución**: Verifica que `PLEX_USERNAME` y `PLEX_PASSWORD` sean correctos.

### El script se ejecuta pero no actualiza Drive

**Solución**:
1. Verifica que `DRY_RUN=false`
2. Confirma que los archivos en Drive están compartidos con la Service Account
3. Revisa los logs para ver mensajes de error

### Timeout en el build

**Solución**: El primer build instala Chromium (~300MB) y puede tardar. Render tiene timeout de 30 minutos, debería ser suficiente.

## 📈 Monitoreo y Mantenimiento

### Costos

- **Starter Plan**: Gratis (400 horas/mes)
- Cada ejecución toma ~2-3 minutos
- Ejecución diaria = ~90 minutos/mes
- Bien dentro del límite gratuito ✅

### Actualizaciones

Render detecta automáticamente cambios en GitHub:

1. Haz push a la rama `main`
2. Render hace redeploy automático
3. El siguiente cron job usará la nueva versión

### Pausar/Reanudar

Para pausar temporalmente:
1. Ve a **Settings**
2. Click en **"Suspend"**
3. Para reanudar: **"Resume"**

## 🔒 Seguridad

### Mejores prácticas

✅ Usa variables de entorno (nunca hardcodees credenciales)  
✅ Marca variables sensibles como **Secret**  
✅ Rota contraseñas periódicamente  
✅ Limita permisos de Service Account en Google Cloud  
✅ Revisa logs regularmente por actividad sospechosa  

### Credenciales de Google

La Service Account debe tener **solo** estos permisos:
- Lectura/Escritura en los archivos específicos de Drive
- NO acceso a toda la organización

## 📞 Soporte

Si tienes problemas:

1. Revisa los logs en Render
2. Verifica las variables de entorno
3. Prueba localmente primero
4. Abre un issue en GitHub

---

**¿Listo para desplegar?** Sigue los pasos en orden y en 15 minutos tendrás tu automatización corriendo en la nube. 🚀
