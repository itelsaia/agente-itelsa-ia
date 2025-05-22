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
SHEET_NAME = os.getenv("SHEET_NAME", "bd")  # Por defecto 'bd'

if not CREDS_FILE:
    raise ValueError("❌ No se encontró CREDS_FILE en el archivo .env")

# Autenticación con Google Sheets
SCOPE = ['https://www.googleapis.com/auth/spreadsheets']
credentials = Credentials.from_service_account_file(CREDS_FILE, scopes=SCOPE)
client = gspread.authorize(credentials)

def guardar_datos(nombre_completo, correo, telefono, servicio_interesado, comentario_mensaje):
    """
    Guarda los datos del usuario en la hoja 'bd'.
    CORREGIDO: Usa la estructura exacta de columnas según las imágenes.
    """
    try:
        # Conectar con la hoja
        sheet = client.open_by_key(SPREADSHEET_ID).worksheet(SHEET_NAME)
        
        # Crear timestamp actual
        now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # Preparar nueva fila según la estructura exacta
        nueva_fila = [
            now,                    # A: Timestamp
            nombre_completo,        # B: Nombre Completo
            correo,                 # C: Indícanos tu Correo Electrónico
            telefono,               # D: Indícanos por favor tu numero de contacto
            servicio_interesado,    # E: Por favor indícanos en que servicio estas interesado/a
            comentario_mensaje      # F: Comentario o Mensaje
        ]
        
        # Insertar la fila
        sheet.append_row(nueva_fila, value_input_option="USER_ENTERED")
        
        print(f"✅ Usuario {nombre_completo} guardado exitosamente en la BD")
        return True
        
    except Exception as e:
        print(f"❌ Error al guardar datos: {str(e)}")
        return False

def verificar_usuario(correo):
    """
    Verifica si un usuario existe en la hoja 'bd' y retorna su nombre.
    CORREGIDO: Usa los nombres exactos de las columnas.
    """
    try:
        sheet = client.open_by_key(SPREADSHEET_ID).worksheet(SHEET_NAME)
        registros = sheet.get_all_records()
        correo_input = correo.strip().lower()

        for fila in registros:
            # Usar el nombre exacto de la columna según las imágenes
            correo_bd = str(fila.get("Indícanos tu Correo Electrónico", "")).strip().lower()

            if correo_input == correo_bd:
                nombre_encontrado = fila.get("Nombre Completo", "")
                print(f"✅ Usuario encontrado: {nombre_encontrado}")
                return nombre_encontrado

        print(f"⚠️ Usuario no encontrado: {correo}")
        return None
        
    except Exception as e:
        print(f"❌ Error al verificar usuario: {str(e)}")
        return None

def registrar_agendamiento(nombre, correo, telefono, fecha, hora, observaciones=""):
    """
    Registra el agendamiento en la pestaña 'agendamientos'.
    DESCONTINUADA: Usa registrar_agendamiento_completo en su lugar.
    """
    print("⚠️ Esta función está descontinuada. Usa 'registrar_agendamiento_completo' del módulo 'registro_agendamiento'")
    return False

# Función de diagnóstico
def diagnosticar_bd():
    """
    Diagnostica la estructura de la hoja 'bd'.
    """
    try:
        sheet = client.open_by_key(SPREADSHEET_ID).worksheet(SHEET_NAME)
        headers = sheet.row_values(1)
        registros = sheet.get_all_records()
        
        print("🔍 DIAGNÓSTICO HOJA 'bd':")
        print(f"   📊 Total de registros: {len(registros)}")
        print("   📋 Estructura de columnas:")
        
        for i, header in enumerate(headers, 1):
            print(f"      {chr(64+i)}: '{header}'")
            
        if registros:
            print("\n   📝 Ejemplo del primer registro:")
            primer_registro = registros[0]
            for key, value in primer_registro.items():
                print(f"      {key}: {value}")
                
    except Exception as e:
        print(f"❌ Error en diagnóstico: {str(e)}")

if __name__ == "__main__":
    print("📋 Módulo de Google Sheets cargado correctamente")
    diagnosticar_bd()