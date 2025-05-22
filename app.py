# app.py - Versión Producción Limpia
import os
import re
from dotenv import load_dotenv
from openai import OpenAI
from datetime import datetime, timedelta
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
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# Variables globales para manejar el estado del usuario
usuario_actual = {}
pendiente_confirmacion = {}
agendamiento_exitoso = False
pregunto_sobre_asesoria = False
es_segunda_oportunidad = False

def es_correo_valido(correo):
    patron = r'^[\w\.-]+@[\w\.-]+\.\w{2,4}$'
    return re.match(patron, correo)

def recolectar_datos_usuario():
    global usuario_actual, es_segunda_oportunidad
    
    print("\n🤖 ¡Hola! Soy el asistente de ITELSA IA.")
    print("📩 Para ayudarte mejor, por favor ingresa tu correo electrónico.\n")

    while True:
        correo = input("📧 ¿Cuál es tu correo electrónico?: ").strip()
        
        if not es_correo_valido(correo):
            print("❌ El correo electrónico no es válido. Inténtalo nuevamente.")
            continue
        
        nombre_encontrado = verificar_usuario(correo)
        
        if nombre_encontrado:
            estado_asesoria = verificar_estado_asesoria_usuario(correo)
            
            if estado_asesoria['tiene_rechazo'] and not estado_asesoria['tiene_cita_exitosa']:
                print(f"👋 ¡Hola de nuevo, {nombre_encontrado}! Qué gusto verte otra vez.")
                
                usuario_actual = {
                    'nombre': nombre_encontrado,
                    'correo': correo,
                    'es_nuevo': False,
                    'telefono': None
                }
                es_segunda_oportunidad = True
                iniciar_chat_llm()
                return
            else:
                print(f"👋 ¡Hola de nuevo, {nombre_encontrado}! Qué gusto verte otra vez.")
                usuario_actual = {
                    'nombre': nombre_encontrado,
                    'correo': correo,
                    'es_nuevo': False,
                    'telefono': None
                }
                es_segunda_oportunidad = False
                iniciar_chat_llm()
                return
        else:
            print("✨ ¡Bienvenido a ITELSA IA! Eres un usuario nuevo, vamos a registrarte.")
            es_segunda_oportunidad = False
            break
    
    nombre = input("👤 ¿Cuál es tu nombre completo?: ").strip()
    telefono = input("📱 ¿Cuál es tu número de contacto?: ").strip()
    servicio = input("💼 ¿Qué servicio de ITELSA IA te interesa?: ").strip()
    comentario = input("📝 ¿Deseas dejar algún comentario adicional?: ").strip()

    print("\n✅ Confirma tus datos:")
    print(f"👤 Nombre: {nombre}\n📧 Correo: {correo}\n📱 Teléfono: {telefono}\n💼 Servicio: {servicio}\n📝 Comentario: {comentario}")

    confirmacion = input("\n¿Son correctos estos datos? (sí/no): ").strip().lower()
    if confirmacion in ["sí", "si", "s"]:
        resultado = guardar_datos(nombre, correo, telefono, servicio, comentario)
        if resultado:
            print("\n✅ ¡Datos registrados con éxito! Ahora puedes hablar con el agente.\n")
            
            usuario_actual = {
                'nombre': nombre,
                'correo': correo,
                'es_nuevo': True,
                'telefono': telefono
            }
            iniciar_chat_llm()
        else:
            print("\n❌ Error al guardar datos. Intenta nuevamente.")
            recolectar_datos_usuario()
    else:
        print("\n❌ Registro cancelado. Volviendo al inicio...")
        recolectar_datos_usuario()

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

