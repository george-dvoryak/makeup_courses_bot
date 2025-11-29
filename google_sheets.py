# google_sheets.py
import csv
import requests

from config import GSHEET_ID, GSHEET_COURSES_NAME, GSHEET_TEXTS_NAME, GOOGLE_SHEETS_USE_API, GOOGLE_CREDENTIALS_FILE, get_bot_config, CURRENT_BOT_NAME

def fetch_sheet_csv(sheet_name: str, gsheet_id: str = None):
    """
    Fetch CSV data from Google Sheets.
    If gsheet_id is not provided, uses current bot's GSHEET_ID.
    """
    if gsheet_id is None:
        gsheet_id = GSHEET_ID
    url = f"https://docs.google.com/spreadsheets/d/{gsheet_id}/gviz/tq?tqx=out:csv&sheet={sheet_name}"
    resp = requests.get(url, timeout=15)
    resp.raise_for_status()
    content = resp.content.decode('utf-8')
    data = list(csv.reader(content.splitlines()))
    return data

def parse_duration(value):
    """
    Parse duration value. Returns None if empty/0 (unlimited), otherwise returns int (days).
    """
    if not value or str(value).strip() == "" or str(value).strip() == "0":
        return None  # Unlimited access
    try:
        duration = int(float(value))
        return None if duration == 0 else duration
    except (ValueError, TypeError):
        return None  # Unlimited access if can't parse

def get_courses_data(bot_name: str = None):
    """
    Get courses data from Google Sheets.
    If bot_name is provided, uses configuration for that bot.
    Otherwise, tries to get bot_name from context, or uses current bot configuration.
    """
    if bot_name is None:
        from bot_context import get_bot_context
        context_bot = get_bot_context()
        bot_name = context_bot or CURRENT_BOT_NAME
        print(f"[GSheets] get_courses_data: context={context_bot}, using bot={bot_name}")
    
    config = get_bot_config(bot_name)
    gsheet_id = config['GSHEET_ID']
    print(f"[GSheets] Using GSHEET_ID: {gsheet_id}")
    courses_name = config['GSHEET_COURSES_NAME']
    texts_name = config['GSHEET_TEXTS_NAME']
    use_api = config['GOOGLE_SHEETS_USE_API']
    credentials_file = config['GOOGLE_CREDENTIALS_FILE']
    
    if use_api:
        try:
            import gspread
            from oauth2client.service_account import ServiceAccountCredentials
        except ImportError:
            raise RuntimeError("gspread/oauth2client not installed. Set GOOGLE_SHEETS_USE_API=False or install libs.")
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive.readonly"]
        creds = ServiceAccountCredentials.from_json_keyfile_name(credentials_file, scope)
        client = gspread.authorize(creds)
        sheet = client.open_by_key(gsheet_id)
        ws = sheet.worksheet(courses_name)
        records = ws.get_all_records()
        courses = []
        for rec in records:
            course = {
                "id": str(rec.get("id") or rec.get("ID") or rec.get("Id") or "").strip(),
                "name": (rec.get("name") or rec.get("Name") or rec.get("Название") or "").strip(),
                "description": (rec.get("description") or rec.get("Description") or rec.get("Описание") or "").strip(),
                "price": float(rec.get("price") or rec.get("Price") or rec.get("Цена") or 0),
                "duration_days": parse_duration(rec.get("duration_days") or rec.get("Duration") or rec.get("Срок") or rec.get("duration_minutes")),
                "image_url": (rec.get("image_url") or rec.get("Image") or rec.get("Картинка") or "").strip(),
                "channel": (rec.get("channel") or rec.get("Channel") or rec.get("Канал") or "").strip(),
            }
            # Parse is_active: 1/True/"1"/"true" = active, 0/False/"0"/"false"/empty = inactive
            is_active_raw = rec.get("is_active") or rec.get("Is Active") or rec.get("isActive") or rec.get("Активен") or rec.get("active") or "1"
            if isinstance(is_active_raw, bool):
                course["is_active"] = 1 if is_active_raw else 0
            elif isinstance(is_active_raw, (int, float)):
                course["is_active"] = 1 if int(is_active_raw) == 1 else 0
            else:
                is_active_str = str(is_active_raw).strip().lower()
                course["is_active"] = 1 if is_active_str in ("1", "true", "yes", "да", "y") else 0
            
            if course["id"]:
                courses.append(course)
        return courses
    else:
        data = fetch_sheet_csv(courses_name, gsheet_id)
        if len(data) < 2:
            return []
        headers = [h.strip().lower() for h in data[0]]  # Normalize headers to lowercase
        print(f"[GSheets] Loaded {len(data)} rows (including header)")
        print(f"[GSheets] Headers: {headers}")
        courses = []
        for row in data[1:]:
            # Skip completely empty rows
            if not row:
                continue
            # Check if row is effectively empty (all cells empty or whitespace)
            if all(not cell or not str(cell).strip() for cell in row):
                continue
            
            # Build dict from row data
            d = {}
            for i, header in enumerate(headers):
                d[header] = row[i].strip() if i < len(row) else ""
            
            # Get course_id - must be non-empty to be valid
            course_id = str(d.get("id", "") or "").strip()
            if not course_id:
                continue
            
            # Get name - if empty, skip this row (invalid course)
            name = (d.get("name", "") or d.get("название", "") or "").strip()
            if not name:
                continue
            
            desc = (d.get("description", "") or d.get("описание", "") or "").strip()
            price_str = d.get("price", "") or d.get("цена", "") or "0"
            duration_str = d.get("duration_days", "") or d.get("duration", "") or d.get("срок", "") or d.get("duration_minutes", "") or ""
            image = (d.get("image_url", "") or d.get("image", "") or d.get("картинка", "") or "").strip()
            channel = (d.get("channel", "") or d.get("канал", "") or "").strip()
            is_active_raw = d.get("is_active", "") or d.get("isactive", "") or d.get("активен", "") or d.get("active", "") or "1"
            
            # Parse price
            try:
                price = float(str(price_str).replace(",", ".").strip() if price_str else 0)
            except (ValueError, TypeError):
                price = 0.0
            
            # Parse duration (None = unlimited)
            duration = parse_duration(duration_str)
            
            # Parse is_active
            if isinstance(is_active_raw, bool):
                is_active = 1 if is_active_raw else 0
            elif isinstance(is_active_raw, (int, float)):
                is_active = 1 if int(is_active_raw) == 1 else 0
            else:
                is_active_str = str(is_active_raw).strip().lower()
                is_active = 1 if is_active_str in ("1", "true", "yes", "да", "y", "") else 0
            
            courses.append({
                "id": course_id,
                "name": name,
                "description": desc,
                "price": price,
                "duration_days": duration,
                "image_url": image,
                "channel": channel,
                "is_active": is_active
            })
        return courses

