# registro_agendamiento.py - Versión Producción
import os
import datetime
import logging
from dotenv import load_dotenv
import gspread
from google.oauth2.service_account import Credentials

# Configurar logging
logger = logging.getLogger(__name__)

# Cargar variables desde .env
load_dotenv()

# CONFIGURACIÓN - PERSONALIZAR AQUÍ
CREDS_FILE = os.getenv("CREDS_FILE")
SPREADSHEET_ID = os.getenv("SPREADSHEET_ID")
AGENDAMIENTOS_SHEET_NAME = os.getenv("AGENDAMIENTOS_SHEET_NAME", "agendamientos")

if not CREDS_FILE or not SPREADSHEET_ID:
    raise ValueError("❌ CREDS_FILE y SPREADSHEET_ID deben estar configurados en .env")

# Configurar conexión con Google Sheets
try:
    SCOPE = ['https://www.googleapis.com/auth/spreadsheets']
    credentials = Credentials.from_service_account_file(CREDS_FILE, scopes=SCOPE)
    client = gspread.authorize(credentials)
    logger.info("✅ Conexión con Google Sheets establecida para agendamientos")
except Exception as e:
    logger.error(f"❌ Error conectando con Google Sheets: {str(e)}")
    raise

def obtener_datos_usuario_completos(correo):
    """
    Obtiene todos los datos del usuario desde la hoja principal.
    
    Args:
        correo (str): Correo electrónico del usuario
    
    Returns:
        dict: Datos completos del usuario o None
    """
    try:
        hoja_bd = client.open_by_key(SPREADSHEET_ID).worksheet("bd")
        registros = hoja_bd.get_all_records()
        correo_input = correo.strip().lower()

        for fila in registros:
            # PERSONALIZAR: Ajustar nombre de columna según tu estructura
            correo_bd = str(fila.get("Indícanos tu Correo Electrónico", "")).strip().lower()
            
            if correo_input == correo_bd:
                datos_usuario = {
                    'nombre_completo': fila.get("Nombre Completo", ""),
                    'correo': fila.get("Indícanos tu Correo Electrónico", ""),
                    'telefono': fila.get("Indícanos por favor tu numero de contacto", ""),
                    'servicio_interesado': fila.get("Por favor indícanos en que servicio estas interesado/a", ""),
                    'comentario': fila.get("Comentario o Mensaje", ""),
                    'timestamp_registro': fila.get("Timestamp", "")
                }
                
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
            correo_registro = str(fila.get("Indícanos tu Correo Electrónico", "")).strip().lower()
            
            if correo_input == correo_registro:
                observaciones = str(fila.get("observaciones", "")).lower()
                fecha_agendamiento = str(fila.get("fecha de agendamiento", ""))
                timestamp = str(fila.get("Timestamp", ""))
                
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
    try:
        # Obtener datos del usuario
        datos_usuario = obtener_datos_usuario_completos(correo)
        if not datos_usuario:
            logger.error(f"❌ No se encontraron datos para actualizar: {correo}")
            return False
        
        hoja_agendamientos = client.open_by_key(SPREADSHEET_ID).worksheet(AGENDAMIENTOS_SHEET_NAME)
        
        # Timestamp de actualización
        timestamp_actualizacion = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # PERSONALIZAR: Ajustar estructura de columnas según tu hoja
        actualizaciones = [
            (fila_a_actualizar, 1, timestamp_actualizacion),                    # A: Timestamp
            (fila_a_actualizar, 2, datos_usuario['nombre_completo']),           # B: Nombre
            (fila_a_actualizar, 3, datos_usuario['correo']),                    # C: Correo
            (fila_a_actualizar, 4, datos_usuario['telefono']),                  # D: Teléfono
            (fila_a_actualizar, 5, datos_usuario['servicio_interesado']),       # E: Servicio
            (fila_a_actualizar, 6, fecha),                                      # F: Fecha
            (fila_a_actualizar, 7, hora),                                       # G: Hora
            (fila_a_actualizar, 8, observaciones)                               # H: Observaciones
        ]
        
        # Aplicar actualizaciones
        for fila_num, col_num, valor in actualizaciones:
            hoja_agendamientos.update_cell(fila_num, col_num, valor)
        
        logger.info(f"✅ Registro actualizado exitosamente para {datos_usuario['nombre_completo']}")
        return True
        
    except Exception as e:
        logger.error(f"❌ Error actualizando registro existente: {str(e)}")
        return False

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
    try:
        datos_usuario = obtener_datos_usuario_completos(correo)
        
        if not datos_usuario:
            logger.error(f"❌ No se encontraron datos del usuario: {correo}")
            return False
        
        hoja_agendamientos = client.open_by_key(SPREADSHEET_ID).worksheet(AGENDAMIENTOS_SHEET_NAME)
        timestamp_agendamiento = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # PERSONALIZAR: Ajustar estructura según tu hoja de agendamientos
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
    try:
        datos_usuario = obtener_datos_usuario_completos(correo)
        
        if not datos_usuario:
            logger.error(f"❌ No se encontraron datos para registrar rechazo: {correo}")
            return False
        
        hoja_agendamientos = client.open_by_key(SPREADSHEET_ID).worksheet(AGENDAMIENTOS_SHEET_NAME)
        timestamp_rechazo = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # PERSONALIZAR: Ajustar estructura según tu hoja
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

