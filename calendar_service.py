import os
import datetime
import re
from dotenv import load_dotenv
import gspread
from google.oauth2.service_account import Credentials
# REMOVED: from registro_agendamiento import registrar_agendamiento_completo

# Cargar variables de entorno
load_dotenv()

# Obtener credenciales desde variables de entorno
CREDS_FILE = os.getenv("CREDS_FILE")
SPREADSHEET_ID = os.getenv("SPREADSHEET_ID")
GOOGLE_CALENDAR_ID = os.getenv("GOOGLE_CALENDAR_ID")

# Definir el alcance de la API
SCOPE = ["https://www.googleapis.com/auth/calendar"]
credentials = Credentials.from_service_account_file(CREDS_FILE, scopes=SCOPE)

# Construir el servicio de Google Calendar
from googleapiclient.discovery import build
service = build("calendar", "v3", credentials=credentials)


def convertir_hora_a_24h(hora_texto):
    """
    Convierte hora en formato 12h (con am/pm) a formato 24h silenciosamente.
    """
    hora_texto = hora_texto.strip().lower()
    
    es_pm = False
    if 'pm' in hora_texto:
        es_pm = True
        hora_texto = hora_texto.replace('pm', '').strip()
    elif 'am' in hora_texto:
        hora_texto = hora_texto.replace('am', '').strip()
    else:
        if ':' in hora_texto:
            return hora_texto
        else:
            return f"{hora_texto}:00"
    
    if ':' in hora_texto:
        partes = hora_texto.split(':')
        hora_num = int(partes[0])
        minutos = partes[1]
    else:
        hora_num = int(hora_texto)
        minutos = "00"
    
    if es_pm and hora_num != 12:
        hora_num += 12
    elif not es_pm and hora_num == 12:
        hora_num = 0
    
    return f"{hora_num:02d}:{minutos}"


def generar_horarios_disponibles(fecha):
    """
    Genera lista de horarios disponibles para una fecha específica.
    
    Returns:
        list: Lista de horarios disponibles en formato amigable
    """
    horarios_sugeridos = []
    
    # Horarios laborales: 8am a 4pm (última cita a las 4pm)
    horarios_base = ["8:00am", "9:00am", "10:00am", "11:00am", "12:00pm", "1:00pm", "2:00pm", "3:00pm", "4:00pm"]
    
    for hora_amigable in horarios_base:
        hora_24h = convertir_hora_a_24h(hora_amigable)
        
        try:
            # Verificar disponibilidad en calendario
            start_datetime = datetime.datetime.strptime(f"{fecha}T{hora_24h}:00", "%Y-%m-%dT%H:%M:%S")
            end_datetime = start_datetime + datetime.timedelta(hours=1)
            
            eventos = service.events().list(
                calendarId=GOOGLE_CALENDAR_ID,
                timeMin=start_datetime.isoformat() + "-05:00",
                timeMax=end_datetime.isoformat() + "-05:00",
                singleEvents=True,
                orderBy="startTime"
            ).execute()
            
            # Si no hay eventos, el horario está disponible
            if len(eventos.get("items", [])) == 0:
                horarios_sugeridos.append(hora_amigable)
        except:
            continue
    
    return horarios_sugeridos


