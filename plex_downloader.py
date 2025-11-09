from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout
import os
import time
from datetime import datetime, timedelta
from typing import Optional

# Drive sync
try:
    from google_drive_utils import update_drive_csv_file
except Exception:
    update_drive_csv_file = None  # Will log later if not available

# Load environment variables from .env if present
try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass

def get_plex_credentials():
    """Read Plex credentials from environment/.env.

    Requires PLEX_USERNAME and PLEX_PASSWORD to be set (por ejemplo, en .env local o variables de entorno del sistema).
    """
    username = os.getenv('PLEX_USERNAME')
    password = os.getenv('PLEX_PASSWORD')
    if not username or not password:
        raise RuntimeError(
            'Faltan credenciales de Plex. Define PLEX_USERNAME y PLEX_PASSWORD en .env (local) o como Environment Variables (Render).'
        )
    return username, password

def log_message(message):
    """Print a message with timestamp"""
    timestamp = datetime.now().strftime('%H:%M:%S')
    print(f"[{timestamp}] {message}")

def ensure_directory(path):
    """Create directory if it doesn't exist"""
    os.makedirs(path, exist_ok=True)

def get_production_filename():
    """Generate production filename based on current month/year"""
    current_date = datetime.now()
    month_abbr = current_date.strftime('%b').lower()
    year_short = current_date.strftime('%y')
    return f"{month_abbr}{year_short}.csv"

def get_scrap_filename():
    """Generate scrap filename based on current week/year"""
    today = datetime.now()
    week_number = today.strftime('%V')
    year = today.strftime('%Y')
    return f"W{week_number}Y{year}.csv"

def get_week_date_range():
    """Get the date range for the current week"""
    today = datetime.now()
    monday = today - timedelta(days=today.weekday())
    sunday = monday + timedelta(days=6)
    monday_str = f"{monday.month}/{monday.day}/{monday.year}"
    sunday_str = f"{sunday.month}/{sunday.day}/{sunday.year}"
    
    return f"{monday_str} - {sunday_str}"

def wait_and_click(page, selector, timeout=10000, message=None):
    """Wait for an element and click it"""
    if message:
        log_message(message)
    element = page.wait_for_selector(selector, timeout=timeout)
    if not element:
        raise PlaywrightTimeout(f"Element not found: {selector}")
    element.click()
    return element

async def export_to_csv(page, save_path):
    """Export data to CSV and save to specified path"""
    log_message("Starting CSV export...")
    
    wait_and_click(page, 'a:has(i.plex-action-export):has(span:text("Export As"))')
    
    with page.expect_download() as download_info:
        wait_and_click(page, 'a:has-text("Export to CSV")')
        download = download_info.value
        save_download(download, save_path)
        log_message("Export completed successfully")

def save_download(download, filepath):
    """Save a download to specified path, ensuring directory exists"""
    ensure_directory(os.path.dirname(filepath))
    download.save_as(filepath)
    log_message(f"File saved successfully to: {filepath}")

