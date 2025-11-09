import csv
import io
import os
import re
from typing import List, Dict, Optional, Tuple
from collections import Counter

from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload, MediaIoBaseUpload
from datetime import datetime
import json
import base64


def _log(msg: str) -> None:
    from datetime import datetime as _dt
    ts = _dt.now().strftime('%H:%M:%S')
    print(f"[Drive {_dt.now().strftime('%H:%M:%S')}] {msg}")


def get_drive_service():
    """Create and return an authenticated Google Drive service using a Service Account.

    Supports three methods (in order):
    - GOOGLE_CREDENTIALS_JSON: full JSON content of the service account.
    - GOOGLE_CREDENTIALS_B64: same JSON, base64-encoded.
    - GOOGLE_APPLICATION_CREDENTIALS: path to the JSON key file.
    """
    scopes = ["https://www.googleapis.com/auth/drive"]

    info_json = os.getenv("GOOGLE_CREDENTIALS_JSON")
    info_b64 = os.getenv("GOOGLE_CREDENTIALS_B64")
    creds_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")

    creds = None
    if info_json:
        try:
            info = json.loads(info_json)
            creds = Credentials.from_service_account_info(info, scopes=scopes)
        except Exception as e:
            raise RuntimeError(f"GOOGLE_CREDENTIALS_JSON inválido: {e}")
    elif info_b64:
        try:
            decoded = base64.b64decode(info_b64)
            info = json.loads(decoded)
            creds = Credentials.from_service_account_info(info, scopes=scopes)
        except Exception as e:
            raise RuntimeError(f"GOOGLE_CREDENTIALS_B64 inválido: {e}")
    else:
        if not creds_path or not os.path.isfile(creds_path):
            raise RuntimeError(
                "Configura GOOGLE_CREDENTIALS_JSON (o GOOGLE_CREDENTIALS_B64) o un archivo en GOOGLE_APPLICATION_CREDENTIALS"
            )
        creds = Credentials.from_service_account_file(creds_path, scopes=scopes)

    service = build("drive", "v3", credentials=creds)
    return service


def download_csv_text(file_id: str) -> str:
    """Download a Drive file by ID or share URL and return its content as UTF-8 text."""
    service = get_drive_service()
    file_id = _normalize_file_id(file_id)
    request = service.files().get_media(fileId=file_id)
    fh = io.BytesIO()
    downloader = MediaIoBaseDownload(fd=fh, request=request)
    done = False
    while not done:
        status, done = downloader.next_chunk()
    fh.seek(0)
    return fh.read().decode("utf-8", errors="replace")


def upload_csv_text(file_id: str, text: str) -> None:
    """Overwrite an existing Drive file (by ID or share URL) with provided CSV text."""
    service = get_drive_service()
    file_id = _normalize_file_id(file_id)
    
    # Usar resumable=True para archivos grandes (más confiable)
    file_bytes = text.encode("utf-8")
    file_size_mb = len(file_bytes) / (1024 * 1024)
    
    # Si el archivo es mayor a 5MB, usar resumable upload
    use_resumable = file_size_mb > 5
    
    media = MediaIoBaseUpload(
        io.BytesIO(file_bytes), 
        mimetype="text/csv", 
        resumable=use_resumable,
        chunksize=1024*1024  # 1MB chunks
    )
    
    result = service.files().update(
        fileId=file_id, 
        media_body=media, 
        body={"mimeType": "text/csv"}
    ).execute()
    
    # Verificar que el upload fue exitoso
    if not result or 'id' not in result:
        raise RuntimeError(f"Upload falló: respuesta inválida de Drive API")
    
    return result


def _try_parse_date(val: str) -> Optional[datetime]:
    """Try parsing a date from a variety of common formats. Return datetime or None."""
    if val is None:
        return None
    val = val.strip()
    if not val:
        return None
    formats = [
        "%m/%d/%Y, %I:%M %p",  # 11/6/2025, 2:32 PM (formato con coma y AM/PM)
        "%m/%d/%Y %I:%M %p",   # 11/6/2025 2:32 PM (sin coma)
        "%m/%d/%Y, %H:%M",     # 11/6/2025, 14:32 (formato 24h con coma)
        "%m/%d/%Y",
        "%m/%d/%y",
        "%Y-%m-%d",
        "%Y/%m/%d",
        "%d/%m/%Y",
        "%d-%m-%Y",
        "%m/%d/%Y %H:%M",
        "%m/%d/%Y %H:%M:%S",
        "%Y-%m-%d %H:%M:%S",
    ]
    for fmt in formats:
        try:
            return datetime.strptime(val, fmt)
        except Exception:
            continue
    return None


