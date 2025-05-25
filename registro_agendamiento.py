# registro_agendamiento.py - Versión Render
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
AGENDAMIENTOS_SHEET_NAME = os.getenv("AGENDAMIENTOS_SHEET_NAME", "agendamientos")

if not SPREADSHEET_ID:
    raise ValueError("❌ SPREADSHEET_ID debe estar configurado en variables de entorno")

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
        
        logger.info("✅ Conexión con Google Sheets establecida para agendamientos")
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

def obtener_datos_usuario_completos(correo):
    """
    Obtiene todos los datos del usuario desde la hoja principal.
    
    Args:
        correo (str): Correo electrónico del usuario
    
    Returns:
        dict: Datos completos del usuario o None
    """
    if not client:
        logger.error("❌ Cliente de Google Sheets no disponible")
        return None
    
    try:
        hoja_bd = client.open_by_key(SPREADSHEET_ID).worksheet("bd")
        registros = hoja_bd.get_all_records()
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
                
                logger.info(f"✅ Datos de usuario obtenidos: {datos_usuario['nombre_completo']}")
                return datos_usuario
        
        logger.warning(f"⚠️ Usuario no encontrado en BD: {correo}")
        return None
        
    except Exception as e:
        logger.error(f"❌ Error obteniendo datos de usuario: {str(e)}")
        return None

def verificar_estado_asesoria_usuario(correo):
    """
    Verifica el estado de las asesorías de un usuario.
    
    Args:
        correo (str): Correo electrónico del usuario
    
    Returns:
        dict: Estado completo de las asesorías del usuario
    """
    if not client:
        logger.error("❌ Cliente de Google Sheets no disponible")
        return {
            'tiene_rechazo': False,
            'tiene_cita_exitosa': False,
            'ultimo_estado': "",
            'fila_rechazo': None,
            'registro_mas_reciente': None
        }
    
    try:
        hoja_agendamientos = client.open_by_key(SPREADSHEET_ID).worksheet(AGENDAMIENTOS_SHEET_NAME)
        registros = hoja_agendamientos.get_all_records()
        correo_input = correo.strip().lower()
        
        # Variables de estado
        tiene_rechazo = False
        tiene_cita_exitosa = False
        ultimo_estado = ""
        fila_rechazo = None
        registro_mas_reciente = None
        fecha_mas_reciente = None
        
        # Analizar todos los registros del usuario
        for i, fila in enumerate(registros, start=2):  # start=2 porque fila 1 son headers
            # Buscar correo en diferentes posibles nombres de columna
            correo_registro = ""
            for key in fila.keys():
                if 'correo' in key.lower() or 'email' in key.lower():
                    correo_registro = str(fila.get(key, "")).strip().lower()
                    break
            
            if correo_input == correo_registro:
                # Buscar observaciones y fecha de agendamiento
                observaciones = ""
                fecha_agendamiento = ""
                timestamp = ""
                
                for key, value in fila.items():
                    key_lower = key.lower()
                    if 'observacion' in key_lower:
                        observaciones = str(value).lower()
                    elif 'fecha' in key_lower and 'agendamiento' in key_lower:
                        fecha_agendamiento = str(value)
                    elif 'timestamp' in key_lower:
                        timestamp = str(value)
                
                # Determinar si es el registro más reciente
                if not fecha_mas_reciente or timestamp > fecha_mas_reciente:
                    fecha_mas_reciente = timestamp
                    registro_mas_reciente = {
                        'fila': i,
                        'datos': fila,
                        'observaciones': observaciones
                    }
                
                # Verificar tipo de registro
                if "agendada con éxito" in observaciones or (fecha_agendamiento and fecha_agendamiento != "N/A"):
                    tiene_cita_exitosa = True
                    ultimo_estado = "cita_exitosa"
                elif "rechazó" in observaciones or "no quiso" in observaciones:
                    tiene_rechazo = True
                    ultimo_estado = "rechazo"
                    fila_rechazo = i
        
        estado = {
            'tiene_rechazo': tiene_rechazo,
            'tiene_cita_exitosa': tiene_cita_exitosa,
            'ultimo_estado': ultimo_estado,
            'fila_rechazo': fila_rechazo,
            'registro_mas_reciente': registro_mas_reciente
        }
        
        logger.info(f"📊 Estado de {correo}: {ultimo_estado}")
        return estado
        
    except Exception as e:
        logger.error(f"❌ Error verificando estado de asesoría: {str(e)}")
        return {
            'tiene_rechazo': False,
            'tiene_cita_exitosa': False,
            'ultimo_estado': "",
            'fila_rechazo': None,
            'registro_mas_reciente': None
        }

