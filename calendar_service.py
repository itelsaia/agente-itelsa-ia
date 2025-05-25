# calendar_service.py - Versión Render
import os
import datetime
import logging
import json
from dotenv import load_dotenv
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build

# Configurar logging
logger = logging.getLogger(__name__)

# Cargar variables de entorno
load_dotenv()

# CONFIGURACIÓN
GOOGLE_CALENDAR_ID = os.getenv("GOOGLE_CALENDAR_ID")

# CONFIGURACIÓN DE HORARIOS
HORARIO_INICIO = 8  # 8 AM
HORARIO_FIN = 17    # 5 PM (última cita a las 4 PM)
DURACION_CITA = 1   # 1 hora por cita
DIAS_LABORABLES = [0, 1, 2, 3, 4]  # Lunes a Viernes (0=Lunes, 6=Domingo)

def setup_google_credentials():
    """Configura las credenciales de Google para Render"""
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
        SCOPE = ["https://www.googleapis.com/auth/calendar"]
        credentials = Credentials.from_service_account_info(creds_dict, scopes=SCOPE)
        service = build("calendar", "v3", credentials=credentials)
        
        logger.info("✅ Conexión con Google Calendar establecida")
        return service
        
    except Exception as e:
        logger.error(f"❌ Error conectando con Google Calendar: {str(e)}")
        raise

# Inicializar servicio
try:
    service = setup_google_credentials()
except Exception as e:
    logger.error(f"Error inicializando Google Calendar: {e}")
    service = None

def convertir_hora_a_24h(hora_texto):
    """
    Convierte hora en formato 12h (con am/pm) a formato 24h.
    
    Args:
        hora_texto (str): Hora en formato como "2pm", "10:30am", etc.
    
    Returns:
        str: Hora en formato 24h (HH:MM)
    """
    try:
        hora_texto = hora_texto.strip().lower()
        
        # Detectar AM/PM
        es_pm = 'pm' in hora_texto
        hora_limpia = hora_texto.replace('pm', '').replace('am', '').strip()
        
        # Procesar hora
        if ':' in hora_limpia:
            partes = hora_limpia.split(':')
            hora_num = int(partes[0])
            minutos = partes[1]
        else:
            hora_num = int(hora_limpia)
            minutos = "00"
        
        # Convertir a 24h
        if es_pm and hora_num != 12:
            hora_num += 12
        elif not es_pm and hora_num == 12:
            hora_num = 0
        
        return f"{hora_num:02d}:{minutos}"
        
    except Exception as e:
        logger.error(f"❌ Error convertiendo hora '{hora_texto}': {str(e)}")
        return None

def generar_horarios_disponibles(fecha):
    """
    Genera lista de horarios disponibles para una fecha específica.
    
    Args:
        fecha (str): Fecha en formato YYYY-MM-DD
    
    Returns:
        list: Lista de horarios disponibles en formato amigable
    """
    if not service:
        logger.error("❌ Servicio de Google Calendar no disponible")
        return []
    
    horarios_disponibles = []
    
    try:
        # Horarios base
        horarios_base = [
            "8:00am", "9:00am", "10:00am", "11:00am",
            "12:00pm", "1:00pm", "2:00pm", "3:00pm", "4:00pm"
        ]
        
        for hora_amigable in horarios_base:
            hora_24h = convertir_hora_a_24h(hora_amigable)
            if not hora_24h:
                continue
            
            # Verificar disponibilidad en calendario
            if verificar_horario_libre(fecha, hora_24h):
                horarios_disponibles.append(hora_amigable)
        
        logger.info(f"📅 {len(horarios_disponibles)} horarios disponibles para {fecha}")
        return horarios_disponibles
        
    except Exception as e:
        logger.error(f"❌ Error generando horarios para {fecha}: {str(e)}")
        return []