def verificar_disponibilidad(fecha, hora):
    """
    Verifica disponibilidad silenciosamente sin mostrar mensajes de debug.
    
    Returns:
        dict: {
            'disponible': bool,
            'motivo': str,
            'horarios_alternativos': list
        }
    """
    try:
        # Convertir la hora a formato 24h
        hora_24h = convertir_hora_a_24h(hora)
        if not hora_24h:
            return {
                'disponible': False,
                'motivo': 'hora_invalida',
                'horarios_alternativos': []
            }
        
        # Verificar horario laboral
        hora_num = int(hora_24h.split(':')[0])
        if hora_num < 8 or hora_num >= 17:
            horarios_disponibles = generar_horarios_disponibles(fecha)
            return {
                'disponible': False,
                'motivo': 'fuera_horario_laboral',
                'horarios_alternativos': horarios_disponibles[:4]  # Solo los primeros 4
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
        if fecha_obj.weekday() >= 5:  # 5=sábado, 6=domingo
            # Sugerir el próximo lunes
            dias_hasta_lunes = 7 - fecha_obj.weekday()
            siguiente_lunes = fecha_obj + datetime.timedelta(days=dias_hasta_lunes)
            horarios_disponibles = generar_horarios_disponibles(siguiente_lunes.strftime("%Y-%m-%d"))
            return {
                'disponible': False,
                'motivo': 'fin_semana',
                'fecha_alternativa': siguiente_lunes.strftime("%Y-%m-%d"),
                'horarios_alternativos': horarios_disponibles[:4]
            }
        
        # Verificar conflictos en calendario
        start_datetime = datetime.datetime.strptime(f"{fecha}T{hora_24h}:00", "%Y-%m-%dT%H:%M:%S")
        end_datetime = start_datetime + datetime.timedelta(hours=1)
        
        eventos = service.events().list(
            calendarId=GOOGLE_CALENDAR_ID,
            timeMin=start_datetime.isoformat() + "-05:00",
            timeMax=end_datetime.isoformat() + "-05:00",
            singleEvents=True,
            orderBy="startTime"
        ).execute()
        
        if len(eventos.get("items", [])) > 0:
            horarios_disponibles = generar_horarios_disponibles(fecha)
            return {
                'disponible': False,
                'motivo': 'horario_ocupado',
                'horarios_alternativos': horarios_disponibles[:4]
            }
        
        # Todo OK, horario disponible
        return {
            'disponible': True,
            'motivo': 'disponible',
            'horarios_alternativos': []
        }
        
    except Exception as e:
        return {
            'disponible': False,
            'motivo': 'error_sistema',
            'horarios_alternativos': []
        }


def agendar_en_calendar(nombre, correo, telefono, fecha, hora):
    """
    Agenda una cita solo si está disponible, sin mostrar mensajes técnicos.
    CORREGIDO: Ya NO registra en Google Sheets aquí (se evita duplicación).
    
    Returns:
        dict: Resultado del agendamiento con información para mostrar al usuario
    """
    # Verificar disponibilidad silenciosamente
    resultado = verificar_disponibilidad(fecha, hora)
    
    if not resultado['disponible']:
        return resultado
    
    try:
        # Convertir hora y crear evento
        hora_24h = convertir_hora_a_24h(hora)
        hora_num = int(hora_24h.split(':')[0])
        minutos = hora_24h.split(':')[1]
        
        fecha_inicio = f"{fecha}T{hora_24h}:00"
        fecha_fin = f"{fecha}T{hora_num + 1:02d}:{minutos}:00"
        
        evento = {
            'summary': f"Asesoría gratuita - {nombre}",
            'description': f"Correo: {correo}\nTeléfono: {telefono}",
            'start': {
                'dateTime': fecha_inicio,
                'timeZone': 'America/Bogota',
            },
            'end': {
                'dateTime': fecha_fin,
                'timeZone': 'America/Bogota',
            },
        }
        
        # Solo crear evento en calendario
        service.events().insert(calendarId=GOOGLE_CALENDAR_ID, body=evento).execute()
        
        # REMOVED: El registro en Google Sheets se hace desde app.py
        # para evitar duplicación
        
        return {
            'disponible': True,
            'motivo': 'agendado_exitosamente',
            'horarios_alternativos': []
        }
        
    except Exception as e:
        return {
            'disponible': False,
            'motivo': 'error_agendamiento',
            'horarios_alternativos': []
        }


def formatear_fecha_amigable(fecha_str):
    """
    Convierte fecha YYYY-MM-DD a formato amigable.
    """
    try:
        fecha_obj = datetime.datetime.strptime(fecha_str, "%Y-%m-%d")
        dias_semana = ['lunes', 'martes', 'miércoles', 'jueves', 'viernes', 'sábado', 'domingo']
        meses = ['enero', 'febrero', 'marzo', 'abril', 'mayo', 'junio',
                 'julio', 'agosto', 'septiembre', 'octubre', 'noviembre', 'diciembre']
        
        dia_semana = dias_semana[fecha_obj.weekday()]
        mes = meses[fecha_obj.month - 1]
        
        return f"{dia_semana} {fecha_obj.day} de {mes}"
    except:
        return fecha_str