def _normalize_date_for_key(val: str, normalize: bool) -> str:
    """Return a key for date comparison. If normalize=True, convert to ISO date (YYYY-MM-DD)."""
    if not normalize:
        return (val or "").strip()
    dt = _try_parse_date(val)
    if dt is None:
        # Fallback to raw string if parsing failed
        return (val or "").strip()
    return dt.date().isoformat()


def _clean_csv_line_breaks(csv_text: str) -> str:
    """Clean line breaks within CSV cell values that break row structure.
    
    This handles cases where cell values contain \n or \r characters that
    would normally break CSV parsing by creating extra rows.
    """
    # Pattern mejorado: captura campos entre comillas que contienen cualquier cantidad de saltos de línea
    # Usa un patrón más robusto que captura TODO el contenido entre comillas, incluyendo múltiples saltos
    pattern = r'"([^"]*(?:[\n\r]+[^"]*)*)"'
    
    def replace_breaks(match):
        # Replace \n and \r with space within the quoted field
        value = match.group(1)
        # Reemplazar todos los saltos de línea con espacios
        value = value.replace('\n', ' ').replace('\r', ' ')
        # Limpiar espacios múltiples
        value = ' '.join(value.split())
        return f'"{value}"'
    
    cleaned = re.sub(pattern, replace_breaks, csv_text)
    
    # Log de cuántos campos fueron limpiados (solo si hubo cambios)
    if cleaned != csv_text:
        original_lines = csv_text.count('\n')
        cleaned_lines = cleaned.count('\n')
        if original_lines != cleaned_lines:
            _log(f"   Line breaks limpiados: {original_lines} → {cleaned_lines} líneas")
    
    return cleaned


def _read_csv_to_rows(csv_text: str) -> Tuple[List[str], List[Dict[str, str]]]:
    """Read CSV text into (fieldnames, rows). Removes BOM if present and cleans line breaks."""
    original_line_count = csv_text.count('\n')
    
    # Remove BOM if present at the start of the text
    if csv_text.startswith('\ufeff'):
        csv_text = csv_text[1:]
    
    # Clean line breaks within cell values
    csv_text = _clean_csv_line_breaks(csv_text)
    cleaned_line_count = csv_text.count('\n')
    
    if original_line_count != cleaned_line_count:
        _log(f"   Limpieza CSV: {original_line_count} → {cleaned_line_count} líneas")
    
    buf = io.StringIO(csv_text)
    reader = csv.DictReader(buf)
    fieldnames = reader.fieldnames or []
    
    # Clean BOM from fieldnames if present
    if fieldnames and fieldnames[0].startswith('\ufeff'):
        fieldnames[0] = fieldnames[0][1:]
    
    rows = [dict(r) for r in reader]
    
    if len(rows) != (cleaned_line_count - 1):  # -1 for header
        _log(f"   ⚠️ Advertencia: Se esperaban {cleaned_line_count - 1} filas pero se leyeron {len(rows)}")
    
    return fieldnames, rows


def _read_csv_file_to_rows(csv_path: str) -> Tuple[List[str], List[Dict[str, str]]]:
    """Read CSV file into (fieldnames, rows). Cleans line breaks within cell values."""
    with open(csv_path, "r", encoding="utf-8-sig", newline="") as f:
        csv_text = f.read()
    
    original_line_count = csv_text.count('\n')
    _log(f"   Archivo local: {original_line_count} líneas en archivo")
    
    # Clean line breaks within cell values
    csv_text = _clean_csv_line_breaks(csv_text)
    cleaned_line_count = csv_text.count('\n')
    
    if original_line_count != cleaned_line_count:
        _log(f"   Limpieza aplicada: {original_line_count} → {cleaned_line_count} líneas")
    
    buf = io.StringIO(csv_text)
    reader = csv.DictReader(buf)
    fieldnames = reader.fieldnames or []
    rows = [dict(r) for r in reader]
    
    if len(rows) != (cleaned_line_count - 1):  # -1 for header
        _log(f"   ⚠️ Advertencia: Se esperaban {cleaned_line_count - 1} filas pero se leyeron {len(rows)}")
    
    return fieldnames, rows