def verificar_horario_libre(fecha, hora_24h):
    """
    Verifica si un horario específico está libre en el calendario.
    
    Args:
        fecha (str): Fecha en formato YYYY-MM-DD
        hora_24h (str): Hora en formato HH:MM
    
    Returns:
        bool: True si está libre, False si está ocupado
    """
    if not service:
        return False
    
    try:
        # Crear ventana de tiempo
        start_datetime = datetime.datetime.strptime(f"{fecha}T{hora_24h}:00", "%Y-%m-%dT%H:%M:%S")
        end_datetime = start_datetime + datetime.timedelta(hours=DURACION_CITA)
        
        # Consultar eventos existentes
        eventos = service.events().list(
            calendarId=GOOGLE_CALENDAR_ID,
            timeMin=start_datetime.isoformat() + "-05:00",  # Timezone Colombia
            timeMax=end_datetime.isoformat() + "-05:00",
            singleEvents=True,
            orderBy="startTime"
        ).execute()
        
        # Si no hay eventos, está libre
        eventos_encontrados = len(eventos.get("items", []))
        esta_libre = eventos_encontrados == 0
        
        if not esta_libre:
            logger.info(f"⏰ Horario ocupado: {fecha} {hora_24h}")
        
        return esta_libre
        
    except Exception as e:
        logger.error(f"❌ Error verificando horario {fecha} {hora_24h}: {str(e)}")
        return False

def verificar_disponibilidad(fecha, hora):
    """
    Verifica disponibilidad completa de una fecha y hora solicitada.
    
    Args:
        fecha (str): Fecha en formato YYYY-MM-DD
        hora (str): Hora en formato amigable (ej: "2pm", "10:30am")
    
    Returns:
        dict: Resultado de la verificación con motivo y alternativas
    """
    try:
        # Convertir hora a formato 24h
        hora_24h = convertir_hora_a_24h(hora)
        if not hora_24h:
            return {
                'disponible': False,
                'motivo': 'hora_invalida',
                'horarios_alternativos': []
            }
        
        # Verificar horario laboral
        hora_num = int(hora_24h.split(':')[0])
        if hora_num < HORARIO_INICIO or hora_num >= HORARIO_FIN:
            horarios_disponibles = generar_horarios_disponibles(fecha)
            return {
                'disponible': False,
                'motivo': 'fuera_horario_laboral',
                'horarios_alternativos': horarios_disponibles[:4]
            }
        
        # Verificar formato de fecha
        try:
            fecha_obj = datetime.datetime.strptime(fecha, "%Y-%m-%d")
        except ValueError:
            return {
                'disponible': False,
                'motivo': 'fecha_invalida',
                'horarios_alternativos': []
            }
        
        # Verificar día laborable
        if fecha_obj.weekday() not in DIAS_LABORABLES:
            # Calcular próximo día laborable
            dias_hasta_laborable = 1
            siguiente_dia = fecha_obj + datetime.timedelta(days=dias_hasta_laborable)
            while siguiente_dia.weekday() not in DIAS_LABORABLES:
                dias_hasta_laborable += 1
                siguiente_dia = fecha_obj + datetime.timedelta(days=dias_hasta_laborable)
            
            horarios_disponibles = generar_horarios_disponibles(siguiente_dia.strftime("%Y-%m-%d"))
            return {
                'disponible': False,
                'motivo': 'fin_semana',
                'fecha_alternativa': siguiente_dia.strftime("%Y-%m-%d"),
                'horarios_alternativos': horarios_disponibles[:4]
            }
        
        # Verificar si el horario está libre
        if not verificar_horario_libre(fecha, hora_24h):
            horarios_disponibles = generar_horarios_disponibles(fecha)
            return {
                'disponible': False,
                'motivo': 'horario_ocupado',
                'horarios_alternativos': horarios_disponibles[:4]
            }
        
        # Todo correcto, horario disponible
        return {
            'disponible': True,
            'motivo': 'disponible',
            'horarios_alternativos': []
        }
        
    except Exception as e:
        logger.error(f"❌ Error verificando disponibilidad {fecha} {hora}: {str(e)}")
        return {
            'disponible': False,
            'motivo': 'error_sistema',
            'horarios_alternativos': []
        }

