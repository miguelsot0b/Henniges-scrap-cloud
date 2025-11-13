from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout
import os
from datetime import datetime

# Drive sync
try:
    from google_drive_utils import update_drive_csv_file
except Exception:
    update_drive_csv_file = None

# Load environment variables
try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass

def log(msg):
    """Print timestamped message"""
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}")

def get_credentials():
    """Get Plex credentials from environment"""
    username = os.getenv('PLEX_USERNAME')
    password = os.getenv('PLEX_PASSWORD')
    if not username or not password:
        raise RuntimeError('Missing PLEX_USERNAME or PLEX_PASSWORD')
    return username, password

def click_ok_button(page):
    """Click OK button in date picker"""
    page.wait_for_timeout(500)
    page.evaluate('document.querySelector("button.plex-datetimepicker-button.btn.default-action").click()')

def export_csv(page, filepath):
    """Export and save CSV file"""
    page.click('a:has(i.plex-action-export):has(span:text("Export As"))')
    with page.expect_download(timeout=180000) as download_info:
        page.click('a:has-text("Export to CSV")')
        download = download_info.value
        os.makedirs(os.path.dirname(filepath) or '.', exist_ok=True)
        download.save_as(filepath)
    log(f"Saved: {filepath}")

def update_drive(file_id, local_path, date_column):
    """Update Google Drive file if configured"""
    if not update_drive_csv_file or not file_id:
        return
    try:
        normalize = os.getenv('NORMALIZE_DATE', 'true').lower() == 'true'
        update_drive_csv_file(file_id, local_path, date_column, normalize_date=normalize)
        log(f"Drive updated: {file_id}")
    except Exception as e:
        log(f"Drive update failed: {e}")

def download_production(page, save_dir):
    """Download production report (Last 7 Days, Part Key = 'fg')"""
    log("Downloading production report...")
    
    page.goto('https://cloud.plex.com/ProductionTracking/ProductionHistory/ViewProductionHistoryDetailedProductionHistoryGrid')
    page.wait_for_load_state('networkidle')
    
    # Set date range
    page.click('#autoID14_Anchor')
    page.select_option('#DateRangePickerRangeSelect', value='plex.dates.DateRange.LastSevenDays')
    click_ok_button(page)
    page.wait_for_timeout(500)
    
    # Filter and search
    page.fill('#autoID29', 'fg')
    page.click('button.btn[data-bind="event: { mousedown: search }"]')
    page.wait_for_selector('td[data-col-index="0"][id="featurable_el_1"]', timeout=30000)
    
    # Export
    filepath = os.path.join(save_dir, 'production.csv')
    export_csv(page, filepath)
    
    # Update Drive
    update_drive(
        os.getenv('DRIVE_PRODUCTION_FILE_ID'),
        filepath,
        os.getenv('PRODUCTION_DATE_COLUMN', 'Date')
    )

def download_scrap(page, save_dir):
    """Download scrap report (Last 7 Days)"""
    log("Downloading scrap report...")
    
    page.goto('https://cloud.plex.com/Inventory/ScrapLog')
    page.wait_for_load_state('networkidle')
    
    # Set date range
    page.click('#autoID56_Anchor')
    page.select_option('#DateRangePickerRangeSelect', value='plex.dates.DateRange.LastSevenDays')
    click_ok_button(page)
    page.wait_for_timeout(500)
    
    # Search
    page.click('button.btn[data-bind="event: { mousedown: search }"]')
    page.wait_for_selector('td[data-col-index="0"][class="plex-date-text"]', timeout=30000)
    page.wait_for_timeout(1000)
    
    # Export
    filepath = os.path.join(save_dir, 'scrap.csv')
    export_csv(page, filepath)
    
    # Update Drive
    update_drive(
        os.getenv('DRIVE_SCRAP_FILE_ID'),
        filepath,
        os.getenv('SCRAP_DATE_COLUMN', 'Report Date')
    )

def main():
    """Main execution"""
    start = datetime.now()
    log("Starting Plex download...")
    
    username, password = get_credentials()
    save_dir = os.getenv('PRODUCTION_SAVE_DIR') or os.getenv('SCRAP_SAVE_DIR') or os.path.dirname(__file__) or '.'
    
    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=os.getenv('HEADLESS', 'true').lower() == 'true'
        )
        page = browser.new_page(accept_downloads=True)
        
        try:
            # Login
            log("Logging in...")
            page.goto('https://cloud.plex.com/')
            page.wait_for_load_state('networkidle')
            page.click('button#iamButton')
            
            page.fill('#inputUsername3', username)
            page.press('#inputUsername3', 'Enter')
            
            page.fill('#inputPassword3', password)
            page.press('#inputPassword3', 'Enter')
            page.wait_for_load_state('networkidle')
            
            # Download reports
            download_production(page, save_dir)
            download_scrap(page, save_dir)
            
            elapsed = (datetime.now() - start).total_seconds()
            log(f"Completed in {elapsed:.1f}s")
            
        except Exception as e:
            log(f"Error: {e}")
            raise
        finally:
            browser.close()

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        log("Stopped by user")
    except Exception as e:
        log(f"Fatal error: {e}")
        raise
