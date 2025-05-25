# app.py - Versión Producción para Render
import os
import json
import re
from datetime import datetime, timedelta
from flask import Flask, request, jsonify
from dotenv import load_dotenv
from openai import OpenAI

# Importar módulos locales
from guardar_datos_google_sheets import guardar_datos, verificar_usuario
from calendar_service import agendar_en_calendar, formatear_fecha_amigable
from registro_agendamiento import (
    registrar_agendamiento_completo,
    registrar_rechazo_asesoria,
    verificar_estado_asesoria_usuario
)
from scraper import extraer_contenido_web

# Cargar variables de entorno
load_dotenv()

app = Flask(__name__)

# Configuración
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
WHATSAPP_VERIFY_TOKEN = os.getenv("WHATSAPP_VERIFY_TOKEN")
WHATSAPP_ACCESS_TOKEN = os.getenv("WHATSAPP_ACCESS_TOKEN")
WHATSAPP_PHONE_NUMBER_ID = os.getenv("WHATSAPP_PHONE_NUMBER_ID")

# Variables globales para sesiones de usuario
user_sessions = {}

def es_correo_valido(correo):
    patron = r'^[\w\.-]+@[\w\.-]+\.\w{2,4}$'
    return re.match(patron, correo)

def extraer_fecha_hora(texto):
    ahora = datetime.now()
    
    patrones_fecha_hora = [
        r'para (mañana|hoy|pasado mañana) a las (\d{1,2}(?::\d{2})?)(am|pm)',
        r'(mañana|hoy|pasado mañana) a las (\d{1,2}(?::\d{2})?)(am|pm)',
        r'las (\d{1,2}(?::\d{2})?)(am|pm) (mañana|hoy|pasado mañana)',
        r'(\d{4}-\d{2}-\d{2}) (\d{1,2}):(\d{2})'
    ]
    
    for i, patron in enumerate(patrones_fecha_hora):
        match = re.search(patron, texto.lower())
        if match:
            if i == 3:
                fecha = datetime.strptime(match.group(1), "%Y-%m-%d")
                hora = f"{match.group(2)}:{match.group(3)}"
                fecha_str = fecha.strftime("%Y-%m-%d")
                return fecha_str, hora
            
            if i in [0, 1]:
                dia = match.group(1)
                hora_texto = match.group(2)
                am_pm = match.group(3)
            else:
                hora_texto = match.group(1)
                am_pm = match.group(2)
                dia = match.group(3)
            
            if dia == "mañana":
                fecha = ahora + timedelta(days=1)
            elif dia == "hoy":
                fecha = ahora
            elif dia == "pasado mañana":
                fecha = ahora + timedelta(days=2)
            
            if ":" not in hora_texto:
                hora_completa = f"{hora_texto}:00{am_pm}"
            else:
                hora_completa = f"{hora_texto}{am_pm}"
            
            fecha_str = fecha.strftime("%Y-%m-%d")
            return fecha_str, hora_completa
    
    return None, None

def detectar_solicitud_agendamiento(texto):
    texto_lower = texto.lower().strip()
    
    frases_agendamiento = [
        'quiero agendar', 'me gustaría agendar', 'quisiera agendar', 'necesito agendar',
        'quiero una cita', 'necesito una cita', 'me gustaría una cita', 'quisiera una cita',
        'quiero programar', 'puedo agendar', 'es posible agendar', 'agendar una cita',
        'agendar cita', 'programar cita', 'reservar cita', 'solicitar cita',
        'quiero más asesoría', 'otra asesoría', 'nueva asesoría', 'segunda asesoría',
        'quiero reunión', 'solicitar reunión', 'programar reunión',
        'sí quiero', 'claro que sí', 'acepto', 'me interesa', 'por favor'
    ]
    
    for frase in frases_agendamiento:
        if frase in texto_lower:
            return True
    
    return False

def detectar_rechazo_asesoria(texto):
    texto_lower = texto.lower().strip()
    
    if texto_lower in ['no', 'nope', 'nah', 'no gracias']:
        return True
    
    frases_rechazo = [
        'no quiero agendar', 'no me interesa', 'no gracias', 'no estoy interesado',
        'no tengo tiempo', 'no puedo', 'ahora no', 'después', 'más tarde',
        'no quiero', 'no necesito', 'tal vez después', 'en otro momento',
        'no me convence', 'no por ahora', 'prefiero no', 'no es para mí',
        'no deseo', 'no me parece', 'mejor no', 'no creo',
        'otro día', 'otro momento', 'mejor después', 'quizás después'
    ]
    
    for frase in frases_rechazo:
        if frase in texto_lower:
            return True
    
    if 'no' in texto_lower and any(palabra in texto_lower for palabra in ['agendar', 'cita', 'asesoría', 'reunión']):
        return True
    
    return False

