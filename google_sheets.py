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
        bot_name = get_bot_context() or CURRENT_BOT_NAME
    
    config = get_bot_config(bot_name)
    gsheet_id = config['GSHEET_ID']
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
        headers = [h.strip() for h in data[0]]
        courses = []
        for row in data[1:]:
            if not row or (len(row) > 0 and row[0].strip() == ""):
                continue
            d = {headers[i]: (row[i] if i < len(row) else "") for i in range(len(headers))}
            course_id = str(d.get("id") or d.get("ID") or d.get("Id") or "").strip()
            if not course_id:
                continue
            name = (d.get("name") or d.get("Name") or d.get("Название") or "").strip()
            desc = (d.get("description") or d.get("Description") or d.get("Описание") or "").strip()
            price = d.get("price") or d.get("Price") or d.get("Цена") or "0"
            duration = d.get("duration_days") or d.get("Duration") or d.get("Срок") or d.get("duration_minutes") or ""
            image = (d.get("image_url") or d.get("Image") or d.get("Картинка") or "").strip()
            channel = (d.get("channel") or d.get("Channel") or d.get("Канал") or "").strip()
            # Parse is_active from column H (index 7) or by name
            is_active_raw = d.get("is_active") or d.get("Is Active") or d.get("isActive") or d.get("Активен") or d.get("active") or "1"
            try:
                price = float(str(price).replace(",", ".") if price else 0)
            except (ValueError, TypeError):
                price = 0.0
            # Если duration пустой или 0, то None (бессрочный доступ)
            duration = parse_duration(duration)
            # Parse is_active: 1/True/"1"/"true" = active, 0/False/"0"/"false"/empty = inactive
            if isinstance(is_active_raw, bool):
                is_active = 1 if is_active_raw else 0
            elif isinstance(is_active_raw, (int, float)):
                is_active = 1 if int(is_active_raw) == 1 else 0
            else:
                is_active_str = str(is_active_raw).strip().lower()
                is_active = 1 if is_active_str in ("1", "true", "yes", "да", "y") else 0
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
        bot_name = get_bot_context() or CURRENT_BOT_NAME
    
    config = get_bot_config(bot_name)
    gsheet_id = config['GSHEET_ID']
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
        ws = sheet.worksheet(texts_name)
        data = ws.get_all_values()
        texts = {}
        for row in data:
            if len(row) >= 2 and row[0]:
                texts[row[0]] = row[1]
        return texts
    else:
        data = fetch_sheet_csv(texts_name, gsheet_id)
        texts = {}
        if not data or len(data) < 2:
            return texts
        # Assume header row present
        # But also handle case with no header
        start_idx = 1
        # If header doesn't look like keys, fallback to no-header
        if len(data[0]) < 2 or data[0][0].lower() not in ("key", "ключ"):
            start_idx = 0
        for row in data[start_idx:]:
            if len(row) >= 2 and row[0]:
                key = row[0].strip()
                value = row[1].strip()
                texts[key] = value
        return texts