def obtener_agendamientos_usuario(correo):
    """
    Obtiene todos los agendamientos de un usuario específico.
    
    Args:
        correo (str): Correo del usuario
    
    Returns:
        list: Lista de agendamientos del usuario
    """
    try:
        hoja_agendamientos = client.open_by_key(SPREADSHEET_ID).worksheet(AGENDAMIENTOS_SHEET_NAME)
        registros = hoja_agendamientos.get_all_records()
        correo_input = correo.strip().lower()
        
        agendamientos_usuario = []
        
        for fila in registros:
            correo_registro = str(fila.get("Indícanos tu Correo Electrónico", "")).strip().lower()
            
            if correo_input == correo_registro:
                agendamiento = {
                    'timestamp': fila.get("Timestamp", ""),
                    'nombre': fila.get("Nombre Completo", ""),
                    'fecha': fila.get("fecha de agendamiento", ""),
                    'hora': fila.get("hora de agendamiento", ""),
                    'observaciones': fila.get("observaciones", ""),
                    'tipo': 'agendamiento' if fila.get("fecha de agendamiento", "") != "N/A" else 'rechazo'
                }
                agendamientos_usuario.append(agendamiento)
        
        logger.info(f"📋 {len(agendamientos_usuario)} registros encontrados para {correo}")
        return agendamientos_usuario
        
    except Exception as e:
        logger.error(f"❌ Error obteniendo agendamientos de usuario: {str(e)}")
        return []