def generar_mensaje_amigable(resultado, fecha, hora, nombre_usuario, es_segunda_oportunidad, es_usuario_nuevo, correo):
    if resultado['disponible']:
        fecha_amigable = formatear_fecha_amigable(fecha)
        
        if es_segunda_oportunidad:
            observaciones = "Asesoría gratuita agendada con éxito - Segunda oportunidad (usuario cambió de opinión)"
        elif es_usuario_nuevo:
            observaciones = "Asesoría gratuita agendada con éxito - Usuario nuevo"
        else:
            observaciones = "Asesoría agendada - Usuario existente"
        
        if correo:
            registrar_agendamiento_completo(correo, fecha, hora, observaciones)
        
        return f"¡Perfecto! ✅ Tu cita ha sido agendada exitosamente para el {fecha_amigable} a las {hora}. Recibirás una confirmación en tu correo electrónico.\n\n¿Hay algo más en lo que pueda ayudarte sobre nuestros servicios de inteligencia artificial? ¿O tienes alguna pregunta sobre tu próxima asesoría?"
    
    motivo = resultado['motivo']
    
    if motivo == 'fuera_horario_laboral':
        mensaje = f"Entiendo que prefieres esa hora, pero nuestro horario de atención es de lunes a viernes de 8:00am a 5:00pm. 😊\n\n"
        if resultado['horarios_alternativos']:
            fecha_amigable = formatear_fecha_amigable(fecha)
            mensaje += f"Te propongo algunos horarios disponibles para el {fecha_amigable}:\n"
            for i, horario in enumerate(resultado['horarios_alternativos'], 1):
                mensaje += f"   {i}. {horario}\n"
            mensaje += "\n¿Alguno de estos horarios te conviene mejor? Solo dime el número de la opción que prefieras."
        else:
            mensaje += "Por favor, elígenos otro horario dentro de nuestro horario de atención. ¡Estaremos encantados de atenderte!"
        return mensaje
    
    elif motivo == 'fin_semana':
        fecha_alt = resultado.get('fecha_alternativa', fecha)
        fecha_amigable = formatear_fecha_amigable(fecha_alt)
        mensaje = f"Los fines de semana no tenemos atención, pero estaremos listos para ti el {fecha_amigable}. 📅\n\n"
        if resultado['horarios_alternativos']:
            mensaje += f"Aquí tienes algunos horarios disponibles para ese día:\n"
            for i, horario in enumerate(resultado['horarios_alternativos'], 1):
                mensaje += f"   {i}. {horario}\n"
            mensaje += "\n¿Te parece bien alguno de estos horarios? Solo dime el número."
        return mensaje
    
    elif motivo == 'horario_ocupado':
        fecha_amigable = formatear_fecha_amigable(fecha)
        mensaje = f"Ese horario ya está ocupado para el {fecha_amigable}, pero tengo otras opciones disponibles: 🕐\n\n"
        if resultado['horarios_alternativos']:
            for i, horario in enumerate(resultado['horarios_alternativos'], 1):
                mensaje += f"   {i}. {horario}\n"
            mensaje += "\n¿Cuál prefieres? Solo dime el número de la opción."
        else:
            mensaje += "Por favor, elígenos otro horario y verificaré la disponibilidad inmediatamente."
        return mensaje
    
    else:
        return "Ups, parece que hubo un pequeño inconveniente. ¿Podrías intentar con otro horario? Estoy aquí para ayudarte a encontrar la cita perfecta. 😊"

def enviar_mensaje_whatsapp(numero_telefono, mensaje):
    """Envía un mensaje por WhatsApp usando la API de Meta"""
    url = f"https://graph.facebook.com/v17.0/{WHATSAPP_PHONE_NUMBER_ID}/messages"
    
    headers = {
        "Authorization": f"Bearer {WHATSAPP_ACCESS_TOKEN}",
        "Content-Type": "application/json"
    }
    
    data = {
        "messaging_product": "whatsapp",
        "to": numero_telefono,
        "type": "text",
        "text": {"body": mensaje}
    }
    
    try:
        import requests
        response = requests.post(url, headers=headers, json=data)
        return response.status_code == 200
    except Exception as e:
        print(f"Error enviando mensaje WhatsApp: {e}")
        return False