def download_files_from_plex():
    """Download production and scrap files from Plex"""
    log_message("=== Starting new download cycle ===")

    with sync_playwright() as p:
        # Local default: headless True is fine; no special container flags.
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(accept_downloads=True)

        try:
            # Login to Plex
            log_message("Logging into Plex...")
            page.goto('https://cloud.plex.com/')
            page.wait_for_load_state('networkidle')
            
            page.click('button#iamButton')
            
            username_input = page.locator('#inputUsername3')
            username, password = get_plex_credentials()
            username_input.fill(username)
            username_input.press('Enter')
            
            password_input = page.locator('#inputPassword3')
            password_input.fill(password)
            password_input.press('Enter')
            
            # Wait for login to complete
            page.wait_for_load_state('networkidle')

            # Download Production file
            log_message("Starting production file download...")
            page.goto('https://cloud.plex.com/ProductionTracking/ProductionHistory/ViewProductionHistoryDetailedProductionHistoryGrid')
            page.wait_for_load_state('networkidle')
            
            wait_and_click(page, '#autoID14_Anchor', message="Clicking calendar icon")
            
            # Set date range to current month
            date_select = wait_and_click(page, '#DateRangePickerRangeSelect')
            date_select.select_option(value='plex.dates.DateRange.CurrentMonth')
            log_message("Selected current month")
            
            print("Looking for OK button...")
            # Wait a moment for any animations to complete
            page.wait_for_timeout(1000)
            
            try:
                # Try multiple selectors to find the OK button
                ok_button = page.wait_for_selector('button.plex-datetimepicker-button.btn.default-action')
                if not ok_button:
                    ok_button = page.wait_for_selector('button:has-text("Ok")')
                
                if ok_button:
                    print("OK button found, attempting to click...")
                    # Try using evaluate_handle for a more direct click
                    page.evaluate('button => button.click()', ok_button)
                    print("Successfully clicked OK button")
                else:
                    print("OK button not found!")
                    raise Exception("OK button not found")
            except Exception as e:
                print(f"Error with OK button: {str(e)}")
                # Try an alternative approach using JavaScript
                try:
                    print("Trying alternative JavaScript click...")
                    page.evaluate('() => document.querySelector("button.plex-datetimepicker-button.btn.default-action").click()')
                    print("Successfully clicked OK button using JavaScript")
                except Exception as js_e:
                    print(f"JavaScript click also failed: {str(js_e)}")
                    raise
            
            # Wait for a moment to ensure the date filter is applied
            print("Waiting for date filter to apply...")
            page.wait_for_timeout(1000)
            
            print("Entering 'fg' in Part Key field...")
            try:
                part_input = page.locator('#autoID29')
                part_input.fill('fg')
                print("Successfully entered 'fg' in Part Key field")
            except Exception as e:
                print(f"Error entering Part Key: {str(e)}")
                raise
            
            # Click the Search button
            print("Clicking search button...")
            page.click('button.btn[data-bind="event: { mousedown: search }"]')
            
            # Wait for the search results to load
            print("Waiting for search results...")
            result_cell = page.wait_for_selector('td[data-col-index="0"][id="featurable_el_1"]', timeout=30000)
            if result_cell:
                print("Search results loaded successfully")
                
                # Click the Export As button
                print("Clicking Export As button...")
                export_button = page.wait_for_selector('a:has(i.plex-action-export):has(span:text("Export As"))')
                if export_button:
                    export_button.click()
                    print("Clicked Export As button")
                    
                    # Wait for and click the Export to CSV option
                    print("Waiting for Export to CSV option...")
                    csv_option = page.wait_for_selector('a:has-text("Export to CSV")')
                    if csv_option:
                        csv_option.click()
                        print("Clicked Export to CSV option")
                        
                        # Wait for the download with a 5-minute timeout
                        print("Waiting for download to start (timeout: 5 minutes)...")
                        with page.expect_download(timeout=300000) as download_info:
                            # Wait for the download to complete
                            download = download_info.value
                            
                            # Generate production filename based on current date
                            current_date = datetime.now()
                            month_abbr = current_date.strftime('%b').lower()  # Get month abbreviation (e.g., 'aug')
                            year_short = current_date.strftime('%y')  # Get 2-digit year
                            production_filename = f"{month_abbr}{year_short}.csv"
                            default_root = os.path.dirname(__file__)
                            prod_dir = os.getenv('PRODUCTION_SAVE_DIR', default_root).strip()
                            if not prod_dir:
                                prod_dir = default_root
                            ensure_directory(prod_dir)
                            target_path = os.path.join(prod_dir, production_filename)
                            
                            print(f"Download started, saving to {target_path}")
                            # Save the file, overwriting if it exists
                            download.save_as(target_path)
                            print("File saved successfully")

                            # Update Google Drive (Production)
                            try:
                                prod_file_id = os.getenv('DRIVE_PRODUCTION_FILE_ID')
                                prod_date_col = os.getenv('PRODUCTION_DATE_COLUMN', 'Date')
                                normalize_date = os.getenv('NORMALIZE_DATE', 'true').lower() == 'true'
                                dry_run = os.getenv('DRY_RUN', 'false').lower() == 'true'
                                preview_dir = os.getenv('DRY_RUN_OUTPUT_DIR', os.path.dirname(__file__)).strip()
                                if not preview_dir:
                                    preview_dir = os.path.dirname(__file__)
                                preview_path = os.path.join(preview_dir, 'preview-production.csv') if dry_run else None
                                if update_drive_csv_file and prod_file_id:
                                    log_message("Updating Production CSV on Google Drive...")
                                    update_drive_csv_file(prod_file_id, target_path, prod_date_col, normalize_date=normalize_date, dry_run=dry_run, preview_path=preview_path)
                                    log_message("Production CSV updated on Google Drive")
                                elif not update_drive_csv_file:
                                    log_message("Drive integration not available (missing dependencies)")
                                else:
                                    log_message("DRIVE_PRODUCTION_FILE_ID not set; skipping Drive update for Production")
                            except Exception as e:
                                log_message(f"Error updating Production file on Drive: {e}")

            print("Production file downloaded successfully!")

            # Start Scrap download process
            print("\nStarting Scrap download process...")
            print("Navigating to Scrap Log page...")
            try:
                page.goto('https://cloud.plex.com/Inventory/ScrapLog')
                page.wait_for_load_state('networkidle')
                print("Scrap Log page loaded")
                
                # Wait for and clear the date field
                print("Waiting for date field to be visible...")
                clear_button = page.wait_for_selector('span.plex-picker-item-remove', timeout=10000)
                if not clear_button:
                    raise Exception("Could not find the date clear button")
                    
                print("Clearing date field...")
                clear_button.click()
                print("Date field cleared successfully")

            except Exception as e:
                print(f"Error in initial scrap page setup: {str(e)}")
                raise            # Calculate and enter the date range
            try:
                print("Calculating date range...")
                today = datetime.now()
                monday = today - timedelta(days=today.weekday())  # Go back to Monday
                sunday = monday + timedelta(days=6)  # Go forward to Sunday
                
                # Format the dates manually to ensure correct format m/d/yyyy
                monday_str = f"{monday.month}/{monday.day}/{monday.year}"
                sunday_str = f"{sunday.month}/{sunday.day}/{sunday.year}"
                date_range = f"{monday_str} - {sunday_str}"
                
                week_number = monday.strftime('%U')  # Get week number
                year = monday.strftime('%Y')
                print(f"Date range calculated: {date_range}")
                
                # Wait for and enter the date range
                print("Waiting for date input field...")
                date_input = page.wait_for_selector('#autoID56', timeout=10000)
                if not date_input:
                    raise Exception("Could not find the date input field")
                
                print(f"Entering date range: {date_range}")
                date_input.fill(date_range)
                
                # Click search button
                print("Looking for search button...")
                search_button = page.wait_for_selector('button.btn[data-bind="event: { mousedown: search }"]', timeout=10000)
                if not search_button:
                    raise Exception("Could not find the search button")
                
                print("Clicking search button...")
                search_button.click()
            except Exception as e:
                print(f"Error in date range and search setup: {str(e)}")
                raise

            # Wait for results using the specific date cell
            try:
                print("Waiting for search results...")
                result_cell = page.wait_for_selector('td[data-col-index="0"][class="plex-date-text"]', timeout=30000)
                if not result_cell:
                    raise Exception("Could not find any results")
                print("Search results loaded successfully")
                page.wait_for_timeout(2000)  # Wait 2 seconds for results to stabilize
                
                # Click Export As button
                print("Looking for Export As button...")
                export_button = page.wait_for_selector('a:has(i.plex-action-export):has(span:text("Export As"))', timeout=10000)
                if not export_button:
                    raise Exception("Could not find Export As button")
                
                print("Clicking Export As button...")
                export_button.click()
                page.wait_for_timeout(2000)  # Wait 2 seconds for export menu
                
                # Click Export to CSV option and handle download
                print("Starting CSV export and download...")
                with page.expect_download() as download_info:
                    # Click the CSV option to trigger download
                    page.click('a:has-text("Export to CSV")')
                    
                    try:
                        # Wait for the download to start and complete
                        download = download_info.value
                        
                        # Calculate week number and prepare filename
                        today = datetime.now()
                        week_number = today.strftime('%V')  # ISO week number (1-53)
                        year = today.strftime('%Y')
                        scrap_filename = f"W{week_number}Y{year}.csv"
                        
                        # Ensure the Scrap directory exists
                        default_root = os.path.dirname(__file__)
                        scrap_dir = os.getenv('SCRAP_SAVE_DIR', default_root).strip()
                        if not scrap_dir:
                            scrap_dir = default_root
                        os.makedirs(scrap_dir, exist_ok=True)
                        
                        # Full path for the scrap file
                        scrap_path = os.path.join(scrap_dir, scrap_filename)
                        
                        print(f"Download complete, saving as: {scrap_filename}")
                        # Save the file, overwriting if it exists
                        download.save_as(scrap_path)
                        print(f"Scrap file saved successfully to: {scrap_path}")
                        
                        print("Scrap file download and save completed!")

                        # Update Google Drive (Scrap)
                        try:
                            scrap_file_id = os.getenv('DRIVE_SCRAP_FILE_ID')
                            scrap_date_col = os.getenv('SCRAP_DATE_COLUMN', 'Report Date')
                            normalize_date = os.getenv('NORMALIZE_DATE', 'true').lower() == 'true'
                            dry_run = os.getenv('DRY_RUN', 'false').lower() == 'true'
                            preview_dir = os.getenv('DRY_RUN_OUTPUT_DIR', os.path.dirname(__file__)).strip()
                            if not preview_dir:
                                preview_dir = os.path.dirname(__file__)
                            preview_path = os.path.join(preview_dir, 'preview-scrap.csv') if dry_run else None
                            if update_drive_csv_file and scrap_file_id:
                                log_message("Updating Scrap CSV on Google Drive...")
                                update_drive_csv_file(scrap_file_id, scrap_path, scrap_date_col, normalize_date=normalize_date, dry_run=dry_run, preview_path=preview_path)
                                log_message("Scrap CSV updated on Google Drive")
                            elif not update_drive_csv_file:
                                log_message("Drive integration not available (missing dependencies)")
                            else:
                                log_message("DRIVE_SCRAP_FILE_ID not set; skipping Drive update for Scrap")
                        except Exception as e:
                            log_message(f"Error updating Scrap file on Drive: {e}")
                    except Exception as download_error:
                        print(f"Error during download: {str(download_error)}")
                        raise
                
            except Exception as e:
                print(f"Error in scrap export process: {str(e)}")
                raise

            print("All downloads completed successfully!")

        except Exception as e:
            print(f"An error occurred: {str(e)}")
        
        finally:
            browser.close()

