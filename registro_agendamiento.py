import os
import datetime
from dotenv import load_dotenv
import gspread
from google.oauth2.service_account import Credentials

# Cargar variables desde .env
load_dotenv()

CREDS_FILE = os.getenv("CREDS_FILE")
SPREADSHEET_ID = os.getenv("SPREADSHEET_ID")

if not CREDS_FILE:
    raise ValueError("❌ No se encontró CREDS_FILE en el archivo .env")

# Autenticación con Google Sheets
SCOPE = ['https://www.googleapis.com/auth/spreadsheets']
credentials = Credentials.from_service_account_file(CREDS_FILE, scopes=SCOPE)
client = gspread.authorize(credentials)

def obtener_datos_usuario_completos(correo):
    """
    Obtiene todos los datos del usuario desde la hoja 'bd' usando su correo electrónico.
    """
    try:
        hoja_bd = client.open_by_key(SPREADSHEET_ID).worksheet("bd")
        registros = hoja_bd.get_all_records()
        correo_input = correo.strip().lower()

        for fila in registros:
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
                
                print(f"✅ Datos encontrados para: {datos_usuario['nombre_completo']}")
                return datos_usuario
        
        print(f"⚠️ No se encontraron datos para: {correo}")
        return None
        
    except Exception as e:
        print(f"❌ Error al obtener datos del usuario: {str(e)}")
        return None

def verificar_estado_asesoria_usuario(correo):
    """
    Verifica si un usuario rechazó previamente la asesoría gratuita.
    MEJORADO: Busca el registro más reciente del usuario.
    
    Returns:
        dict: {
            'tiene_rechazo': bool,
            'tiene_cita_exitosa': bool,
            'ultimo_estado': str,
            'fila_rechazo': int,
            'registro_mas_reciente': dict
        }
    """
    try:
        hoja_agendamientos = client.open_by_key(SPREADSHEET_ID).worksheet("agendamientos")
        registros = hoja_agendamientos.get_all_records()
        correo_input = correo.strip().lower()
        
        tiene_rechazo = False
        tiene_cita_exitosa = False
        ultimo_estado = ""
        fila_rechazo = None
        registro_mas_reciente = None
        fecha_mas_reciente = None
        
        # Buscar todos los registros del usuario y encontrar el más reciente
        for i, fila in enumerate(registros, start=2):  # start=2 porque fila 1 son headers
            correo_registro = str(fila.get("Indícanos tu Correo Electrónico", "")).strip().lower()
            
            if correo_input == correo_registro:
                observaciones = str(fila.get("observaciones", "")).lower()
                fecha_agendamiento = str(fila.get("fecha de agendamiento", ""))
                timestamp = str(fila.get("Timestamp", ""))
                
                # Verificar si es el registro más reciente
                if not fecha_mas_reciente or timestamp > fecha_mas_reciente:
                    fecha_mas_reciente = timestamp
                    registro_mas_reciente = {
                        'fila': i,
                        'datos': fila,
                        'observaciones': observaciones
                    }
                
                # Verificar si tiene cita exitosa
                if "agendada con éxito" in observaciones or (fecha_agendamiento and fecha_agendamiento != "N/A"):
                    tiene_cita_exitosa = True
                    ultimo_estado = "cita_exitosa"
                
                # Verificar si tiene rechazo
                elif "rechazó" in observaciones or "no quiso" in observaciones:
                    tiene_rechazo = True
                    ultimo_estado = "rechazo"
                    fila_rechazo = i
        
        return {
            'tiene_rechazo': tiene_rechazo,
            'tiene_cita_exitosa': tiene_cita_exitosa,
            'ultimo_estado': ultimo_estado,
            'fila_rechazo': fila_rechazo,
            'registro_mas_reciente': registro_mas_reciente
        }
        
    except Exception as e:
        print(f"❌ Error verificando estado de asesoría: {str(e)}")
        return {
            'tiene_rechazo': False,
            'tiene_cita_exitosa': False,
            'ultimo_estado': "",
            'fila_rechazo': None,
            'registro_mas_reciente': None
        }