def procesar_conversacion_llm(mensaje_usuario, session_data):
    """Procesa la conversación usando OpenAI"""
    try:
        # Obtener contexto de la empresa
        url_cliente = "https://itelsaia.com"
        contenido_web = extraer_contenido_web(url_cliente) or ""
        
        try:
            with open("contenido_fijo.txt", "r", encoding="utf-8") as file:
                contenido_manual = file.read()
        except FileNotFoundError:
            contenido_manual = "No hay contenido manual cargado."
        
        contexto_completo = contenido_manual + "\n\n" + contenido_web
        
        # Configurar prompt según el tipo de usuario
        es_segunda_oportunidad = session_data.get('es_segunda_oportunidad', False)
        es_usuario_nuevo = session_data.get('es_nuevo', False)
        nombre_usuario = session_data.get('nombre', 'Usuario')
        
        if es_segunda_oportunidad:
            prompt_sistema = (
                f"Eres un asistente amigable pero directo de ITELSA IA. {nombre_usuario} es un usuario registrado que anteriormente "
                f"rechazó su asesoría gratuita, pero ha regresado. Tu MISIÓN es conseguir que agende la asesoría AHORA.\n\n"
                f"ESTRATEGIA DIRECTA:\n"
                f"1. Sé cálido pero directo - pregunta inmediatamente sobre agendar\n"
                f"2. Enfócate en los beneficios de la asesoría GRATUITA\n"
                f"3. Si muestra cualquier señal de interés, facilita inmediatamente el agendamiento\n"
                f"4. Si dice 'sí' o muestra interés, ve directo a solicitar fecha y hora\n"
                f"5. No hagas preguntas generales sobre necesidades, ve directo al agendamiento\n\n"
                f"CONTEXTO DE SERVICIOS:\n{contexto_completo}"
            )
        elif es_usuario_nuevo:
            prompt_sistema = (
                f"Eres un asistente de ventas experto de ITELSA IA. {nombre_usuario} es un usuario COMPLETAMENTE NUEVO "
                f"y tu ÚNICA MISIÓN es que agende su primera asesoría GRATUITA.\n\n"
                f"REGLAS ESTRICTAS:\n"
                f"1. Responde amablemente a sus preguntas\n"
                f"2. OBLIGATORIO: Después de CADA respuesta, debes preguntarle sobre agendar:\n"
                f"   - '¿Te gustaría agendar tu primera asesoría gratuita ahora mismo?'\n"
                f"   - '¿Cuándo podrías tener 30 minutos para tu consulta gratuita?'\n"
                f"   - '¿Te interesa programar una reunión sin costo para conocer nuestros servicios?'\n"
                f"3. NUNCA termines sin invitar a agendar\n"
                f"4. Si dice NO, respeta pero insiste gentilmente en el siguiente mensaje\n"
                f"5. Enfoca todos los beneficios en la asesoría GRATUITA\n\n"
                f"CONTEXTO DE SERVICIOS:\n{contexto_completo}"
            )
        else:
            prompt_sistema = (
                f"Eres un asistente de soporte profesional de ITELSA IA hablando con {nombre_usuario}, "
                f"quien ya es un cliente registrado y confiable.\n\n"
                f"Tu objetivo es:\n"
                f"1. Brindar excelente soporte y información\n"
                f"2. Resolver todas sus dudas técnicas\n"
                f"3. Ser cálido y profesional\n"
                f"4. SOLO agendar si él expresamente lo solicita\n"
                f"5. No presionar para ventas adicionales\n\n"
                f"CONTEXTO DE SERVICIOS:\n{contexto_completo}"
            )
        
        # Preparar mensajes para OpenAI
        messages = [{"role": "system", "content": prompt_sistema}]
        
        # Agregar historial de conversación si existe
        if 'messages' in session_data:
            messages.extend(session_data['messages'])
        
        messages.append({"role": "user", "content": mensaje_usuario})
        
        # Llamar a OpenAI
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=messages,
            temperature=0.7,
            max_tokens=600
        )
        
        reply = response.choices[0].message.content
        
        # Actualizar historial de mensajes en la sesión
        if 'messages' not in session_data:
            session_data['messages'] = []
        
        session_data['messages'].append({"role": "user", "content": mensaje_usuario})
        session_data['messages'].append({"role": "assistant", "content": reply})
        
        # Mantener solo los últimos 10 mensajes para no exceder límites
        if len(session_data['messages']) > 10:
            session_data['messages'] = session_data['messages'][-10:]
        
        return reply
        
    except Exception as e:
        print(f"Error en OpenAI: {e}")
        return "Disculpa, tuve un pequeño problema técnico. ¿Puedes repetir tu mensaje? 😊"

