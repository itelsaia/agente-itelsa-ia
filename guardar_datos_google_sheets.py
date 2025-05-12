# guardar_datos_google_sheets.py
import os
import datetime
from dotenv import load_dotenv
import gspread
from google.oauth2.service_account import Credentials

# Cargar variables desde .env
load_dotenv()

CREDS_FILE = os.getenv("CREDS_FILE")
SPREADSHEET_ID = os.getenv("SPREADSHEET_ID")
SHEET_NAME = os.getenv("SHEET_NAME")

if not CREDS_FILE:
    raise ValueError("❌ No se encontró CREDS_FILE en el archivo .env")

# Autenticación con Google Sheets
SCOPE = ['https://www.googleapis.com/auth/spreadsheets']
credentials = Credentials.from_service_account_file(CREDS_FILE, scopes=SCOPE)
client = gspread.authorize(credentials)
sheet = client.open_by_key(SPREADSHEET_ID).worksheet(SHEET_NAME)

def guardar_datos(nombre_completo, correo, telefono, servicio_interesado, comentario_mensaje):
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    nueva_fila = [
        now,
        nombre_completo,
        correo,
        telefono,
        servicio_interesado,
        comentario_mensaje
    ]
    sheet.append_row(nueva_fila, value_input_option="USER_ENTERED")

# Solución robusta para verificar el correo electrónico en Google Sheets

def verificar_usuario(correo):
    registros = sheet.get_all_records()
    correo_input = correo.strip().lower()

    for fila in registros:
        correo_bd = str(fila.get("Indícanos tu Correo Electrónico", "")).strip().lower()

       

        if correo_input == correo_bd:
            return fila.get("Nombre Completo")

    return None
