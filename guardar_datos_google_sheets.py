# guardar_datos_google_sheets.py - Versión Render
import os
import datetime
import logging
import json
from dotenv import load_dotenv
import gspread
from google.oauth2.service_account import Credentials

# Configurar logging
logger = logging.getLogger(__name__)

# Cargar variables desde .env
load_dotenv()

# CONFIGURACIÓN
SPREADSHEET_ID = os.getenv("SPREADSHEET_ID")
SHEET_NAME = os.getenv("SHEET_NAME", "bd")

if not SPREADSHEET_ID:
    raise ValueError("❌ SPREADSHEET_ID no configurado en variables de entorno")

def setup_google_sheets_credentials():
    """Configura las credenciales de Google Sheets para Render"""
    try:
        # Opción 1: JSON completo como variable de entorno
        google_creds_json = os.getenv("GOOGLE_CREDENTIALS_JSON")
        if google_creds_json:
            creds_dict = json.loads(google_creds_json)
        else:
            # Opción 2: Variables individuales
            creds_dict = {
                "type": "service_account",
                "project_id": os.getenv("GOOGLE_PROJECT_ID", "itelsa-chatbot-457800"),
                "private_key_id": os.getenv("GOOGLE_PRIVATE_KEY_ID", "5e24805be5c74c038355e3d9b337bee4adc81b2c"),
                "private_key": os.getenv("GOOGLE_PRIVATE_KEY", "").replace('\\n', '\n'),
                "client_email": os.getenv("GOOGLE_CLIENT_EMAIL", "itelsa-chatbot@itelsa-chatbot-457800.iam.gserviceaccount.com"),
                "client_id": os.getenv("GOOGLE_CLIENT_ID", "105596722046990867098"),
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
                "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
                "client_x509_cert_url": os.getenv("GOOGLE_CLIENT_X509_CERT_URL", "https://www.googleapis.com/robot/v1/metadata/x509/itelsa-chatbot%40itelsa-chatbot-457800.iam.gserviceaccount.com"),
                "universe_domain": "googleapis.com"
            }
        
        # Crear credenciales desde el diccionario
        SCOPE = ['https://www.googleapis.com/auth/spreadsheets']
        credentials = Credentials.from_service_account_info(creds_dict, scopes=SCOPE)
        client = gspread.authorize(credentials)
        
        logger.info("✅ Conexión con Google Sheets establecida")
        return client
        
    except Exception as e:
        logger.error(f"❌ Error conectando con Google Sheets: {str(e)}")
        raise

# Inicializar cliente
try:
    client = setup_google_sheets_credentials()
except Exception as e:
    logger.error(f"Error inicializando Google Sheets: {e}")
    client = None

def guardar_datos(nombre_completo, correo, telefono, servicio_interesado, comentario_mensaje):
    """
    Guarda los datos del usuario en la hoja principal.
    
    Args:
        nombre_completo (str): Nombre completo del usuario
        correo (str): Correo electrónico
        telefono (str): Número de teléfono
        servicio_interesado (str): Servicio de interés
        comentario_mensaje (str): Comentario o mensaje adicional
    
    Returns:
        bool: True si se guardó exitosamente, False en caso contrario
    """
    if not client:
        logger.error("❌ Cliente de Google Sheets no disponible")
        return False
    
    try:
        # Conectar con la hoja
        sheet = client.open_by_key(SPREADSHEET_ID).worksheet(SHEET_NAME)
        
        # Crear timestamp actual
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # Estructura: [Timestamp, Nombre, Correo, Telefono, Servicio, Comentario]
        nueva_fila = [
            timestamp,              # A: Timestamp
            nombre_completo,        # B: Nombre Completo
            correo,                 # C: Correo Electrónico
            telefono,               # D: Teléfono
            servicio_interesado,    # E: Servicio Interesado
            comentario_mensaje      # F: Comentario
        ]
        
        # Insertar la fila
        sheet.append_row(nueva_fila, value_input_option="USER_ENTERED")
        
        logger.info(f"✅ Usuario {nombre_completo} guardado en BD")
        return True
        
    except Exception as e:
        logger.error(f"❌ Error guardando datos: {str(e)}")
        return False