def get_texts_data(bot_name: str = None):
    """
    Get texts data from Google Sheets.
    If bot_name is provided, uses configuration for that bot.
    Otherwise, tries to get bot_name from context, or uses current bot configuration.
    """
    if bot_name is None:
        from bot_context import get_bot_context
        context_bot = get_bot_context()
        bot_name = context_bot or CURRENT_BOT_NAME
        print(f"[GSheets] get_texts_data: context={context_bot}, using bot={bot_name}")
    
    config = get_bot_config(bot_name)
    gsheet_id = config['GSHEET_ID']
    texts_name = config['GSHEET_TEXTS_NAME']
    use_api = config['GOOGLE_SHEETS_USE_API']
    credentials_file = config['GOOGLE_CREDENTIALS_FILE']
    
    print(f"[GSheets] Loading texts from sheet '{texts_name}' (GSHEET_ID: {gsheet_id})")
    
    if use_api:
        try:
            import gspread
            from oauth2client.service_account import ServiceAccountCredentials
        except ImportError:
            raise RuntimeError("gspread/oauth2client not installed. Set GOOGLE_SHEETS_USE_API=False or install libs.")
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive.readonly"]
        creds = ServiceAccountCredentials.from_json_keyfile_name(credentials_file, scope)
        client = gspread.authorize(creds)
        sheet = client.open_by_key(gsheet_id)
        ws = sheet.worksheet(texts_name)
        data = ws.get_all_values()
        texts = {}
        for row in data:
            # Skip completely empty rows
            if not row:
                continue
            # Check if row is effectively empty (all cells empty or whitespace)
            if all(not cell or not str(cell).strip() for cell in row):
                continue
            if len(row) >= 2 and row[0]:
                key = str(row[0]).strip()
                value = str(row[1]).strip() if len(row) > 1 and row[1] else ""
                if key:
                    texts[key] = value
        print(f"[GSheets] Loaded {len(texts)} text entries via API")
        return texts
    else:
        data = fetch_sheet_csv(texts_name, gsheet_id)
        texts = {}
        if not data or len(data) < 1:
            print(f"[GSheets] No data found in CSV for sheet '{texts_name}'")
            return texts
        
        print(f"[GSheets] Loaded {len(data)} rows from CSV (including header if present)")
        
        # Determine if first row is header
        start_idx = 0
        if len(data) > 0 and len(data[0]) >= 2:
            first_cell = str(data[0][0]).strip().lower() if data[0][0] else ""
            # Check if first row looks like a header
            if first_cell in ("key", "ключ", "name", "название", "text_key", "ключ_текста"):
                print(f"[GSheets] Detected header row, skipping: {data[0]}")
                start_idx = 1
        
        loaded_count = 0
        for idx, row in enumerate(data[start_idx:], start=start_idx):
            # Skip completely empty rows
            if not row:
                continue
            # Check if row is effectively empty (all cells empty or whitespace)
            if all(not cell or not str(cell).strip() for cell in row):
                continue
            
            # Ensure we have at least 2 columns
            if len(row) < 2:
                print(f"[GSheets] Row {idx+1} has less than 2 columns, skipping: {row}")
                continue
            
            key = str(row[0]).strip() if row[0] else ""
            value = str(row[1]).strip() if len(row) > 1 and row[1] else ""
            
            # Only add if key is not empty
            if key:
                texts[key] = value
                loaded_count += 1
            else:
                print(f"[GSheets] Row {idx+1} has empty key, skipping: {row}")
        
        print(f"[GSheets] Successfully loaded {loaded_count} text entries from CSV")
        if loaded_count > 0:
            print(f"[GSheets] Sample keys: {list(texts.keys())[:5]}")
        return texts
