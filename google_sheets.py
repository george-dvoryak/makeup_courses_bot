# google_sheets.py
import csv
import requests

from config import GSHEET_ID, GSHEET_COURSES_NAME, GSHEET_TEXTS_NAME, GOOGLE_SHEETS_USE_API, GOOGLE_CREDENTIALS_FILE

def fetch_sheet_csv(sheet_name: str):
    url = f"https://docs.google.com/spreadsheets/d/{GSHEET_ID}/gviz/tq?tqx=out:csv&sheet={sheet_name}"
    resp = requests.get(url, timeout=15)
    resp.raise_for_status()
    content = resp.content.decode('utf-8')
    data = list(csv.reader(content.splitlines()))
    return data

def get_courses_data():
    if GOOGLE_SHEETS_USE_API:
        try:
            import gspread
            from oauth2client.service_account import ServiceAccountCredentials
        except ImportError:
            raise RuntimeError("gspread/oauth2client not installed. Set GOOGLE_SHEETS_USE_API=False or install libs.")
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive.readonly"]
        creds = ServiceAccountCredentials.from_json_keyfile_name(GOOGLE_CREDENTIALS_FILE, scope)
        client = gspread.authorize(creds)
        sheet = client.open_by_key(GSHEET_ID)
        ws = sheet.worksheet(GSHEET_COURSES_NAME)
        records = ws.get_all_records()
        courses = []
        for rec in records:
            course = {
                "id": str(rec.get("id") or rec.get("ID") or rec.get("Id") or "").strip(),
                "name": (rec.get("name") or rec.get("Name") or rec.get("Название") or "").strip(),
                "description": (rec.get("description") or rec.get("Description") or rec.get("Описание") or "").strip(),
                "price": float(rec.get("price") or rec.get("Price") or rec.get("Цена") or 0),
                "duration_minutes": int(float(rec.get("duration_minutes") or rec.get("Duration") or rec.get("Срок") or 0)),
                "image_url": (rec.get("image_url") or rec.get("Image") or rec.get("Картинка") or "").strip(),
                "channel": (rec.get("channel") or rec.get("Channel") or rec.get("Канал") or "").strip(),
            }
            if course["id"]:
                courses.append(course)
        return courses
    else:
        data = fetch_sheet_csv(GSHEET_COURSES_NAME)
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
            duration = d.get("duration_minutes") or d.get("Duration") or d.get("Срок") or "0"
            image = (d.get("image_url") or d.get("Image") or d.get("Картинка") or "").strip()
            channel = (d.get("channel") or d.get("Channel") or d.get("Канал") or "").strip()
            try:
                price = float(str(price).replace(",", ".") if price else 0)
            except (ValueError, TypeError):
                price = 0.0
            try:
                duration = int(float(duration)) if duration else 0
            except (ValueError, TypeError):
                duration = 0
            courses.append({
                "id": course_id,
                "name": name,
                "description": desc,
                "price": price,
                "duration_minutes": duration,
                "image_url": image,
                "channel": channel
            })
        return courses

def get_texts_data():
    if GOOGLE_SHEETS_USE_API:
        try:
            import gspread
            from oauth2client.service_account import ServiceAccountCredentials
        except ImportError:
            raise RuntimeError("gspread/oauth2client not installed. Set GOOGLE_SHEETS_USE_API=False or install libs.")
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive.readonly"]
        creds = ServiceAccountCredentials.from_json_keyfile_name(GOOGLE_CREDENTIALS_FILE, scope)
        client = gspread.authorize(creds)
        sheet = client.open_by_key(GSHEET_ID)
        ws = sheet.worksheet(GSHEET_TEXTS_NAME)
        data = ws.get_all_values()
        texts = {}
        for row in data:
            if len(row) >= 2 and row[0]:
                texts[row[0]] = row[1]
        return texts
    else:
        data = fetch_sheet_csv(GSHEET_TEXTS_NAME)
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