def crear_nuevo_registro_agendamiento(correo, fecha, hora, observaciones):
    """
    Crea un nuevo registro de agendamiento.
    
    Args:
        correo (str): Correo del usuario
        fecha (str): Fecha de la cita
        hora (str): Hora de la cita
        observaciones (str): Observaciones del agendamiento
    
    Returns:
        bool: True si se creó exitosamente
    """
    if not client:
        logger.error("❌ Cliente de Google Sheets no disponible")
        return False
    
    try:
        datos_usuario = obtener_datos_usuario_completos(correo)
        
        if not datos_usuario:
            logger.error(f"❌ No se encontraron datos del usuario: {correo}")
            return False
        
        hoja_agendamientos = client.open_by_key(SPREADSHEET_ID).worksheet(AGENDAMIENTOS_SHEET_NAME)
        timestamp_agendamiento = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # Estructura flexible para diferentes configuraciones de hoja
        nueva_fila = [
            timestamp_agendamiento,                     # A: Timestamp
            datos_usuario['nombre_completo'],           # B: Nombre Completo
            datos_usuario['correo'],                    # C: Correo Electrónico
            datos_usuario['telefono'],                  # D: Teléfono
            datos_usuario['servicio_interesado'],       # E: Servicio interesado
            fecha,                                      # F: Fecha de agendamiento
            hora,                                       # G: Hora de agendamiento
            observaciones                               # H: Observaciones
        ]
        
        hoja_agendamientos.append_row(nueva_fila, value_input_option="USER_ENTERED")
        
        logger.info(f"✅ Nuevo agendamiento creado para {datos_usuario['nombre_completo']}")
        return True
        
    except Exception as e:
        logger.error(f"❌ Error creando nuevo agendamiento: {str(e)}")
        return False

def actualizar_registro_existente_con_cita(correo, fecha, hora, observaciones, fila_a_actualizar):
    """
    Actualiza un registro existente de rechazo a cita exitosa.
    
    Args:
        correo (str): Correo del usuario
        fecha (str): Fecha de la nueva cita
        hora (str): Hora de la nueva cita
        observaciones (str): Observaciones del agendamiento
        fila_a_actualizar (int): Número de fila a actualizar
    
    Returns:
        bool: True si se actualizó exitosamente
    """
    if not client:
        logger.error("❌ Cliente de Google Sheets no disponible")
        return False
    
    try:
        # Obtener datos del usuario
        datos_usuario = obtener_datos_usuario_completos(correo)
        if not datos_usuario:
            logger.error(f"❌ No se encontraron datos para actualizar: {correo}")
            return False
        
        hoja_agendamientos = client.open_by_key(SPREADSHEET_ID).worksheet(AGENDAMIENTOS_SHEET_NAME)
        
        # Timestamp de actualización
        timestamp_actualizacion = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # Actualizaciones por columna
        actualizaciones = [
            (fila_a_actualizar, 1, timestamp_actualizacion),            # A: Timestamp
            (fila_a_actualizar, 2, datos_usuario['nombre_completo']),   # B: Nombre
            (fila_a_actualizar, 3, datos_usuario['correo']),            # C: Correo
            (fila_a_actualizar, 4, datos_usuario['telefono']),          # D: Teléfono
            (fila_a_actualizar, 5, datos_usuario['servicio_interesado']), # E: Servicio
            (fila_a_actualizar, 6, fecha),                              # F: Fecha
            (fila_a_actualizar, 7, hora),                               # G: Hora
            (fila_a_actualizar, 8, observaciones)                       # H: Observaciones
        ]
        
        # Aplicar actualizaciones
        for fila_num, col_num, valor in actualizaciones:
            hoja_agendamientos.update_cell(fila_num, col_num, valor)
        
        logger.info(f"✅ Registro actualizado exitosamente para {datos_usuario['nombre_completo']}")
        return True
        
    except Exception as e:
        logger.error(f"❌ Error actualizando registro existente: {str(e)}")
        return False