def main():
    """Run one cycle by default. If LOOP=true, loop with interval."""
    loop = os.getenv('LOOP', 'false').lower() == 'true'
    wait_time = int(os.getenv('WAIT_TIME', '300'))  # seconds

    def run_cycle():
        start_time = datetime.now()
        download_files_from_plex()
        elapsed = (datetime.now() - start_time).total_seconds()
        log_message(f"=== Download cycle completed in {elapsed:.1f} seconds ===")

    if not loop:
        try:
            run_cycle()
        except PlaywrightTimeout as e:
            log_message(f"!!! Timeout error: {str(e)}")
        except Exception as e:
            log_message(f"!!! Error in download cycle: {str(e)}")
        return

    while True:
        try:
            run_cycle()
        except PlaywrightTimeout as e:
            log_message(f"!!! Timeout error: {str(e)}")
        except Exception as e:
            log_message(f"!!! Error in download cycle: {str(e)}")
        log_message(f"Waiting {wait_time/60:.0f} minutes before next run...")
        time.sleep(wait_time)

if __name__ == "__main__":
    try:
        log_message("Starting automated Plex download script")
        main()
    except KeyboardInterrupt:
        log_message("=== Script stopped by user ===")
    except Exception as e:
        log_message(f"!!! Fatal error: {str(e)}")
        raise