@app.route("/webhook", methods=["GET", "POST"])
def webhook():
    if request.method == "GET":
        # Verificación del webhook de WhatsApp
        mode = request.args.get("hub.mode")
        token = request.args.get("hub.verify_token")
        challenge = request.args.get("hub.challenge")
        
        if mode == "subscribe" and token == WHATSAPP_VERIFY_TOKEN:
            return challenge, 200
        else:
            return "Forbidden", 403
    
    elif request.method == "POST":
        # Procesar mensaje entrante de WhatsApp
        data = request.get_json()
        
        try:
            # Extraer información del mensaje
            entry = data["entry"][0]
            changes = entry["changes"][0]
            value = changes["value"]
            
            if "messages" in value:
                message = value["messages"][0]
                from_number = message["from"]
                message_body = message["text"]["body"].strip()
                
                # Procesar el mensaje
                response_message = procesar_mensaje_usuario(from_number, message_body)
                
                # Enviar respuesta
                if response_message and enviar_mensaje_whatsapp(from_number, response_message):
                    print(f"Mensaje enviado a {from_number}: {response_message[:50]}...")
                else:
                    print(f"Error enviando mensaje a {from_number}")
                
        except Exception as e:
            print(f"Error procesando webhook: {e}")
        
        return jsonify({"status": "success"}), 200

def procesar_mensaje_usuario(numero_telefono, mensaje):
    """Procesa el mensaje del usuario y retorna la respuesta"""
    
    # Obtener o crear sesión del usuario
    if numero_telefono not in user_sessions:
        user_sessions[numero_telefono] = {
            'estado': 'inicial',
            'datos_usuario': {},
            'pendiente_confirmacion': {},
            'messages': []
        }
    
    session = user_sessions[numero_telefono]
    
    # Estado inicial: solicitar correo
    if session['estado'] == 'inicial':
        return "🤖 ¡Hola! Soy el asistente de ITELSA IA.\n📩 Para ayudarte mejor, por favor ingresa tu correo electrónico."
    
    # Validar correo electrónico
    elif session['estado'] == 'inicial' and not session['datos_usuario'].get('correo'):
        if not es_correo_valido(mensaje):
            return "❌ El correo electrónico no es válido. Inténtalo nuevamente."
        
        correo = mensaje.strip()
        nombre_encontrado = verificar_usuario(correo)
        
        if nombre_encontrado:
            estado_asesoria = verificar_estado_asesoria_usuario(correo)
            
            session['datos_usuario'] = {
                'nombre': nombre_encontrado,
                'correo': correo,
                'es_nuevo': False
            }
            
            if estado_asesoria['tiene_rechazo'] and not estado_asesoria['tiene_cita_exitosa']:
                session['es_segunda_oportunidad'] = True
                session['estado'] = 'conversacion'
                return f"👋 ¡Hola de nuevo, {nombre_encontrado}! Qué gusto verte otra vez.\n\nVeo que aún no has podido aprovechar tu primera asesoría gratuita con ITELSA IA. ✨ Las circunstancias pueden haber cambiado, ¿te gustaría agendar tu asesoría gratuita ahora? Es una excelente oportunidad para que podamos ayudarte específicamente con tus necesidades de inteligencia artificial. 🚀\n\n¿Cuándo te vendría bien programar tu consulta gratuita?"
            else:
                session['estado'] = 'conversacion'
                return f"👋 ¡Hola de nuevo, {nombre_encontrado}! Qué gusto verte otra vez. ¿En qué puedo ayudarte hoy? 😊"
        else:
            session['datos_usuario']['correo'] = correo
            session['estado'] = 'recolectar_datos'
            return "✨ ¡Bienvenido a ITELSA IA! Eres un usuario nuevo, vamos a registrarte.\n👤 ¿Cuál es tu nombre completo?"
    
    # Recolectar datos de usuario nuevo
    elif session['estado'] == 'recolectar_datos':
        datos = session['datos_usuario']
        
        if not datos.get('nombre'):
            datos['nombre'] = mensaje.strip()
            return "📱 ¿Cuál es tu número de contacto?"
        
        elif not datos.get('telefono'):
            datos['telefono'] = mensaje.strip()
            return "💼 ¿Qué servicio de ITELSA IA te interesa?"
        
        elif not datos.get('servicio'):
            datos['servicio'] = mensaje.strip()
            return "📝 ¿Deseas dejar algún comentario adicional?"
        
        elif not datos.get('comentario'):
            datos['comentario'] = mensaje.strip()
            # Mostrar confirmación
            confirmacion = f"✅ Confirma tus datos:\n👤 Nombre: {datos['nombre']}\n📧 Correo: {datos['correo']}\n📱 Teléfono: {datos['telefono']}\n💼 Servicio: {datos['servicio']}\n📝 Comentario: {datos['comentario']}\n\n¿Son correctos estos datos? (sí/no):"
            session['estado'] = 'confirmar_datos'
            return confirmacion
    
    # Confirmar datos
    elif session['estado'] == 'confirmar_datos':
        if mensaje.lower() in ["sí", "si", "s"]:
            datos = session['datos_usuario']
            resultado = guardar_datos(
                datos['nombre'], 
                datos['correo'], 
                datos['telefono'], 
                datos['servicio'], 
                datos['comentario']
            )
            
            if resultado:
                session['datos_usuario']['es_nuevo'] = True
                session['estado'] = 'conversacion'
                return f"✅ ¡Datos registrados con éxito! Ahora puedes hablar con el agente.\n\n¡Excelente {datos['nombre']}! Ya tienes tu cuenta creada con nosotros. 🎉\n\nCuéntame: ¿qué aspecto específico de nuestros servicios de inteligencia artificial te interesa más? ¿Automatización de procesos, análisis de datos, chatbots inteligentes o consultoría estratégica? 🤖"
            else:
                return "❌ Error al guardar datos. Por favor, intenta nuevamente enviando tu correo electrónico."
        else:
            session['estado'] = 'recolectar_datos'
            session['datos_usuario'] = {'correo': session['datos_usuario']['correo']}
            return "❌ Registro cancelado. Volviendo al inicio...\n👤 ¿Cuál es tu nombre completo?"
    
    # Conversación principal
    elif session['estado'] == 'conversacion':
        return procesar_conversacion_principal(session, mensaje)
    
    return "❌ Ha ocurrido un error. Por favor, envía tu correo electrónico para comenzar."