def actualizar_registro_existente_con_cita(correo, fecha, hora, observaciones, fila_a_actualizar):
    """
    NUEVA FUNCIÓN: Actualiza un registro existente de rechazo a cita exitosa.
    En lugar de crear un nuevo registro, actualiza el existente.
    """
    try:
        # Obtener datos del usuario
        datos_usuario = obtener_datos_usuario_completos(correo)
        if not datos_usuario:
            return False
        
        hoja_agendamientos = client.open_by_key(SPREADSHEET_ID).worksheet("agendamientos")
        
        # Actualizar timestamp
        timestamp_actualizacion = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # Actualizar todas las columnas relevantes en la fila existente
        actualizaciones = [
            (fila_a_actualizar, 1, timestamp_actualizacion),                    # A: Timestamp
            (fila_a_actualizar, 2, datos_usuario['nombre_completo']),           # B: Nombre
            (fila_a_actualizar, 3, datos_usuario['correo']),                    # C: Correo
            (fila_a_actualizar, 4, datos_usuario['telefono']),                  # D: Teléfono
            (fila_a_actualizar, 5, datos_usuario['servicio_interesado']),       # E: Servicio
            (fila_a_actualizar, 6, fecha),                                      # F: Fecha de agendamiento
            (fila_a_actualizar, 7, hora),                                       # G: Hora de agendamiento
            (fila_a_actualizar, 8, observaciones)                               # H: Observaciones
        ]
        
        # Aplicar todas las actualizaciones
        for fila_num, col_num, valor in actualizaciones:
            hoja_agendamientos.update_cell(fila_num, col_num, valor)
        
        print(f"✅ Registro existente actualizado exitosamente para {datos_usuario['nombre_completo']}")
        print(f"   📅 Nueva fecha: {fecha} - Hora: {hora}")
        print(f"   📝 Nueva observación: {observaciones}")
        return True
        
    except Exception as e:
        print(f"❌ Error actualizando registro existente: {str(e)}")
        return False

def registrar_agendamiento_completo(correo, fecha, hora, observaciones=""):
    """
    FUNCIÓN MEJORADA: Registra agendamiento completo.
    Si es segunda oportunidad, actualiza registro existente.
    Si es nuevo, crea registro nuevo.
    """
    try:
        # Verificar estado del usuario
        estado_asesoria = verificar_estado_asesoria_usuario(correo)
        
        # Si el usuario tiene un rechazo previo, actualizar registro existente
        if estado_asesoria['tiene_rechazo'] and estado_asesoria['registro_mas_reciente']:
            fila_a_actualizar = estado_asesoria['registro_mas_reciente']['fila']
            print(f"🔄 Actualizando registro existente (fila {fila_a_actualizar}) para segunda oportunidad...")
            return actualizar_registro_existente_con_cita(correo, fecha, hora, observaciones, fila_a_actualizar)
        
        # Si no tiene rechazo previo, crear nuevo registro
        else:
            print(f"➕ Creando nuevo registro de agendamiento...")
            datos_usuario = obtener_datos_usuario_completos(correo)
            
            if not datos_usuario:
                print(f"❌ No se encontraron datos del usuario: {correo}")
                return False
            
            hoja_agendamientos = client.open_by_key(SPREADSHEET_ID).worksheet("agendamientos")
            timestamp_agendamiento = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
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
            
            print(f"✅ Nuevo agendamiento registrado para {datos_usuario['nombre_completo']}")
            print(f"   📅 Fecha: {fecha} - Hora: {hora}")
            print(f"   📝 Observaciones: {observaciones}")
            return True
        
    except Exception as e:
        print(f"❌ Error al registrar agendamiento: {str(e)}")
        return False

def registrar_rechazo_asesoria(correo, motivo_rechazo="Usuario nuevo rechazó asesoría gratuita"):
    """
    Registra cuando un usuario rechaza la asesoría gratuita en la hoja 'agendamientos'.
    """
    try:
        datos_usuario = obtener_datos_usuario_completos(correo)
        
        if not datos_usuario:
            print(f"❌ No se encontraron datos del usuario para registrar rechazo: {correo}")
            return False
        
        hoja_agendamientos = client.open_by_key(SPREADSHEET_ID).worksheet("agendamientos")
        timestamp_rechazo = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        nueva_fila = [
            timestamp_rechazo,                              # A: Timestamp
            datos_usuario['nombre_completo'],               # B: Nombre Completo
            datos_usuario['correo'],                        # C: Correo Electrónico
            datos_usuario['telefono'],                      # D: Teléfono
            datos_usuario['servicio_interesado'],           # E: Servicio interesado
            "N/A",                                          # F: Fecha de agendamiento (vacía)
            "N/A",                                          # G: Hora de agendamiento (vacía)
            motivo_rechazo                                  # H: Observaciones
        ]
        
        hoja_agendamientos.append_row(nueva_fila, value_input_option="USER_ENTERED")
        
        print(f"📝 Rechazo registrado para {datos_usuario['nombre_completo']}")
        print(f"   💬 Motivo: {motivo_rechazo}")
        return True
        
    except Exception as e:
        print(f"❌ Error al registrar rechazo: {str(e)}")
        return False

def verificar_agendamientos_previos(correo):
    """
    Verifica si un usuario ya tiene agendamientos previos.
    """
    try:
        hoja_agendamientos = client.open_by_key(SPREADSHEET_ID).worksheet("agendamientos")
        registros = hoja_agendamientos.get_all_records()
        correo_input = correo.strip().lower()
        
        agendamientos_usuario = []
        for fila in registros:
            correo_registro = str(fila.get("Indícanos tu Correo Electrónico", "")).strip().lower()
            if correo_input == correo_registro:
                agendamientos_usuario.append({
                    'timestamp': fila.get("Timestamp", ""),
                    'fecha': fila.get("fecha de agendamiento", ""),
                    'hora': fila.get("hora de agendamiento", ""),
                    'observaciones': fila.get("observaciones", "")
                })
        
        return agendamientos_usuario
        
    except Exception as e:
        print(f"❌ Error verificando agendamientos previos: {str(e)}")
        return []