def agendar_en_calendar(nombre, correo, telefono, fecha, hora):
    """
    Agenda una cita en Google Calendar si está disponible.
    
    Args:
        nombre (str): Nombre del cliente
        correo (str): Correo del cliente
        telefono (str): Teléfono del cliente
        fecha (str): Fecha en formato YYYY-MM-DD
        hora (str): Hora en formato amigable
    
    Returns:
        dict: Resultado del agendamiento
    """
    if not service:
        return {
            'disponible': False,
            'motivo': 'error_servicio',
            'horarios_alternativos': []
        }
    
    try:
        # Verificar disponibilidad primero
        resultado = verificar_disponibilidad(fecha, hora)
        
        if not resultado['disponible']:
            logger.info(f"📅 Agendamiento rechazado para {nombre}: {resultado['motivo']}")
            return resultado
        
        # Proceder con el agendamiento
        hora_24h = convertir_hora_a_24h(hora)
        hora_num = int(hora_24h.split(':')[0])
        minutos = hora_24h.split(':')[1]
        
        # Crear fechas de inicio y fin
        fecha_inicio = f"{fecha}T{hora_24h}:00"
        fecha_fin = f"{fecha}T{hora_num + DURACION_CITA:02d}:{minutos}:00"
        
        # Crear evento
        evento = {
            'summary': f"Asesoría - {nombre}",
            'description': (
                f"Cliente: {nombre}\n"
                f"Correo: {correo}\n"
                f"Teléfono: {telefono}\n"
                f"Tipo: Asesoría gratuita"
            ),
            'start': {
                'dateTime': fecha_inicio,
                'timeZone': 'America/Bogota',
            },
            'end': {
                'dateTime': fecha_fin,
                'timeZone': 'America/Bogota',
            },
            'attendees': [
                {'email': correo}
            ],
            'reminders': {
                'useDefault': False,
                'overrides': [
                    {'method': 'email', 'minutes': 24 * 60},  # 1 día antes
                    {'method': 'popup', 'minutes': 60},       # 1 hora antes
                ],
            },
        }
        
        # Crear el evento en el calendario
        evento_creado = service.events().insert(
            calendarId=GOOGLE_CALENDAR_ID,
            body=evento,
            sendUpdates='all'  # Enviar invitaciones por email
        ).execute()
        
        logger.info(f"✅ Cita agendada exitosamente para {nombre} - {fecha} {hora}")
        
        return {
            'disponible': True,
            'motivo': 'agendado_exitosamente',
            'evento_id': evento_creado.get('id'),
            'horarios_alternativos': []
        }
        
    except Exception as e:
        logger.error(f"❌ Error agendando cita para {nombre}: {str(e)}")
        return {
            'disponible': False,
            'motivo': 'error_agendamiento',
            'horarios_alternativos': []
        }

def formatear_fecha_amigable(fecha_str):
    """
    Convierte fecha YYYY-MM-DD a formato amigable en español.
    
    Args:
        fecha_str (str): Fecha en formato YYYY-MM-DD
    
    Returns:
        str: Fecha en formato amigable
    """
    try:
        fecha_obj = datetime.datetime.strptime(fecha_str, "%Y-%m-%d")
        
        dias_semana = [
            'lunes', 'martes', 'miércoles', 'jueves',
            'viernes', 'sábado', 'domingo'
        ]
        meses = [
            'enero', 'febrero', 'marzo', 'abril', 'mayo', 'junio',
            'julio', 'agosto', 'septiembre', 'octubre', 'noviembre', 'diciembre'
        ]
        
        dia_semana = dias_semana[fecha_obj.weekday()]
        mes = meses[fecha_obj.month - 1]
        
        return f"{dia_semana} {fecha_obj.day} de {mes}"
        
    except Exception as e:
        logger.error(f"❌ Error formateando fecha '{fecha_str}': {str(e)}")
        return fecha_str

def verificar_conexion_calendar():
    """
    Verifica que la conexión con Google Calendar funcione correctamente.
    
    Returns:
        bool: True si la conexión es exitosa
    """
    if not service:
        return False
    
    try:
        # Intentar obtener información del calendario
        calendar = service.calendars().get(calendarId=GOOGLE_CALENDAR_ID).execute()
        logger.info(f"✅ Conexión verificada con calendario: {calendar.get('summary', 'Sin nombre')}")
        return True
        
    except Exception as e:
        logger.error(f"❌ Error verificando conexión: {str(e)}")
        return False

# Verificar conexión al importar
if service and not verificar_conexion_calendar():
    logger.warning("⚠️ Advertencia: Problemas con la conexión a Google Calendar")