def _write_rows_to_csv_text(fieldnames: List[str], rows: List[Dict[str, str]]) -> str:
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=fieldnames, lineterminator='\n')
    writer.writeheader()
    for r in rows:
        writer.writerow({k: r.get(k, "") for k in fieldnames})
    return buf.getvalue()


def merge_csv_by_date(existing_csv_text: str,
                      new_csv_path: str,
                      date_column: str,
                      normalize_date: bool = True,
                      preserve_order: bool = True) -> str:
    """Merge two CSVs replacing all rows for matching dates with rows from new CSV.

    - existing_csv_text: current CSV content from Drive
    - new_csv_path: local path to newly downloaded CSV
    - date_column: column name that carries the date
    - normalize_date: if True, attempt to parse and compare by date-only (YYYY-MM-DD)
    - preserve_order: if True, keep original order for non-replaced rows; appended new rows go at the end

    Returns merged CSV as text.
    """
    # Read both datasets
    old_fields, old_rows = _read_csv_to_rows(existing_csv_text)
    new_fields, new_rows = _read_csv_file_to_rows(new_csv_path)
    
    _log(f"DEBUG: Archivo local leído - {len(new_rows)} filas totales")

    if not old_fields:
        # If Drive file is empty or missing header, just adopt new CSV structure fully
        fieldnames = new_fields
        return _write_rows_to_csv_text(fieldnames, new_rows)

    # Build unified header
    field_set = list(dict.fromkeys([*old_fields, *new_fields]))  # ordered union
    
    # Check for potential column mismatches
    if len(field_set) != len(old_fields) and len(old_fields) == len(new_fields):
        _log(f"⚠ Advertencia: Diferencia en nombres de columnas detectada")
        diff_old = set(old_fields) - set(new_fields)
        diff_new = set(new_fields) - set(old_fields)
        if diff_old:
            _log(f"  Columnas solo en archivo viejo: {', '.join(list(diff_old)[:3])}")
        if diff_new:
            _log(f"  Columnas solo en archivo nuevo: {', '.join(list(diff_new)[:3])}")

    # Calculate date keys to replace
    new_date_keys = set(_normalize_date_for_key(r.get(date_column, ""), normalize_date) for r in new_rows)
    
    # Validar que la columna de fecha existe y tiene valores
    if not date_column:
        raise ValueError("date_column está vacío!")
    
    # Verificar que al menos algunas filas tienen la columna de fecha
    rows_with_date = sum(1 for r in new_rows if r.get(date_column, "").strip())
    if rows_with_date == 0:
        _log(f"⚠️ ADVERTENCIA CRÍTICA: Ninguna fila tiene la columna '{date_column}'!")
        _log(f"   Columnas disponibles: {', '.join(list(new_rows[0].keys())[:5]) if new_rows else 'N/A'}")
    else:
        _log(f"   Columna '{date_column}': {rows_with_date}/{len(new_rows)} filas con valor")
    
    # Count rows per date in new file
    new_date_counts = Counter(_normalize_date_for_key(r.get(date_column, ""), normalize_date) for r in new_rows)
    
    # Debug: Show sample dates from new file
    sample_new_dates = list(new_date_keys)[:3]
    _log(f"→ Archivo nuevo tiene {len(new_rows)} filas con {len(new_date_keys)} fechas únicas")
    if sample_new_dates:
        _log(f"   Ejemplos de fechas nuevas: {', '.join(sample_new_dates)}")

    # Filter out old rows whose date is in new set and track what's being replaced
    kept_old_rows: List[Dict[str, str]] = []
    removed_rows_by_date = Counter()
    old_date_keys = set()
    
    for r in old_rows:
        key = _normalize_date_for_key(r.get(date_column, ""), normalize_date)
        old_date_keys.add(key)
        if key not in new_date_keys:
            kept_old_rows.append(r)
        else:
            removed_rows_by_date[key] += 1
    
    # Debug: Show sample dates from old file
    sample_old_dates = list(old_date_keys)[:3]
    _log(f"→ Archivo viejo tiene {len(old_rows)} filas con {len(old_date_keys)} fechas únicas")
    if sample_old_dates:
        _log(f"   Ejemplos de fechas viejas: {', '.join(sample_old_dates)}")
    
    # Summary logging
    if removed_rows_by_date:
        _log(f"→ Reemplazando {len(removed_rows_by_date)} fechas ({sum(removed_rows_by_date.values())} → {len(new_rows)} filas)")
    else:
        _log(f"→ Agregando {len(new_rows)} filas nuevas (sin fechas coincidentes)")

    # Combine
    if preserve_order:
        merged_rows = kept_old_rows + new_rows
    else:
        # Optionally sort by date after combining (not default)
        merged_rows = kept_old_rows + new_rows
    
    _log(f"→ Resultado merge: {len(kept_old_rows)} viejas mantenidas + {len(new_rows)} nuevas = {len(merged_rows)} total")
    
    return _write_rows_to_csv_text(field_set, merged_rows)


