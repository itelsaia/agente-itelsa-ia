# app.py - Versión Producción Limpia para WhatsApp Business API
import os
import re
import logging
from datetime import datetime, timedelta
from flask import Flask, request, jsonify
from dotenv import load_dotenv
from openai import OpenAI
import requests

# Importar módulos personalizados
from guardar_datos_google_sheets import guardar_datos, verificar_usuario
from calendar_service import agendar_en_calendar, formatear_fecha_amigable
from registro_agendamiento import (
    registrar_agendamiento_completo, 
    registrar_rechazo_asesoria,
    verificar_estado_asesoria_usuario
)
from scraper import extraer_contenido_web

# Configurar logging para producción
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('chatbot.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Cargar variables de entorno
load_dotenv()

# Inicializar Flask
app = Flask(__name__)

# Configuración de APIs
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
WHATSAPP_VERIFY_TOKEN = os.getenv("WHATSAPP_VERIFY_TOKEN")
WHATSAPP_ACCESS_TOKEN = os.getenv("WHATSAPP_ACCESS_TOKEN")
WHATSAPP_PHONE_NUMBER_ID = os.getenv("WHATSAPP_PHONE_NUMBER_ID")

# CONFIGURACIÓN DE EMPRESA - PERSONALIZAR AQUÍ
EMPRESA_CONFIG = {
    "nombre": "ITELSA IA",  # CAMBIAR: Nombre de tu empresa
    "url_website": "https://itelsaia.com",  # CAMBIAR: URL de tu website
    "horario_atencion": "lunes a viernes de 8:00am a 5:00pm",  # CAMBIAR: Tu horario
    "telefono_soporte": "+57 300 123 4567",  # CAMBIAR: Tu teléfono
    "email_soporte": "soporte@itelsaia.com"  # CAMBIAR: Tu email
}

# Inicializar OpenAI
client = OpenAI(api_key=OPENAI_API_KEY)

# Almacenamiento temporal de sesiones de usuario (en producción usar Redis/Database)
sesiones_usuarios = {}

class GestorSesion:
    """Maneja las sesiones de conversación de usuarios"""
    
    def __init__(self, telefono):
        self.telefono = telefono
        self.estado = "inicial"  # inicial, registrando, conversando, agendando
        self.datos_usuario = {}
        self.pendiente_confirmacion = {}
        self.pregunto_sobre_asesoria = False
        self.es_segunda_oportunidad = False
        self.ultimo_mensaje = datetime.now()
        
    def actualizar_actividad(self):
        self.ultimo_mensaje = datetime.now()
        
    def es_sesion_activa(self):
        """Verifica si la sesión sigue activa (últimos 30 minutos)"""
        tiempo_limite = datetime.now() - timedelta(minutes=30)
        return self.ultimo_mensaje > tiempo_limite

def obtener_sesion(telefono):
    """Obtiene o crea una sesión para un usuario"""
    if telefono not in sesiones_usuarios:
        sesiones_usuarios[telefono] = GestorSesion(telefono)
    
    sesion = sesiones_usuarios[telefono]
    
    # Limpiar sesión si es muy antigua
    if not sesion.es_sesion_activa():
        sesiones_usuarios[telefono] = GestorSesion(telefono)
    
    sesiones_usuarios[telefono].actualizar_actividad()
    return sesiones_usuarios[telefono]

def enviar_mensaje_whatsapp(telefono, mensaje):
    """
    Envía mensaje por WhatsApp Business API
    PERSONALIZAR: Ajustar según tu configuración de WhatsApp
    """
    try:
        url = f"https://graph.facebook.com/v18.0/{WHATSAPP_PHONE_NUMBER_ID}/messages"
        
        headers = {
            "Authorization": f"Bearer {WHATSAPP_ACCESS_TOKEN}",
            "Content-Type": "application/json"
        }
        
        data = {
            "messaging_product": "whatsapp",
            "to": telefono,
            "type": "text",
            "text": {"body": mensaje}
        }
        
        response = requests.post(url, json=data, headers=headers)
        
        if response.status_code == 200:
            logger.info(f"Mensaje enviado exitosamente a {telefono}")
            return True
        else:
            logger.error(f"Error enviando mensaje: {response.status_code} - {response.text}")
            return False
            
    except Exception as e:
        logger.error(f"Error en envío de WhatsApp: {str(e)}")
        return False

def es_correo_valido(correo):
    """Valida formato de correo electrónico"""
    patron = r'^[\w\.-]+@[\w\.-]+\.\w{2,4}$'
    return re.match(patron, correo) is not None

def extraer_fecha_hora(texto):
    """Extrae fecha y hora del texto del usuario"""
    ahora = datetime.now()
    
    # PERSONALIZAR: Ajustar patrones según tu región/idioma
    patrones_fecha_hora = [
        r'para (mañana|hoy|pasado mañana) a las (\d{1,2}(?::\d{2})?)(am|pm)',
        r'(mañana|hoy|pasado mañana) a las (\d{1,2}(?::\d{2})?)(am|pm)',
        r'las (\d{1,2}(?::\d{2})?)(am|pm) (mañana|hoy|pasado mañana)',
        r'(\d{4}-\d{2}-\d{2}) (\d{1,2}):(\d{2})'
    ]
    
    for i, patron in enumerate(patrones_fecha_hora):
        match = re.search(patron, texto.lower())
        if match:
            try:
                if i == 3:  # Formato fecha completa
                    fecha = datetime.strptime(match.group(1), "%Y-%m-%d")
                    hora = f"{match.group(2)}:{match.group(3)}"
                    return fecha.strftime("%Y-%m-%d"), hora
                
                # Procesar días relativos
                if i in [0, 1]:
                    dia = match.group(1)
                    hora_texto = match.group(2)
                    am_pm = match.group(3)
                else:
                    hora_texto = match.group(1)
                    am_pm = match.group(2)
                    dia = match.group(3)
                
                # Calcular fecha
                if dia == "mañana":
                    fecha = ahora + timedelta(days=1)
                elif dia == "hoy":
                    fecha = ahora
                elif dia == "pasado mañana":
                    fecha = ahora + timedelta(days=2)
                
                # Formatear hora
                if ":" not in hora_texto:
                    hora_completa = f"{hora_texto}:00{am_pm}"
                else:
                    hora_completa = f"{hora_texto}{am_pm}"
                
                return fecha.strftime("%Y-%m-%d"), hora_completa
                
            except Exception:
                continue
    
    return None, None

def detectar_seleccion_opcion(texto, horarios_disponibles):
    """Detecta si el usuario seleccionó una opción de horario"""
    texto_lower = texto.lower()
    
    patrones_seleccion = [
        r'opci[óo]n\s*(\d+)',
        r'la\s*(\d+)',
        r'el\s*(\d+)',
        r'n[úu]mero\s*(\d+)',
        r'^(\d+)$'
    ]
    
    for patron in patrones_seleccion:
        match = re.search(patron, texto_lower)
        if match:
            try:
                numero = int(match.group(1))
                if 1 <= numero <= len(horarios_disponibles):
                    return horarios_disponibles[numero - 1]
            except (ValueError, IndexError):
                continue
    
    # Respuestas afirmativas para una sola opción
    if any(palabra in texto_lower for palabra in ['sí', 'si', 'ok', 'está bien', 'perfecto']):
        if len(horarios_disponibles) == 1:
            return horarios_disponibles[0]
    
    return None

def detectar_solicitud_agendamiento(texto):
    """Detecta si el usuario quiere agendar una cita"""
    texto_lower = texto.lower().strip()
    
    # PERSONALIZAR: Ajustar frases según tu contexto de negocio
    frases_agendamiento = [
        'quiero agendar', 'me gustaría agendar', 'necesito agendar',
        'quiero una cita', 'necesito una cita', 'quisiera una cita',
        'quiero programar', 'puedo agendar', 'agendar una cita',
        'quiero más asesoría', 'otra asesoría', 'nueva asesoría',
        'sí quiero', 'claro que sí', 'acepto', 'me interesa'
    ]
    
    return any(frase in texto_lower for frase in frases_agendamiento)

def detectar_rechazo_asesoria(texto):
    """Detecta si el usuario rechaza la asesoría"""
    texto_lower = texto.lower().strip()
    
    if texto_lower in ['no', 'nope', 'nah', 'no gracias']:
        return True
    
    frases_rechazo = [
        'no quiero agendar', 'no me interesa', 'no estoy interesado',
        'no tengo tiempo', 'no puedo', 'ahora no', 'después',
        'no quiero', 'no necesito', 'tal vez después', 'mejor no'
    ]
    
    return any(frase in texto_lower for frase in frases_rechazo)

def generar_mensaje_agendamiento(resultado, fecha, hora, sesion):
    """Genera mensaje amigable para resultado de agendamiento"""
    if resultado['disponible']:
        fecha_amigable = formatear_fecha_amigable(fecha)
        
        # Determinar tipo de asesoría
        if sesion.es_segunda_oportunidad:
            observaciones = f"Asesoría gratuita - Segunda oportunidad"
        elif sesion.datos_usuario.get('es_nuevo', False):
            observaciones = f"Asesoría gratuita - Usuario nuevo"
        else:
            observaciones = f"Asesoría programada"
        
        # Registrar en base de datos
        correo = sesion.datos_usuario.get('correo')
        if correo:
            registrar_agendamiento_completo(correo, fecha, hora, observaciones)
        
        return (f"¡Perfecto! ✅ Tu cita ha sido agendada para el {fecha_amigable} a las {hora}.\n\n"
                f"Recibirás confirmación por correo electrónico.\n\n"
                f"¿Hay algo más en lo que pueda ayudarte?")
    
    # Manejar diferentes motivos de no disponibilidad
    motivo = resultado['motivo']
    fecha_amigable = formatear_fecha_amigable(fecha)
    
    if motivo == 'fuera_horario_laboral':
        mensaje = f"Nuestro horario es {EMPRESA_CONFIG['horario_atencion']}. 😊\n\n"
        if resultado['horarios_alternativos']:
            mensaje += f"Horarios disponibles para el {fecha_amigable}:\n"
            for i, horario in enumerate(resultado['horarios_alternativos'], 1):
                mensaje += f"{i}. {horario}\n"
            mensaje += "\n¿Cuál prefieres? Solo envía el número."
            
            # Guardar opciones en sesión
            sesion.pendiente_confirmacion[fecha_amigable] = {
                'fecha': fecha,
                'horarios': resultado['horarios_alternativos']
            }
        return mensaje
    
    elif motivo == 'fin_semana':
        fecha_alt = resultado.get('fecha_alternativa', fecha)
        fecha_amigable_alt = formatear_fecha_amigable(fecha_alt)
        mensaje = f"No atendemos fines de semana, pero el {fecha_amigable_alt} sí. 📅\n\n"
        if resultado['horarios_alternativos']:
            mensaje += f"Horarios disponibles:\n"
            for i, horario in enumerate(resultado['horarios_alternativos'], 1):
                mensaje += f"{i}. {horario}\n"
            mensaje += "\n¿Te parece bien alguno? Envía el número."
            
            sesion.pendiente_confirmacion[fecha_amigable_alt] = {
                'fecha': fecha_alt,
                'horarios': resultado['horarios_alternativos']
            }
        return mensaje
    
    elif motivo == 'horario_ocupado':
        mensaje = f"Ese horario está ocupado para el {fecha_amigable}. 🕐\n\n"
        if resultado['horarios_alternativos']:
            mensaje += f"Otras opciones disponibles:\n"
            for i, horario in enumerate(resultado['horarios_alternativos'], 1):
                mensaje += f"{i}. {horario}\n"
            mensaje += "\n¿Cuál prefieres? Envía el número."
            
            sesion.pendiente_confirmacion[fecha_amigable] = {
                'fecha': fecha,
                'horarios': resultado['horarios_alternativos']
            }
        return mensaje
    
    return "Hubo un inconveniente. ¿Podrías intentar con otro horario? 😊"

def procesar_mensaje_usuario(telefono, mensaje):
    """
    Función principal que procesa mensajes de usuario
    PERSONALIZAR: Aquí puedes ajustar la lógica de negocio
    """
    try:
        sesion = obtener_sesion(telefono)
        mensaje_limpio = mensaje.strip()
        
        # Comando para reiniciar conversación
        if mensaje_limpio.lower() in ['reiniciar', 'empezar', 'start', 'hola']:
            sesion.estado = "inicial"
            sesion.datos_usuario = {}
            sesion.pendiente_confirmacion = {}
            
            return (f"¡Hola! 👋 Soy el asistente de {EMPRESA_CONFIG['nombre']}.\n\n"
                   f"Para ayudarte mejor, ¿podrías compartir tu correo electrónico?")
        
        # Estado inicial - solicitar correo
        if sesion.estado == "inicial":
            if not es_correo_valido(mensaje_limpio):
                return "Por favor, ingresa un correo electrónico válido. 📧"
            
            # Verificar si es usuario existente
            nombre_encontrado = verificar_usuario(mensaje_limpio)
            
            if nombre_encontrado:
                estado_asesoria = verificar_estado_asesoria_usuario(mensaje_limpio)
                
                sesion.datos_usuario = {
                    'nombre': nombre_encontrado,
                    'correo': mensaje_limpio,
                    'es_nuevo': False
                }
                
                # Usuario con rechazo previo (segunda oportunidad)
                if estado_asesoria['tiene_rechazo'] and not estado_asesoria['tiene_cita_exitosa']:
                    sesion.es_segunda_oportunidad = True
                    sesion.estado = "conversando"
                    
                    return (f"¡Hola de nuevo, {nombre_encontrado}! 👋\n\n"
                           f"Veo que aún no has aprovechado tu asesoría gratuita. "
                           f"¿Te gustaría programarla ahora? Es una excelente oportunidad "
                           f"para ayudarte con tus necesidades específicas. 🚀\n\n"
                           f"¿Cuándo te vendría bien?")
                
                # Usuario existente normal
                else:
                    sesion.estado = "conversando" 
                    return (f"¡Hola {nombre_encontrado}! 😊\n\n"
                           f"Es un placer tenerte de vuelta. ¿En qué puedo ayudarte hoy?")
            
            # Usuario nuevo - solicitar datos
            else:
                sesion.estado = "registrando"
                sesion.datos_usuario['correo'] = mensaje_limpio
                return (f"¡Bienvenido a {EMPRESA_CONFIG['nombre']}! ✨\n\n"
                       f"Eres nuevo aquí. ¿Cuál es tu nombre completo?")
        
        # Estado registrando - recolectar datos
        elif sesion.estado == "registrando":
            if 'nombre' not in sesion.datos_usuario:
                sesion.datos_usuario['nombre'] = mensaje_limpio
                return "¿Cuál es tu número de teléfono? 📱"
            
            elif 'telefono' not in sesion.datos_usuario:
                sesion.datos_usuario['telefono'] = mensaje_limpio
                return f"¿Qué servicio de {EMPRESA_CONFIG['nombre']} te interesa? 💼"
            
            elif 'servicio' not in sesion.datos_usuario:
                sesion.datos_usuario['servicio'] = mensaje_limpio
                return "¿Deseas dejar algún comentario adicional? (o escribe 'ninguno') 📝"
            
            elif 'comentario' not in sesion.datos_usuario:
                sesion.datos_usuario['comentario'] = mensaje_limpio if mensaje_limpio.lower() != 'ninguno' else ""
                
                # Confirmar datos
                datos = sesion.datos_usuario
                confirmacion = (f"Confirma tus datos:\n\n"
                               f"👤 Nombre: {datos['nombre']}\n"
                               f"📧 Correo: {datos['correo']}\n"
                               f"📱 Teléfono: {datos['telefono']}\n"
                               f"💼 Servicio: {datos['servicio']}\n"
                               f"📝 Comentario: {datos['comentario']}\n\n"
                               f"¿Son correctos? (sí/no)")
                
                sesion.estado = "confirmando_datos"
                return confirmacion
        
        # Estado confirmando datos
        elif sesion.estado == "confirmando_datos":
            if mensaje_limpio.lower() in ['sí', 'si', 's', 'yes', 'correcto']:
                # Guardar en base de datos
                datos = sesion.datos_usuario
                resultado = guardar_datos(
                    datos['nombre'], datos['correo'], datos['telefono'],
                    datos['servicio'], datos['comentario']
                )
                
                if resultado:
                    sesion.datos_usuario['es_nuevo'] = True
                    sesion.estado = "conversando"
                    
                    return (f"¡Excelente! ✅ Tu cuenta ha sido creada.\n\n"
                           f"Cuéntame: ¿qué aspecto específico de nuestros servicios te interesa más? "
                           f"¿Automatización, análisis de datos, chatbots o consultoría estratégica? 🤖")
                else:
                    return "Hubo un error al guardar tus datos. Por favor, inténtalo nuevamente."
            
            elif mensaje_limpio.lower() in ['no', 'n', 'incorrecto']:
                sesion.estado = "inicial"
                sesion.datos_usuario = {}
                return "Entendido. Volvamos a empezar. ¿Cuál es tu correo electrónico?"
            
            else:
                return "Por favor, responde 'sí' o 'no' para confirmar tus datos."
        
        # Estado conversando - chatbot principal
        elif sesion.estado == "conversando":
            return procesar_conversacion_principal(sesion, mensaje_limpio)
        
        else:
            # Estado no válido, reiniciar
            sesion.estado = "inicial"
            return "Algo salió mal. Empecemos de nuevo. ¿Cuál es tu correo electrónico?"
    
    except Exception as e:
        logger.error(f"Error procesando mensaje: {str(e)}")
        return "Disculpa, tuve un problema técnico. ¿Puedes intentar nuevamente?"

def procesar_conversacion_principal(sesion, mensaje):
    """
    Procesa la conversación principal con IA
    PERSONALIZAR: Ajustar prompts y lógica según tu negocio
    """
    try:
        # Verificar agendamiento pendiente
        if sesion.pendiente_confirmacion:
            for fecha_amigable, datos in sesion.pendiente_confirmacion.items():
                hora_seleccionada = detectar_seleccion_opcion(mensaje, datos['horarios'])
                if hora_seleccionada:
                    # Procesar agendamiento
                    resultado = agendar_en_calendar(
                        sesion.datos_usuario['nombre'],
                        sesion.datos_usuario['correo'],
                        sesion.datos_usuario.get('telefono', ''),
                        datos['fecha'],
                        hora_seleccionada
                    )
                    
                    sesion.pendiente_confirmacion = {}
                    return generar_mensaje_agendamiento(resultado, datos['fecha'], hora_seleccionada, sesion)
        
        # Verificar solicitud de agendamiento directo
        fecha, hora = extraer_fecha_hora(mensaje)
        if fecha and hora:
            resultado = agendar_en_calendar(
                sesion.datos_usuario['nombre'],
                sesion.datos_usuario['correo'],
                sesion.datos_usuario.get('telefono', ''),
                fecha,
                hora
            )
            return generar_mensaje_agendamiento(resultado, fecha, hora, sesion)
        
        # Detectar solicitud de agendamiento
        if detectar_solicitud_agendamiento(mensaje):
            if sesion.es_segunda_oportunidad:
                return (f"¡Excelente decisión! 🌟\n\n"
                       f"¿Cuál sería tu fecha y hora preferida? "
                       f"Nuestro horario es {EMPRESA_CONFIG['horario_atencion']}.")
            else:
                return (f"¡Perfecto! 🎉\n\n"
                       f"¿Cuál sería tu fecha y hora preferida? "
                       f"Nuestro horario es {EMPRESA_CONFIG['horario_atencion']}.")
        
        # Detectar rechazo de asesoría
        if detectar_rechazo_asesoria(mensaje):
            if sesion.datos_usuario.get('es_nuevo', False):
                registrar_rechazo_asesoria(
                    sesion.datos_usuario['correo'],
                    "Usuario nuevo rechazó asesoría gratuita"
                )
            
            return ("Entiendo perfectamente. La oferta seguirá disponible cuando estés listo. "
                   "¡Que tengas un excelente día! 😊")
        
        # Procesar con IA
        return generar_respuesta_ia(sesion, mensaje)
    
    except Exception as e:
        logger.error(f"Error en conversación principal: {str(e)}")
        return "Disculpa, tuve un problema. ¿Puedes repetir tu mensaje?"

def generar_respuesta_ia(sesion, mensaje):
    """
    Genera respuesta usando OpenAI
    PERSONALIZAR: Ajustar prompt según tu empresa y servicios
    """
    try:
        # Cargar contenido de la empresa
        contenido_web = extraer_contenido_web(EMPRESA_CONFIG['url_website']) or ""
        
        try:
            with open("contenido_fijo.txt", "r", encoding="utf-8") as file:
                contenido_manual = file.read()
        except FileNotFoundError:
            contenido_manual = f"Información de {EMPRESA_CONFIG['nombre']}: Empresa de servicios de IA."
        
        contexto_completo = contenido_manual + "\n\n" + contenido_web
        
        # Configurar prompt según tipo de usuario
        nombre_usuario = sesion.datos_usuario.get('nombre', 'Usuario')
        es_nuevo = sesion.datos_usuario.get('es_nuevo', False)
        
        if sesion.es_segunda_oportunidad:
            prompt_sistema = (
                f"Eres un asistente de {EMPRESA_CONFIG['nombre']}. {nombre_usuario} rechazó "
                f"previamente su asesoría gratuita pero regresó. Tu misión es conseguir que agende AHORA.\n\n"
                f"ESTRATEGIA:\n"
                f"- Sé cálido pero directo\n"
                f"- Enfócate en los beneficios de la asesoría GRATUITA\n"
                f"- Si muestra interés, facilita inmediatamente el agendamiento\n"
                f"- Pregunta sobre fecha y hora si dice que sí\n\n"
                f"INFORMACIÓN DE LA EMPRESA:\n{contexto_completo}"
            )
        elif es_nuevo:
            prompt_sistema = (
                f"Eres un asistente de ventas de {EMPRESA_CONFIG['nombre']}. {nombre_usuario} es "
                f"COMPLETAMENTE NUEVO y tu misión es que agende su primera asesoría GRATUITA.\n\n"
                f"REGLAS:\n"
                f"- Responde amablemente a sus preguntas\n"
                f"- DESPUÉS de cada respuesta, pregunta sobre agendar\n"
                f"- Enfoca los beneficios en la asesoría GRATUITA\n"
                f"- Si dice NO, respeta pero insiste gentilmente\n\n"
                f"INFORMACIÓN DE LA EMPRESA:\n{contexto_completo}"
            )
        else:
            prompt_sistema = (
                f"Eres un asistente de {EMPRESA_CONFIG['nombre']} hablando con {nombre_usuario}, "
                f"un cliente registrado.\n\n"
                f"OBJETIVOS:\n"
                f"- Brindar excelente soporte\n"
                f"- Resolver dudas técnicas\n"
                f"- Ser cálido y profesional\n"
                f"- Solo agendar si él lo solicita expresamente\n\n"
                f"INFORMACIÓN DE LA EMPRESA:\n{contexto_completo}"
            )
        
        # Generar respuesta con OpenAI
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": prompt_sistema},
                {"role": "user", "content": mensaje}
            ],
            temperature=0.7,
            max_tokens=300  # Limitado para WhatsApp
        )
        
        respuesta_ia = response.choices[0].message.content
        
        # Para usuarios nuevos, agregar pregunta de agendamiento si no la incluye
        if es_nuevo and not sesion.es_segunda_oportunidad:
            palabras_agendamiento = ['agendar', 'cita', 'asesoría', 'reunión', 'consulta', 'gratuita']
            if not any(palabra in respuesta_ia.lower() for palabra in palabras_agendamiento):
                import random
                preguntas = [
                    "\n\n¿Te gustaría agendar tu asesoría gratuita para analizar tu caso específico?",
                    "\n\n¿Cuándo podrías tener 30 minutos para una consulta gratuita personalizada?",
                    "\n\n¿Te interesa programar una reunión sin costo para revisar tu situación?"
                ]
                respuesta_ia += random.choice(preguntas)
        
        return respuesta_ia
    
    except Exception as e:
        logger.error(f"Error generando respuesta IA: {str(e)}")
        return ("Disculpa, tuve un problema técnico. ¿Puedes repetir tu pregunta? "
               f"También puedes contactarnos en {EMPRESA_CONFIG['telefono_soporte']}")