def procesar_conversacion_principal(session, mensaje):
    """Procesa la conversación principal del usuario"""
    datos_usuario = session['datos_usuario']
    
    # Detectar intención de agendamiento
    if detectar_solicitud_agendamiento(mensaje):
        es_segunda_oportunidad = session.get('es_segunda_oportunidad', False)
        es_usuario_nuevo = datos_usuario.get('es_nuevo', False)
        
        if es_segunda_oportunidad:
            return "¡Qué excelente decisión! 🌟 Me alegra mucho que quieras aprovechar esta oportunidad. ¿Cuál sería tu fecha y hora preferida? Nuestro horario es de lunes a viernes de 8:00am a 5:00pm."
        elif es_usuario_nuevo:
            return "¡Fantástico! 🎉 Me emociona que quieras aprovechar tu asesoría gratuita. ¿Cuál sería tu fecha y hora preferida? Nuestro horario es de lunes a viernes de 8:00am a 5:00pm."
        else:
            return "¡Por supuesto! Estaré encantado de ayudarte a agendar una nueva asesoría. ¿Cuál sería tu fecha y hora preferida?"
    
    # Detectar rechazo de asesoría
    if detectar_rechazo_asesoria(mensaje):
        es_segunda_oportunidad = session.get('es_segunda_oportunidad', False)
        
        if es_segunda_oportunidad:
            return "Lo entiendo perfectamente, respeto tu decisión. Sabes que siempre estaremos aquí cuando necesites nuestros servicios. ¡Que tengas un excelente día! 😊"
        else:
            registrar_rechazo_asesoria(datos_usuario['correo'], "Usuario nuevo rechazó asesoría gratuita")
            return "Entiendo perfectamente, no hay problema. La oferta de tu asesoría gratuita seguirá disponible cuando estés listo. ¡Que tengas un excelente día! 😊"
    
    # Detectar fecha y hora en el mensaje
    fecha, hora = extraer_fecha_hora(mensaje)
    if fecha and hora:
        resultado = agendar_en_calendar(
            datos_usuario['nombre'], 
            datos_usuario['correo'], 
            datos_usuario.get('telefono', ''), 
            fecha, 
            hora
        )
        
        respuesta = generar_mensaje_amigable(
            resultado, 
            fecha, 
            hora, 
            datos_usuario['nombre'],
            session.get('es_segunda_oportunidad', False),
            datos_usuario.get('es_nuevo', False),
            datos_usuario['correo']
        )
        
        return respuesta
    
    # Usar OpenAI para respuestas generales
    return procesar_conversacion_llm(mensaje, session)

@app.route("/", methods=["GET"])
def home():
    return jsonify({
        "status": "ITELSA IA Agent is running",
        "version": "1.0.0",
        "endpoints": ["/webhook"]
    })

@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "healthy", "timestamp": datetime.now().isoformat()})

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)