def registrar_agendamiento_completo(correo, fecha, hora, observaciones=""):
    """
    Función principal para registrar agendamientos.
    Decide si actualizar registro existente o crear uno nuevo.
    
    Args:
        correo (str): Correo del usuario
        fecha (str): Fecha de la cita
        hora (str): Hora de la cita
        observaciones (str): Observaciones adicionales
    
    Returns:
        bool: True si se registró exitosamente
    """
    if not client:
        logger.error("❌ Cliente de Google Sheets no disponible")
        return False
    
    try:
        # Verificar estado actual del usuario
        estado_asesoria = verificar_estado_asesoria_usuario(correo)
        
        # Si tiene rechazo previo, actualizar registro existente
        if estado_asesoria['tiene_rechazo'] and estado_asesoria['registro_mas_reciente']:
            fila_a_actualizar = estado_asesoria['registro_mas_reciente']['fila']
            logger.info(f"🔄 Actualizando registro existente (fila {fila_a_actualizar}) - Segunda oportunidad")
            
            return actualizar_registro_existente_con_cita(
                correo, fecha, hora, observaciones, fila_a_actualizar
            )
        
        # Si no tiene rechazo previo, crear nuevo registro
        else:
            logger.info(f"➕ Creando nuevo registro de agendamiento")
            return crear_nuevo_registro_agendamiento(correo, fecha, hora, observaciones)
        
    except Exception as e:
        logger.error(f"❌ Error en registro completo de agendamiento: {str(e)}")
        return False

def registrar_rechazo_asesoria(correo, motivo_rechazo="Usuario rechazó asesoría gratuita"):
    """
    Registra cuando un usuario rechaza la asesoría.
    
    Args:
        correo (str): Correo del usuario
        motivo_rechazo (str): Motivo del rechazo
    
    Returns:
        bool: True si se registró exitosamente
    """
    if not client:
        logger.error("❌ Cliente de Google Sheets no disponible")
        return False
    
    try:
        datos_usuario = obtener_datos_usuario_completos(correo)
        
        if not datos_usuario:
            logger.error(f"❌ No se encontraron datos para registrar rechazo: {correo}")
            return False
        
        hoja_agendamientos = client.open_by_key(SPREADSHEET_ID).worksheet(AGENDAMIENTOS_SHEET_NAME)
        timestamp_rechazo = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # Estructura para registro de rechazo
        nueva_fila = [
            timestamp_rechazo,                              # A: Timestamp
            datos_usuario['nombre_completo'],               # B: Nombre Completo
            datos_usuario['correo'],                        # C: Correo Electrónico
            datos_usuario['telefono'],                      # D: Teléfono
            datos_usuario['servicio_interesado'],           # E: Servicio interesado
            "N/A",                                          # F: Fecha (vacía para rechazos)
            "N/A",                                          # G: Hora (vacía para rechazos)
            motivo_rechazo                                  # H: Observaciones
        ]
        
        hoja_agendamientos.append_row(nueva_fila, value_input_option="USER_ENTERED")
        
        logger.info(f"📝 Rechazo registrado para {datos_usuario['nombre_completo']}")
        return True
        
    except Exception as e:
        logger.error(f"❌ Error registrando rechazo: {str(e)}")
        return False

def verificar_conexion_agendamientos():
    """
    Verifica que la conexión con la hoja de agendamientos funcione correctamente.
    
    Returns:
        bool: True si la conexión es exitosa
    """
    if not client:
        return False
    
    try:
        # Verificar acceso a la hoja
        spreadsheet = client.open_by_key(SPREADSHEET_ID)
        logger.info(f"✅ Acceso verificado a: {spreadsheet.title}")
        
        # Verificar que existe la hoja de agendamientos
        hoja_agendamientos = spreadsheet.worksheet(AGENDAMIENTOS_SHEET_NAME)
        logger.info(f"✅ Hoja '{AGENDAMIENTOS_SHEET_NAME}' encontrada")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Error verificando conexión de agendamientos: {str(e)}")
        return False

# Verificar conexión al importar
if client and not verificar_conexion_agendamientos():
    logger.warning("⚠️ Advertencia: Problemas con la conexión a la hoja de agendamientos")