def obtener_estadisticas_agendamientos():
    """
    Obtiene estadísticas generales de agendamientos.
    
    Returns:
        dict: Estadísticas de agendamientos
    """
    try:
        hoja_agendamientos = client.open_by_key(SPREADSHEET_ID).worksheet(AGENDAMIENTOS_SHEET_NAME)
        registros = hoja_agendamientos.get_all_records()
        
        # Contadores
        total_registros = len(registros)
        agendamientos_exitosos = 0
        rechazos = 0
        usuarios_unicos = set()
        
        # Registros por día (últimos 30 días)
        hace_30_dias = datetime.datetime.now() - datetime.timedelta(days=30)
        registros_recientes = 0
        
        for registro in registros:
            correo = registro.get("Indícanos tu Correo Electrónico", "")
            if correo:
                usuarios_unicos.add(correo.strip().lower())
            
            fecha_agendamiento = registro.get("fecha de agendamiento", "")
            if fecha_agendamiento and fecha_agendamiento != "N/A":
                agendamientos_exitosos += 1
            else:
                rechazos += 1
            
            # Verificar si es registro reciente
            try:
                timestamp_str = registro.get("Timestamp", "")
                if timestamp_str:
                    timestamp = datetime.datetime.strptime(timestamp_str, "%Y-%m-%d %H:%M:%S")
                    if timestamp > hace_30_dias:
                        registros_recientes += 1
            except:
                continue
        
        # Calcular tasas
        tasa_conversion = (agendamientos_exitosos / total_registros * 100) if total_registros > 0 else 0
        
        estadisticas = {
            'total_registros': total_registros,
            'agendamientos_exitosos': agendamientos_exitosos,
            'rechazos': rechazos,
            'usuarios_unicos': len(usuarios_unicos),
            'tasa_conversion': round(tasa_conversion, 2),
            'registros_ultimos_30_dias': registros_recientes,
            'timestamp_consulta': datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        
        logger.info(f"📊 Estadísticas: {agendamientos_exitosos}/{total_registros} agendamientos exitosos ({tasa_conversion:.1f}%)")
        return estadisticas
        
    except Exception as e:
        logger.error(f"❌ Error obteniendo estadísticas: {str(e)}")
        return None

def limpiar_registros_duplicados_usuario(correo):
    """
    Limpia registros duplicados de un usuario, manteniendo solo el más reciente.
    ⚠️ USAR CON PRECAUCIÓN: Esta función elimina filas.
    
    Args:
        correo (str): Correo del usuario
    
    Returns:
        bool: True si se limpiaron registros
    """
    try:
        hoja_agendamientos = client.open_by_key(SPREADSHEET_ID).worksheet(AGENDAMIENTOS_SHEET_NAME)
        registros = hoja_agendamientos.get_all_records()
        correo_input = correo.strip().lower()
        
        registros_usuario = []
        
        # Encontrar todos los registros del usuario
        for i, fila in enumerate(registros, start=2):
            correo_registro = str(fila.get("Indícanos tu Correo Electrónico", "")).strip().lower()
            
            if correo_input == correo_registro:
                timestamp = str(fila.get("Timestamp", ""))
                registros_usuario.append({
                    'fila': i,
                    'timestamp': timestamp,
                    'datos': fila
                })
        
        if len(registros_usuario) <= 1:
            logger.info(f"ℹ️ Usuario {correo} tiene {len(registros_usuario)} registro(s). No hay duplicados.")
            return True
        
        # Ordenar por timestamp (más reciente primero)
        registros_usuario.sort(key=lambda x: x['timestamp'], reverse=True)
        
        # Mantener solo el más reciente
        logger.info(f"🧹 Limpiando {len(registros_usuario)-1} registros duplicados para {correo}")
        
        # Eliminar de abajo hacia arriba para no afectar numeración
        filas_a_eliminar = [reg['fila'] for reg in registros_usuario[1:]]
        filas_a_eliminar.sort(reverse=True)
        
        for fila_num in filas_a_eliminar:
            hoja_agendamientos.delete_rows(fila_num)
            logger.info(f"   🗑️ Eliminada fila {fila_num}")
        
        logger.info(f"✅ Limpieza completada para {correo}")
        return True
        
    except Exception as e:
        logger.error(f"❌ Error limpiando registros duplicados: {str(e)}")
        return False

def validar_estructura_agendamientos():
    """
    Valida que la estructura de la hoja de agendamientos sea correcta.
    
    Returns:
        bool: True si la estructura es válida
    """
    try:
        hoja_agendamientos = client.open_by_key(SPREADSHEET_ID).worksheet(AGENDAMIENTOS_SHEET_NAME)
        headers = hoja_agendamientos.row_values(1)
        
        # PERSONALIZAR: Definir headers esperados para tu hoja de agendamientos
        headers_esperados = [
            "Timestamp",
            "Nombre Completo",
            "Indícanos tu Correo Electrónico",
            "Indícanos por favor tu numero de contacto",
            "Por favor indícanos en que servicio estas interesado/a",
            "fecha de agendamiento",
            "hora de agendamiento",
            "observaciones"
        ]
        
        estructura_valida = True
        for i, header_esperado in enumerate(headers_esperados):
            if i >= len(headers) or headers[i] != header_esperado:
                logger.warning(f"⚠️ Header incorrecto en columna {i+1}: '{headers[i] if i < len(headers) else 'FALTANTE'}' (esperado: '{header_esperado}')")
                estructura_valida = False
        
        if estructura_valida:
            logger.info("✅ Estructura de agendamientos válida")
        else:
            logger.error("❌ Estructura de agendamientos inválida")
            
        return estructura_valida
        
    except Exception as e:
        logger.error(f"❌ Error validando estructura: {str(e)}")
        return False

def inicializar_sistema_agendamientos():
    """
    Inicializa el sistema de agendamientos y verifica configuración.
    
    Returns:
        bool: True si la inicialización es exitosa
    """
    try:
        # Verificar acceso a la hoja
        spreadsheet = client.open_by_key(SPREADSHEET_ID)
        logger.info(f"✅ Acceso verificado a: {spreadsheet.title}")
        
        # Verificar que existe la hoja de agendamientos
        hoja_agendamientos = spreadsheet.worksheet(AGENDAMIENTOS_SHEET_NAME)
        logger.info(f"✅ Hoja '{AGENDAMIENTOS_SHEET_NAME}' encontrada")
        
        # Validar estructura
        if not validar_estructura_agendamientos():
            logger.warning("⚠️ Estructura de hoja no es la esperada, pero continuando...")
        
        # Obtener estadísticas iniciales
        stats = obtener_estadisticas_agendamientos()
        if stats:
            logger.info(f"📊 Sistema inicializado: {stats['total_registros']} registros, {stats['tasa_conversion']}% conversión")
        
        logger.info("✅ Sistema de agendamientos inicializado correctamente")
        return True
        
    except Exception as e:
        logger.error(f"❌ Error inicializando sistema de agendamientos: {str(e)}")
        return False

if __name__ == "__main__":
    # Pruebas de funcionamiento
    print("📅 Módulo Registro de Agendamientos - Versión Producción")
    print("=" * 60)
    
    if inicializar_sistema_agendamientos():
        print("✅ Sistema inicializado exitosamente")
        
        # Mostrar estadísticas
        stats = obtener_estadisticas_agendamientos()
        if stats:
            print(f"\n📊 ESTADÍSTICAS:")
            print(f"   Total registros: {stats['total_registros']}")
            print(f"   Agendamientos exitosos: {stats['agendamientos_exitosos']}")
            print(f"   Rechazos: {stats['rechazos']}")
            print(f"   Usuarios únicos: {stats['usuarios_unicos']}")
            print(f"   Tasa de conversión: {stats['tasa_conversion']}%")
            print(f"   Actividad últimos 30 días: {stats['registros_ultimos_30_dias']} registros")
        
        # Ejemplo de verificación de usuario
        print(f"\n🔍 EJEMPLO DE VERIFICACIÓN:")
        correo_prueba = "ejemplo@gmail.com"
        estado = verificar_estado_asesoria_usuario(correo_prueba)
        print(f"   Usuario: {correo_prueba}")
        print(f"   Tiene rechazo: {estado['tiene_rechazo']}")
        print(f"   Tiene cita exitosa: {estado['tiene_cita_exitosa']}")
        print(f"   Último estado: {estado['ultimo_estado']}")
        
    else:
        print("❌ Error en la inicialización")
        print("Verifica tu configuración en el archivo .env")