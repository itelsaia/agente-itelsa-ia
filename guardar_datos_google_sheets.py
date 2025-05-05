def guardar_datos(nombre_completo, correo, telefono, servicio_interesado, comentario_mensaje=""):
    """
    Guarda una nueva fila en Google Sheets incluyendo la fecha y hora automática (Timestamp).
    Columnas: Timestamp | Nombre | Correo | Teléfono | Servicio | Comentario
    """
    from google.oauth2 import service_account
    from googleapiclient.discovery import build
    import datetime

    # CONFIGURACIÓN DE TU PROYECTO
    SERVICE_ACCOUNT_FILE = 'itelsa-chatbot-457800-5e24805be5c7.json'  # Cambia si tu JSON tiene otro nombre
    SCOPES = ['https://www.googleapis.com/auth/spreadsheets']
    
    # ID CORREGIDO basado en la URL que veo en tu navegador
    SPREADSHEET_ID = '1w8xOpQCBcmoxWM0JqKI-fZYddgK6EinldDIfctaCNiQ'  # CORREGIDO
    SHEET_NAME = 'bd'  # Este nombre debe coincidir con el nombre exacto de la pestaña en Sheets

    # Conectar con Sheets
    credentials = service_account.Credentials.from_service_account_file(
        SERVICE_ACCOUNT_FILE, scopes=SCOPES)
    service = build('sheets', 'v4', credentials=credentials)
    sheet = service.spreadsheets()

    # FUNCIÓN PARA GUARDAR DATOS CON TIMESTAMP
    timestamp_actual = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')  # Generar timestamp
    
    # Crear array con los valores en el orden correcto de las columnas
    valores = [[
        timestamp_actual,
        nombre_completo,
        correo,
        telefono,
        servicio_interesado,
        comentario_mensaje
    ]]

    # Usar rango A:F para incluir todas las columnas (A para el Timestamp)
    rango = f'{SHEET_NAME}!A:F'  # Incluye columna A para el Timestamp
    
    body = {
        'values': valores
    }
    
    try:
        result = sheet.values().append(
            spreadsheetId=SPREADSHEET_ID,
            range=rango,
            valueInputOption='RAW',
            insertDataOption='INSERT_ROWS',
            body=body
        ).execute()
        
        print(f"✅ {result.get('updates').get('updatedCells')} celdas actualizadas en Google Sheets.")
        return True
    except Exception as e:
        print(f"❌ Error al guardar datos: {e}")
        
        # Imprimir el ID de la hoja para verificar
        print(f"ID de la hoja utilizado: {SPREADSHEET_ID}")
        
        # Intentar verificar si podemos acceder a la hoja
        try:
            # Obtener metadatos para verificar hojas disponibles
            metadata = sheet.get(spreadsheetId=SPREADSHEET_ID).execute()
            print("Hojas disponibles en el documento:")
            for sheet_info in metadata.get('sheets', []):
                title = sheet_info.get('properties', {}).get('title')
                print(f" - '{title}'")
        except Exception as meta_error:
            print(f"❌ No se puede acceder al documento: {meta_error}")
        
        return False