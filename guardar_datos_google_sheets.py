# guardar_datos_google_sheets.py - Versión Producción
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
CREDS_FILE = os.getenv("CREDS_FILE")  # Ruta al archivo JSON de credenciales
SPREADSHEET_ID = os.getenv("SPREADSHEET_ID")  # ID de tu Google Sheet
SHEET_NAME = os.getenv("SHEET_NAME", "bd")  # Nombre de la hoja principal

if not CREDS_FILE:
    raise ValueError("❌ CREDS_FILE no configurado en .env")
if not SPREADSHEET_ID:
    raise ValueError("❌ SPREADSHEET_ID no configurado en .env")

# Autenticación con Google Sheets
SCOPE = ['https://www.googleapis.com/auth/spreadsheets']

try:
    credentials = Credentials.from_service_account_file(CREDS_FILE, scopes=SCOPE)
    client = gspread.authorize(credentials)
    logger.info("✅ Conexión con Google Sheets establecida")
except Exception as e:
    logger.error(f"❌ Error conectando con Google Sheets: {str(e)}")
    raise

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
    try:
        # Conectar con la hoja
        sheet = client.open_by_key(SPREADSHEET_ID).worksheet(SHEET_NAME)
        
        # Crear timestamp actual
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # PERSONALIZAR: Ajustar según tu estructura de columnas
        # Estructura actual: [Timestamp, Nombre, Correo, Telefono, Servicio, Comentario]
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
    try:
        sheet = client.open_by_key(SPREADSHEET_ID).worksheet(SHEET_NAME)
        registros = sheet.get_all_records()
        correo_input = correo.strip().lower()

        for fila in registros:
            # PERSONALIZAR: Ajustar nombre de columna según tu hoja
            correo_bd = str(fila.get("Indícanos tu Correo Electrónico", "")).strip().lower()
            
            if correo_input == correo_bd:
                nombre_encontrado = fila.get("Nombre Completo", "")
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
    try:
        sheet = client.open_by_key(SPREADSHEET_ID).worksheet(SHEET_NAME)
        registros = sheet.get_all_records()
        correo_input = correo.strip().lower()

        for fila in registros:
            correo_bd = str(fila.get("Indícanos tu Correo Electrónico", "")).strip().lower()
            
            if correo_input == correo_bd:
                # PERSONALIZAR: Ajustar nombres de columnas según tu estructura
                datos_usuario = {
                    'nombre_completo': fila.get("Nombre Completo", ""),
                    'correo': fila.get("Indícanos tu Correo Electrónico", ""),
                    'telefono': fila.get("Indícanos por favor tu numero de contacto", ""),
                    'servicio_interesado': fila.get("Por favor indícanos en que servicio estas interesado/a", ""),
                    'comentario': fila.get("Comentario o Mensaje", ""),
                    'timestamp_registro': fila.get("Timestamp", "")
                }
                
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
    try:
        sheet = client.open_by_key(SPREADSHEET_ID).worksheet(SHEET_NAME)
        registros = sheet.get_all_records()
        total = len(registros)
        
        logger.info(f"📊 Total usuarios registrados: {total}")
        return total
        
    except Exception as e:
        logger.error(f"❌ Error contando usuarios: {str(e)}")
        return 0

def validar_estructura_bd():
    """
    Valida que la estructura de la base de datos sea correcta.
    
    Returns:
        bool: True si la estructura es válida
    """
    try:
        sheet = client.open_by_key(SPREADSHEET_ID).worksheet(SHEET_NAME)
        headers = sheet.row_values(1)
        
        # PERSONALIZAR: Definir headers esperados para tu caso
        headers_esperados = [
            "Timestamp",
            "Nombre Completo", 
            "Indícanos tu Correo Electrónico",
            "Indícanos por favor tu numero de contacto",
            "Por favor indícanos en que servicio estas interesado/a",
            "Comentario o Mensaje"
        ]
        
        estructura_valida = True
        for i, header_esperado in enumerate(headers_esperados):
            if i >= len(headers) or headers[i] != header_esperado:
                logger.warning(f"⚠️ Header incorrecto en columna {i+1}: '{headers[i] if i < len(headers) else 'FALTANTE'}' (esperado: '{header_esperado}')")
                estructura_valida = False
        
        if estructura_valida:
            logger.info("✅ Estructura de BD válida")
        else:
            logger.error("❌ Estructura de BD inválida")
            
        return estructura_valida
        
    except Exception as e:
        logger.error(f"❌ Error validando estructura: {str(e)}")
        return False