# Rutas de Flask para WhatsApp Webhook
@app.route('/webhook', methods=['GET'])
def verify_webhook():
    """Verificación del webhook de WhatsApp"""
    mode = request.args.get('hub.mode')
    token = request.args.get('hub.verify_token')
    challenge = request.args.get('hub.challenge')
    
    if mode == 'subscribe' and token == WHATSAPP_VERIFY_TOKEN:
        logger.info("Webhook verificado exitosamente")
        return challenge
    else:
        logger.warning("Fallo en verificación de webhook")
        return 'Forbidden', 403

@app.route('/webhook', methods=['POST'])
def handle_webhook():
    """Maneja mensajes entrantes de WhatsApp"""
    try:
        data = request.get_json()
        
        # Verificar estructura del mensaje
        if (data.get('object') and 
            data.get('entry') and 
            data['entry'][0].get('changes') and
            data['entry'][0]['changes'][0].get('value') and
            data['entry'][0]['changes'][0]['value'].get('messages')):
            
            messages = data['entry'][0]['changes'][0]['value']['messages']
            
            for message in messages:
                # Procesar solo mensajes de texto
                if message.get('type') == 'text':
                    telefono = message['from']
                    texto = message['text']['body']
                    
                    logger.info(f"Mensaje recibido de {telefono}: {texto}")
                    
                    # Procesar mensaje y generar respuesta
                    respuesta = procesar_mensaje_usuario(telefono, texto)
                    
                    # Enviar respuesta por WhatsApp
                    if respuesta:
                        enviar_mensaje_whatsapp(telefono, respuesta)
                    
        return jsonify({'status': 'success'}), 200
        
    except Exception as e:
        logger.error(f"Error procesando webhook: {str(e)}")
        return jsonify({'status': 'error'}), 500