def verificar_usuario(correo):
    """
    Verifica si un usuario existe en la base de datos.
    
    Args:
        correo (str): Correo electrónico a verificar
    
    Returns:
        str: Nombre del usuario si existe, None si no existe
    """
    if not client:
        logger.error("❌ Cliente de Google Sheets no disponible")
        return None
    
    try:
        sheet = client.open_by_key(SPREADSHEET_ID).worksheet(SHEET_NAME)
        registros = sheet.get_all_records()
        correo_input = correo.strip().lower()
        
        for fila in registros:
            # Buscar en diferentes posibles nombres de columna
            correo_bd = ""
            for key in fila.keys():
                if 'correo' in key.lower() or 'email' in key.lower():
                    correo_bd = str(fila.get(key, "")).strip().lower()
                    break
            
            if correo_input == correo_bd:
                # Buscar nombre en diferentes posibles nombres de columna
                nombre_encontrado = ""
                for key in fila.keys():
                    if 'nombre' in key.lower():
                        nombre_encontrado = fila.get(key, "")
                        break
                
                logger.info(f"✅ Usuario encontrado: {nombre_encontrado}")
                return nombre_encontrado
        
        logger.info(f"ℹ️ Usuario nuevo: {correo}")
        return None
        
    except Exception as e:
        logger.error(f"❌ Error verificando usuario: {str(e)}")
        return None

def obtener_datos_usuario_completos(correo):
    """
    Obtiene todos los datos de un usuario por su correo.
    
    Args:
        correo (str): Correo electrónico del usuario
    
    Returns:
        dict: Datos completos del usuario o None si no existe
    """
    if not client:
        logger.error("❌ Cliente de Google Sheets no disponible")
        return None
    
    try:
        sheet = client.open_by_key(SPREADSHEET_ID).worksheet(SHEET_NAME)
        registros = sheet.get_all_records()
        correo_input = correo.strip().lower()
        
        for fila in registros:
            # Buscar correo en diferentes posibles nombres de columna
            correo_bd = ""
            for key in fila.keys():
                if 'correo' in key.lower() or 'email' in key.lower():
                    correo_bd = str(fila.get(key, "")).strip().lower()
                    break
            
            if correo_input == correo_bd:
                # Extraer datos usando patrones flexibles
                datos_usuario = {
                    'nombre_completo': "",
                    'correo': correo,
                    'telefono': "",
                    'servicio_interesado': "",
                    'comentario': "",
                    'timestamp_registro': ""
                }
                
                # Mapear campos de forma flexible
                for key, value in fila.items():
                    key_lower = key.lower()
                    if 'nombre' in key_lower:
                        datos_usuario['nombre_completo'] = str(value)
                    elif 'telefono' in key_lower or 'contacto' in key_lower:
                        datos_usuario['telefono'] = str(value)
                    elif 'servicio' in key_lower or 'interesa' in key_lower:
                        datos_usuario['servicio_interesado'] = str(value)
                    elif 'comentario' in key_lower or 'mensaje' in key_lower:
                        datos_usuario['comentario'] = str(value)
                    elif 'timestamp' in key_lower or 'fecha' in key_lower:
                        datos_usuario['timestamp_registro'] = str(value)
                
                logger.info(f"✅ Datos encontrados para: {datos_usuario['nombre_completo']}")
                return datos_usuario
        
        logger.info(f"ℹ️ No se encontraron datos para: {correo}")
        return None
        
    except Exception as e:
        logger.error(f"❌ Error obteniendo datos de usuario: {str(e)}")
        return None

def contar_usuarios_registrados():
    """
    Cuenta el total de usuarios registrados.
    
    Returns:
        int: Número total de usuarios
    """
    if not client:
        return 0
    
    try:
        sheet = client.open_by_key(SPREADSHEET_ID).worksheet(SHEET_NAME)
        registros = sheet.get_all_records()
        total = len(registros)
        
        logger.info(f"📊 Total usuarios registrados: {total}")
        return total
        
    except Exception as e:
        logger.error(f"❌ Error contando usuarios: {str(e)}")
        return 0

def verificar_conexion_sheets():
    """
    Verifica que la conexión con Google Sheets funcione correctamente.
    
    Returns:
        bool: True si la conexión es exitosa
    """
    if not client:
        return False
    
    try:
        # Verificar acceso a la hoja
        sheet = client.open_by_key(SPREADSHEET_ID)
        logger.info(f"✅ Acceso verificado a: {sheet.title}")
        
        # Verificar que existe la hoja principal
        worksheet = sheet.worksheet(SHEET_NAME)
        logger.info(f"✅ Hoja '{SHEET_NAME}' encontrada")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Error verificando conexión: {str(e)}")
        return False

# Verificar conexión al importar
if client and not verificar_conexion_sheets():
    logger.warning("⚠️ Advertencia: Problemas con la conexión a Google Sheets")