def update_drive_csv_file(file_id: str,
                          new_csv_path: str,
                          date_column: str,
                          normalize_date: bool = True,
                          dry_run: bool = False,
                          preview_path: Optional[str] = None) -> None:
    """Download, merge by date and upload CSV back to Drive.

    If dry_run=True, don't upload; optionally write merged preview to preview_path and log summary.
    """
    _log(f"Procesando actualización de Drive...")
    file_id = _normalize_file_id(file_id)
    
    existing_text = ""
    old_fields: List[str] = []
    old_rows: List[Dict[str, str]] = []
    try:
        existing_text = download_csv_text(file_id)
        old_fields, old_rows = _read_csv_to_rows(existing_text)
        _log(f"Descargado archivo existente: {len(old_rows)} filas")
    except Exception as e:
        _log(f"No se pudo descargar archivo existente: {e}")

    # Read new data for info
    new_fields, new_rows = _read_csv_file_to_rows(new_csv_path)
    _log(f"Archivo nuevo: {len(new_rows)} filas")
    
    # Build new date keys set for summary
    new_date_keys = set(_normalize_date_for_key(r.get(date_column, ""), normalize_date) for r in new_rows)
    
    removed_count = 0
    if old_rows:
        for r in old_rows:
            key = _normalize_date_for_key(r.get(date_column, ""), normalize_date)
            if key in new_date_keys:
                removed_count += 1
    
    merged_text = merge_csv_by_date(existing_text, new_csv_path, date_column, normalize_date=normalize_date)

    if dry_run:
        _log(f"DRY_RUN: {len(new_date_keys)} fechas, {removed_count} filas reemplazadas, {len(new_rows)} filas nuevas")
        if preview_path:
            try:
                os.makedirs(os.path.dirname(preview_path) or '.', exist_ok=True)
                with open(preview_path, 'w', encoding='utf-8', newline='') as f:
                    f.write(merged_text)
                _log(f"Preview guardado: {preview_path}")
            except Exception as e:
                _log(f"Error al escribir preview: {e}")
        return

        
    _log("Subiendo archivo combinado a Drive...")
    
    # Verificar tamaño del archivo antes de subir
    file_size_mb = len(merged_text.encode('utf-8')) / (1024 * 1024)
    _log(f"   Tamaño del archivo: {file_size_mb:.2f} MB")
    
    # Contar filas finales
    final_rows = merged_text.count('\n') - 1  # -1 for header
    _log(f"   Filas finales en merge: {final_rows}")
    
    try:
        upload_csv_text(file_id, merged_text)
        _log(f"✓ Actualización completada: {len(new_date_keys)} fechas, {removed_count} filas actualizadas")
        _log(f"✓ Upload exitoso confirmado")
    except Exception as e:
        _log(f"✗ Error al subir a Drive: {e}")
        _log(f"✗ Tipo de error: {type(e).__name__}")
        import traceback
        _log(f"✗ Traceback: {traceback.format_exc()}")
        raise


def _normalize_file_id(file_id_or_url: str) -> str:
    """Accepts a plain Drive file ID or a full share URL and returns the file ID.

    Supported URL forms:
    - https://drive.google.com/file/d/<ID>/view?...
    - https://drive.google.com/open?id=<ID>
    - https://drive.google.com/uc?id=<ID>&export=download
    """
    val = (file_id_or_url or "").strip()
    if not val:
        return val
    if "/file/d/" in val:
        # extract between /d/ and next /
        try:
            start = val.index("/file/d/") + len("/file/d/")
            rest = val[start:]
            end = rest.index("/")
            return rest[:end]
        except Exception:
            return val
    if "id=" in val:
        try:
            # naive parse, split by id= and then by &
            part = val.split("id=", 1)[1]
            return part.split("&", 1)[0]
        except Exception:
            return val
    return val