@app.route('/health', methods=['GET'])
def health_check():
    """Endpoint para verificar estado del servicio"""
    return jsonify({
        'status': 'healthy',
        'timestamp': datetime.now().isoformat(),
        'service': EMPRESA_CONFIG['nombre']
    }), 200

@app.route('/stats', methods=['GET'])
def get_stats():
    """Endpoint para estadísticas básicas"""
    try:
        sesiones_activas = len([s for s in sesiones_usuarios.values() if s.es_sesion_activa()])
        return jsonify({
            'sesiones_activas': sesiones_activas,
            'total_sesiones': len(sesiones_usuarios),
            'timestamp': datetime.now().isoformat()
        }), 200
    except Exception as e:
        logger.error(f"Error obteniendo estadísticas: {str(e)}")
        return jsonify({'error': 'Error interno'}), 500

# Función para limpiar sesiones antiguas (ejecutar periódicamente)
def limpiar_sesiones_antiguas():
    """Limpia sesiones inactivas para liberar memoria"""
    try:
        sesiones_a_eliminar = []
        for telefono, sesion in sesiones_usuarios.items():
            if not sesion.es_sesion_activa():
                sesiones_a_eliminar.append(telefono)
        
        for telefono in sesiones_a_eliminar:
            del sesiones_usuarios[telefono]
        
        if sesiones_a_eliminar:
            logger.info(f"Eliminadas {len(sesiones_a_eliminar)} sesiones inactivas")
            
    except Exception as e:
        logger.error(f"Error limpiando sesiones: {str(e)}")

if __name__ == '__main__':
    # CONFIGURACIÓN DE DESPLIEGUE
    # DESARROLLO: Usar debug=True, port=5000
    # PRODUCCIÓN: Usar debug=False, port=80 o el que asigne tu hosting
    
    port = int(os.environ.get('PORT', 5000))  # Para Heroku/Railway
    app.run(host='0.0.0.0', port=port, debug=False)  # CAMBIAR: debug=False en producción