def obtener_estadisticas_bd():
    """
    Obtiene estadísticas básicas de la base de datos.
    
    Returns:
        dict: Estadísticas de la base de datos
    """
    try:
        sheet = client.open_by_key(SPREADSHEET_ID).worksheet(SHEET_NAME)
        registros = sheet.get_all_records()
        
        total_usuarios = len(registros)
        
        # Contar usuarios por servicio de interés
        servicios = {}
        for registro in registros:
            servicio = registro.get("Por favor indícanos en que servicio estas interesado/a", "Sin especificar")
            servicios[servicio] = servicios.get(servicio, 0) + 1
        
        # Registros recientes (últimos 7 días)
        hace_7_dias = datetime.datetime.now() - datetime.timedelta(days=7)
        registros_recientes = 0
        
        for registro in registros:
            try:
                timestamp_str = registro.get("Timestamp", "")
                if timestamp_str:
                    timestamp = datetime.datetime.strptime(timestamp_str, "%Y-%m-%d %H:%M:%S")
                    if timestamp > hace_7_dias:
                        registros_recientes += 1
            except:
                continue
        
        estadisticas = {
            'total_usuarios': total_usuarios,
            'registros_ultimos_7_dias': registros_recientes,
            'servicios_de_interes': servicios,
            'timestamp_consulta': datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        
        logger.info(f"📊 Estadísticas generadas: {total_usuarios} usuarios total, {registros_recientes} recientes")
        return estadisticas
        
    except Exception as e:
        logger.error(f"❌ Error obteniendo estadísticas: {str(e)}")
        return None

# Función de inicialización para verificar conexión
def inicializar_conexion():
    """
    Inicializa y verifica la conexión con Google Sheets.
    
    Returns:
        bool: True si la conexión es exitosa
    """
    try:
        # Verificar acceso a la hoja
        sheet = client.open_by_key(SPREADSHEET_ID)
        logger.info(f"✅ Acceso verificado a: {sheet.title}")
        
        # Verificar que existe la hoja principal
        worksheet = sheet.worksheet(SHEET_NAME)
        logger.info(f"✅ Hoja '{SHEET_NAME}' encontrada")
        
        # Validar estructura
        if validar_estructura_bd():
            logger.info("✅ Inicialización de Google Sheets completa")
            return True
        else:
            logger.warning("⚠️ Inicialización con advertencias de estructura")
            return True  # Continuar aunque haya advertencias
            
    except Exception as e:
        logger.error(f"❌ Error en inicialización: {str(e)}")
        return False

if __name__ == "__main__":
    # Pruebas de funcionamiento
    print("🔧 Módulo Google Sheets - Versión Producción")
    print("=" * 50)
    
    if inicializar_conexion():
        print("✅ Conexión establecida exitosamente")
        
        # Mostrar estadísticas
        stats = obtener_estadisticas_bd()
        if stats:
            print(f"\n📊 ESTADÍSTICAS:")
            print(f"   Total usuarios: {stats['total_usuarios']}")
            print(f"   Registros últimos 7 días: {stats['registros_ultimos_7_dias']}")
            print(f"   Servicios más solicitados:")
            for servicio, cantidad in sorted(stats['servicios_de_interes'].items(), key=lambda x: x[1], reverse=True)[:3]:
                print(f"     - {servicio}: {cantidad}")
    else:
        print("❌ Error en la conexión")
        print("Verifica tu configuración en el archivo .env")