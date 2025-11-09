#!/bin/bash
# Script de inicio para Render Cron Job

echo "====================================="
echo "Henniges Scrap & Production Sync"
echo "====================================="
echo ""

# Verificar que las variables de entorno estén configuradas
if [ -z "$PLEX_USERNAME" ]; then
    echo "ERROR: PLEX_USERNAME no está configurado"
    exit 1
fi

if [ -z "$PLEX_PASSWORD" ]; then
    echo "ERROR: PLEX_PASSWORD no está configurado"
    exit 1
fi

if [ -z "$GOOGLE_CREDENTIALS_B64" ]; then
    echo "ERROR: GOOGLE_CREDENTIALS_B64 no está configurado"
    exit 1
fi

echo "✓ Variables de entorno verificadas"
echo ""

# Decodificar credenciales de Google desde base64
echo "$GOOGLE_CREDENTIALS_B64" | base64 -d > /tmp/google-credentials.json
export GOOGLE_APPLICATION_CREDENTIALS=/tmp/google-credentials.json

echo "✓ Credenciales de Google decodificadas"
echo ""

# Ejecutar el script principal
echo "Iniciando descarga automatizada..."
echo ""

python plex_downloader.py

EXIT_CODE=$?

# Limpiar credenciales temporales
rm -f /tmp/google-credentials.json

echo ""
echo "====================================="
if [ $EXIT_CODE -eq 0 ]; then
    echo "✓ Ejecución completada exitosamente"
else
    echo "✗ Ejecución falló con código: $EXIT_CODE"
fi
echo "====================================="

exit $EXIT_CODE