def detectar_seleccion_opcion(texto, horarios_disponibles):
    texto_lower = texto.lower()
    
    patrones_seleccion = [
        r'opci[óo]n\s*(\d+)',
        r'la\s*(\d+)',
        r'el\s*(\d+)',
        r'n[úu]mero\s*(\d+)',
        r'^(\d+)$',
        r'^\s*(\d+)\s*$'
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
    
    if any(palabra in texto_lower for palabra in ['sí', 'si', 'ok', 'está bien', 'me parece bien', 'perfecto', 'dale', 'confirmo']):
        if len(horarios_disponibles) == 1:
            return horarios_disponibles[0]
    
    return None

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

def detectar_respuesta_simple(texto):
    texto_lower = texto.lower().strip()
    
    if any(palabra in texto_lower for palabra in ['sí', 'si', 'yes', 'claro', 'por favor', 'dame información', 'me gustaría', 'quisiera', 'necesito', 'tengo preguntas']):
        return 'afirmativa'
    
    if any(palabra in texto_lower for palabra in ['no', 'nada', 'gracias', 'está bien', 'perfecto', 'listo', 'todo bien', 'no necesito']):
        return 'negativa'
    
    return 'otra'

def generar_mensaje_amigable(resultado, fecha, hora):
    global usuario_actual, es_segunda_oportunidad
    
    if resultado['disponible']:
        fecha_amigable = formatear_fecha_amigable(fecha)
        
        if es_segunda_oportunidad:
            observaciones = "Asesoría gratuita agendada con éxito - Segunda oportunidad (usuario cambió de opinión)"
        elif usuario_actual['es_nuevo']:
            observaciones = "Asesoría gratuita agendada con éxito - Usuario nuevo"
        else:
            observaciones = "Asesoría agendada - Usuario existente"
        
        if usuario_actual['correo']:
            registrar_agendamiento_completo(
                usuario_actual['correo'], 
                fecha, 
                hora, 
                observaciones
            )
        
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
            global pendiente_confirmacion
            pendiente_confirmacion[fecha_amigable] = {
                'fecha': fecha,
                'horarios': resultado['horarios_alternativos']
            }
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
            pendiente_confirmacion[fecha_amigable] = {
                'fecha': fecha_alt,
                'horarios': resultado['horarios_alternativos']
            }
        return mensaje
    
    elif motivo == 'horario_ocupado':
        fecha_amigable = formatear_fecha_amigable(fecha)
        mensaje = f"Ese horario ya está ocupado para el {fecha_amigable}, pero tengo otras opciones disponibles: 🕐\n\n"
        if resultado['horarios_alternativos']:
            for i, horario in enumerate(resultado['horarios_alternativos'], 1):
                mensaje += f"   {i}. {horario}\n"
            mensaje += "\n¿Cuál prefieres? Solo dime el número de la opción."
            pendiente_confirmacion[fecha_amigable] = {
                'fecha': fecha,
                'horarios': resultado['horarios_alternativos']
            }
        else:
            mensaje += "Por favor, elígenos otro horario y verificaré la disponibilidad inmediatamente."
        return mensaje
    
    else:
        return "Ups, parece que hubo un pequeño inconveniente. ¿Podrías intentar con otro horario? Estoy aquí para ayudarte a encontrar la cita perfecta. 😊"

def iniciar_chat_llm():
    global pendiente_confirmacion, agendamiento_exitoso, pregunto_sobre_asesoria, usuario_actual, es_segunda_oportunidad
    
    pendiente_confirmacion = {}
    agendamiento_exitoso = False
    pregunto_sobre_asesoria = False
    
    nombre_usuario = usuario_actual['nombre']
    correo = usuario_actual['correo']
    es_usuario_nuevo = usuario_actual['es_nuevo']
    telefono = usuario_actual.get('telefono')
    
    url_cliente = "https://itelsaia.com"
    contenido_web = extraer_contenido_web(url_cliente) or ""

    try:
        with open("contenido_fijo.txt", "r", encoding="utf-8") as file:
            contenido_manual = file.read()
    except FileNotFoundError:
        contenido_manual = "No hay contenido manual cargado."

    contexto_completo = contenido_manual + "\n\n" + contenido_web

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
        mensaje_inicial = f"¡Hola de nuevo, {nombre_usuario}! 👋 Qué gusto verte otra vez.\n\nVeo que aún no has podido aprovechar tu primera asesoría gratuita con ITELSA IA. ✨ Las circunstancias pueden haber cambiado, ¿te gustaría agendar tu asesoría gratuita ahora? Es una excelente oportunidad para que podamos ayudarte específicamente con tus necesidades de inteligencia artificial. 🚀\n\n¿Cuándo te vendría bien programar tu consulta gratuita?"
        
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
        mensaje_inicial = f"¡Excelente {nombre_usuario}! Ya tienes tu cuenta creada con nosotros. 🎉\n\nCuéntame: ¿qué aspecto específico de nuestros servicios de inteligencia artificial te interesa más? ¿Automatización de procesos, análisis de datos, chatbots inteligentes o consultoría estratégica? 🤖"
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
        mensaje_inicial = f"¡Hola {nombre_usuario}! Es un placer tenerte de vuelta. ¿En qué puedo ayudarte hoy? 😊"

    print(f"🤖 ITELSA IA: {mensaje_inicial}")
    
    mensajes = [{"role": "system", "content": prompt_sistema}]

    while True:
        entrada = input(f"\n{nombre_usuario}: ").strip()
        
        if entrada.lower() in ["salir", "terminar", "adiós", "adios"]:
            if es_segunda_oportunidad:
                print("\n🤖 ITELSA IA: ¡Gracias por darme la oportunidad de conversar contigo! Estaré aquí cuando estés listo. ¡Hasta pronto! 👋")
            elif es_usuario_nuevo:
                print("\n🤖 ITELSA IA: ¡Gracias por conocer ITELSA IA! Recuerda que tu asesoría gratuita te está esperando. ¡Hasta pronto! 👋")
            else:
                print("\n🤖 ITELSA IA: ¡Gracias por contactarnos! Siempre estamos aquí para apoyarte. ¡Que tengas un excelente día! 👋")
            break

        entrada_procesada = False

        if agendamiento_exitoso:
            tipo_respuesta = detectar_respuesta_simple(entrada)
            
            if tipo_respuesta == 'negativa':
                print("\n🤖 ITELSA IA: ¡Perfecto! Ha sido un placer ayudarte. Nos vemos en tu asesoría. ¡Que tengas un excelente día! 🌟")
                agendamiento_exitoso = False
                entrada_procesada = True
            elif tipo_respuesta == 'afirmativa':
                print("\n🤖 ITELSA IA: ¡Genial! Estaré encantado de ayudarte. ¿Qué más te gustaría saber sobre nuestros servicios?")
                agendamiento_exitoso = False
                entrada_procesada = True
            else:
                agendamiento_exitoso = False

        if not entrada_procesada and pendiente_confirmacion:
            for fecha_amigable, datos in pendiente_confirmacion.items():
                hora_seleccionada = detectar_seleccion_opcion(entrada, datos['horarios'])
                if hora_seleccionada:
                    fecha = datos['fecha']
                    resultado = agendar_en_calendar(nombre_usuario, correo, telefono, fecha, hora_seleccionada)
                    respuesta_amigable = generar_mensaje_amigable(resultado, fecha, hora_seleccionada)
                    print(f"\n🤖 ITELSA IA: {respuesta_amigable}")
                    pendiente_confirmacion = {}
                    
                    if resultado['disponible']:
                        agendamiento_exitoso = True
                    
                    entrada_procesada = True
                    break

        if not entrada_procesada and correo:
            fecha, hora = extraer_fecha_hora(entrada)
            if fecha and hora:
                resultado = agendar_en_calendar(nombre_usuario, correo, telefono, fecha, hora)
                respuesta_amigable = generar_mensaje_amigable(resultado, fecha, hora)
                print(f"\n🤖 ITELSA IA: {respuesta_amigable}")
                
                if resultado['disponible']:
                    agendamiento_exitoso = True
                
                entrada_procesada = True

        if not entrada_procesada and correo:
            if detectar_solicitud_agendamiento(entrada):
                if es_segunda_oportunidad:
                    print("\n🤖 ITELSA IA: ¡Qué excelente decisión! 🌟 Me alegra mucho que quieras aprovechar esta oportunidad. ¿Cuál sería tu fecha y hora preferida? Nuestro horario es de lunes a viernes de 8:00am a 5:00pm.")
                    pregunto_sobre_asesoria = True
                elif es_usuario_nuevo:
                    print("\n🤖 ITELSA IA: ¡Fantástico! 🎉 Me emociona que quieras aprovechar tu asesoría gratuita. ¿Cuál sería tu fecha y hora preferida? Nuestro horario es de lunes a viernes de 8:00am a 5:00pm.")
                    pregunto_sobre_asesoria = True
                else:
                    print("\n🤖 ITELSA IA: ¡Por supuesto! Estaré encantado de ayudarte a agendar una nueva asesoría. ¿Cuál sería tu fecha y hora preferida?")
                entrada_procesada = True

        if not entrada_procesada and (es_usuario_nuevo or es_segunda_oportunidad):
            if detectar_rechazo_asesoria(entrada):
                if es_segunda_oportunidad:
                    print("\n🤖 ITELSA IA: Lo entiendo perfectamente, respeto tu decisión. Sabes que siempre estaremos aquí cuando necesites nuestros servicios. ¡Que tengas un excelente día! 😊")
                    entrada_procesada = True
                else:
                    registrar_rechazo_asesoria(correo, "Usuario nuevo rechazó asesoría gratuita")
                    pregunto_sobre_asesoria = False
                    print("\n🤖 ITELSA IA: Entiendo perfectamente, no hay problema. La oferta de tu asesoría gratuita seguirá disponible cuando estés listo. ¡Que tengas un excelente día! 😊")
                    entrada_procesada = True

        if not entrada_procesada:
            mensajes.append({"role": "user", "content": entrada})

            try:
                respuesta = client.chat.completions.create(
                    model="gpt-3.5-turbo",
                    messages=mensajes,
                    temperature=0.7,
                    max_tokens=600
                )
                reply = respuesta.choices[0].message.content
                print(f"\n🤖 ITELSA IA: {reply}")
                mensajes.append({"role": "assistant", "content": reply})
                
                if es_usuario_nuevo and not es_segunda_oportunidad:
                    palabras_agendamiento = [
                        'agendar', 'cita', 'asesoría', 'reunión', 'consulta',
                        'cuando', 'programar', 'te interesa', 'quisieras',
                        'gratuita', 'sin costo', 'primera vez', 'disponible'
                    ]
                    
                    ya_pregunto = any(palabra in reply.lower() for palabra in palabras_agendamiento)
                    
                    if ya_pregunto:
                        pregunto_sobre_asesoria = True
                    else:
                        import random
                        preguntas_persuasivas = [
                            "Por cierto, ¿te gustaría agendar tu primera asesoría gratuita para que podamos ayudarte específicamente con tu proyecto?",
                            "¿Cuándo podrías tener 30 minutos para una consulta gratuita personalizada donde analizaríamos tu caso específico?",
                            "¿Te interesa programar una reunión sin costo para que un experto revise tu situación particular?"
                        ]
                        
                        pregunta_elegida = random.choice(preguntas_persuasivas)
                        print(f"\n🤖 ITELSA IA: {pregunta_elegida}")
                        mensajes.append({"role": "assistant", "content": pregunta_elegida})
                        pregunto_sobre_asesoria = True
                    
            except Exception as e:
                print(f"\n🤖 ITELSA IA: Disculpa, tuve un pequeño problema técnico. ¿Puedes repetir tu mensaje? 😊")

if __name__ == "__main__":
    print("="*60)
    print("🚀 SISTEMA DE AGENTE IA - ITELSA IA")
    print("="*60)
    recolectar_datos_usuario()