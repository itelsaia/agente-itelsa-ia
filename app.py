# conversacion_agente_llm.py - VERSIÓN MEJORADA

import re
import os
import random
from dotenv import load_dotenv
from openai import OpenAI
from guardar_datos_google_sheets import guardar_datos

# Cargar las variables de entorno desde el archivo .env
load_dotenv()

# Crear cliente OpenAI
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

def es_correo_valido(correo):
    """
    Verifica si el correo electrónico ingresado es válido mediante expresión regular.
    """
    patron = r'^[\w\.-]+@[\w\.-]+\.\w{2,4}$'
    return re.match(patron, correo)

def es_telefono_valido(telefono):
    """
    Verifica si el teléfono es numérico y tiene una longitud aceptable.
    """
    return telefono.isdigit() and (7 <= len(telefono) <= 15)

def recolectar_datos_usuario():
    """
    Flujo inicial de conversación para recolectar datos, validarlos, 
    guardar en Google Sheets y luego permitir conversación libre con GPT.
    """

    print("\n🤖 ¡Hola! Soy el asistente de ITELSA IA.")
    print("🎯 Para ofrecerte la mejor ayuda, por favor regístrate brevemente. 😊\n")

    # Solicitud de datos uno por uno
    nombre = input("👤 ¿Cuál es tu nombre completo?: ").strip()

    # Validar correo electrónico
    while True:
        correo = input("📧 ¿Cuál es tu correo electrónico?: ").strip()
        if es_correo_valido(correo):
            break
        else:
            print("⚠️ El correo ingresado no parece válido. Por favor, intenta de nuevo.\n")

    # Validar número de teléfono
    while True:
        telefono = input("📱 ¿Cuál es tu número de contacto?: ").strip()
        if es_telefono_valido(telefono):
            break
        else:
            print("⚠️ El número de teléfono debe ser numérico y tener entre 7 y 15 dígitos.\n")

    servicio = input("💼 ¿Qué servicio de ITELSA IA te interesa?: ").strip()
    comentario = input("📝 ¿Deseas dejar algún comentario adicional?: ").strip()

    # Confirmación de datos
    print("\n🔎 Confirma tus datos ingresados:")
    print(f"👤 Nombre: {nombre}")
    print(f"📧 Correo: {correo}")
    print(f"📱 Teléfono: {telefono}")
    print(f"💼 Servicio de interés: {servicio}")
    print(f"📝 Comentario: {comentario}\n")

    confirmacion = input("✅ ¿Son correctos estos datos? (sí/no): ").strip().lower()

    if confirmacion in ["sí", "si", "s"]:
        # Guardar datos en Sheets
        guardar_datos(
            nombre_completo=nombre,
            correo=correo,
            telefono=telefono,
            servicio_interesado=servicio,
            comentario_mensaje=comentario
        )
        print("\n🎉 ¡Tus datos han sido registrados exitosamente! Ahora podemos conversar.\n")
        iniciar_chat_llm(nombre)
    else:
        print("\n❌ Registro cancelado. Puedes reiniciar el formulario si deseas intentarlo de nuevo.\n")

def iniciar_chat_llm(nombre_usuario):
    """
    Inicia una conversación libre con el modelo GPT, usando un contexto inicial amigable.
    """
    mensajes = [
        {"role": "system", "content": f"Eres un asistente amigable, experto en IA y servicios digitales de ITELSA IA. Ayuda a {nombre_usuario} de forma cálida y profesional."}
    ]

    while True:
        user_input = input(f"{nombre_usuario}: ").strip()

        if user_input.lower() in ["salir", "terminar", "adiós"]:
            print("\n👋 ¡Gracias por conversar con ITELSA IA! Hasta pronto. 🌟\n")
            break

        mensajes.append({"role": "user", "content": user_input})

        try:
            response = client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=mensajes,
                temperature=0.7,
                max_tokens=500
            )

            reply = response.choices[0].message.content
            print(f"🤖 ITELSA IA: {reply}\n")

            mensajes.append({"role": "assistant", "content": reply})

        except Exception as e:
            print(f"❌ Error al contactar OpenAI: {str(e)}\n")

if __name__ == "__main__":
    recolectar_datos_usuario()