def limpiar_registros_duplicados(correo):
    """
    NUEVA FUNCIÓN: Limpia registros duplicados de un usuario, manteniendo solo el más reciente.
    USAR CON PRECAUCIÓN: Esta función elimina filas de la hoja.
    """
    try:
        hoja_agendamientos = client.open_by_key(SPREADSHEET_ID).worksheet("agendamientos")
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
            print(f"ℹ️ Usuario {correo} tiene {len(registros_usuario)} registro(s). No es necesario limpiar.")
            return True
        
        # Ordenar por timestamp (más reciente primero)
        registros_usuario.sort(key=lambda x: x['timestamp'], reverse=True)
        
        # Mantener solo el más reciente, eliminar los demás
        print(f"🧹 Limpiando {len(registros_usuario)-1} registros duplicados para {correo}")
        
        # Eliminar filas de abajo hacia arriba para no afectar numeración
        filas_a_eliminar = [reg['fila'] for reg in registros_usuario[1:]]
        filas_a_eliminar.sort(reverse=True)
        
        for fila_num in filas_a_eliminar:
            hoja_agendamientos.delete_rows(fila_num)
            print(f"   🗑️ Eliminada fila {fila_num}")
        
        print(f"✅ Limpieza completada. Registro más reciente mantenido.")
        return True
        
    except Exception as e:
        print(f"❌ Error limpiando registros duplicados: {str(e)}")
        return False

def diagnosticar_estructura_completa():
    """
    Diagnóstico completo de la estructura de ambas hojas.
    """
    print("="*60)
    print("🔍 DIAGNÓSTICO COMPLETO DE ESTRUCTURA")
    print("="*60)
    
    try:
        # Diagnosticar hoja 'bd'
        print("\n1. 📋 ESTRUCTURA HOJA 'bd':")
        hoja_bd = client.open_by_key(SPREADSHEET_ID).worksheet("bd")
        headers_bd = hoja_bd.row_values(1)
        
        if headers_bd:
            for i, header in enumerate(headers_bd, 1):
                print(f"   Columna {chr(64+i)}: '{header}'")
        else:
            print("   ❌ No se encontraron headers en 'bd'")
            
        # Diagnosticar hoja 'agendamientos'
        print("\n2. 📅 ESTRUCTURA HOJA 'agendamientos':")
        hoja_agendamientos = client.open_by_key(SPREADSHEET_ID).worksheet("agendamientos")
        headers_agendamientos = hoja_agendamientos.row_values(1)
        
        if headers_agendamientos:
            for i, header in enumerate(headers_agendamientos, 1):
                print(f"   Columna {chr(64+i)}: '{header}'")
        else:
            print("   ❌ No se encontraron headers en 'agendamientos'")
            
        # Contar registros
        registros_bd = hoja_bd.get_all_records()
        registros_agendamientos = hoja_agendamientos.get_all_records()
        
        print(f"\n3. 📊 ESTADÍSTICAS:")
        print(f"   • Usuarios registrados en 'bd': {len(registros_bd)}")
        print(f"   • Agendamientos en 'agendamientos': {len(registros_agendamientos)}")
        
        print("\n✅ Diagnóstico completado")
        
    except Exception as e:
        print(f"❌ Error en diagnóstico: {str(e)}")

# Función de prueba
def probar_sistema_segunda_oportunidad():
    """
    Función para probar la nueva funcionalidad de actualización de registros.
    """
    print("\n" + "="*60)
    print("🧪 PRUEBA DEL SISTEMA DE SEGUNDA OPORTUNIDAD MEJORADO")
    print("="*60)
    
    diagnosticar_estructura_completa()
    
    # Ejemplo de prueba con el email de Valeria
    correo_prueba = "valeria@gmail.com"
    
    print(f"\n🔄 Verificando estado actual para: {correo_prueba}")
    estado = verificar_estado_asesoria_usuario(correo_prueba)
    
    print(f"Resultado:")
    print(f"   • Tiene rechazo: {estado['tiene_rechazo']}")
    print(f"   • Tiene cita exitosa: {estado['tiene_cita_exitosa']}")
    print(f"   • Último estado: {estado['ultimo_estado']}")
    print(f"   • Fila de rechazo: {estado['fila_rechazo']}")
    print(f"   • Registro más reciente: Fila {estado['registro_mas_reciente']['fila'] if estado['registro_mas_reciente'] else 'N/A'}")

if __name__ == "__main__":
    print("📋 Módulo de registro mejorado cargado correctamente")
    probar_sistema_segunda_oportunidad()