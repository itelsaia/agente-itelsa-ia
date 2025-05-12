import os
import re
from dotenv import load_dotenv
from openai import OpenAI
from guardar_datos_google_sheets import guardar_datos, verificar_usuario
from scraper import extraer_contenido_web

# Cargar variables de entorno
load_dotenv()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

def es_correo_valido(correo):
    patron = r'^[\w\.-]+@[\w\.-]+\.\w{2,4}$'
    return re.match(patron, correo)

def recolectar_datos_usuario():
    print("\n🤖 ¡Hola! Soy el asistente de ITELSA IA.")
    print("📩 Para ayudarte mejor, por favor ingresa tu correo electrónico.\n")

    correo = input("📧 ¿Cuál es tu correo electrónico?: ").strip()

    # Verificar si el correo ya está registrado
    nombre_encontrado = verificar_usuario(correo)
    if nombre_encontrado:
        print(f"👋 ¡Hola de nuevo, {nombre_encontrado}! Qué gusto verte otra vez.")
        iniciar_chat_llm(nombre_encontrado)
        return

    if not es_correo_valido(correo):
        print("❌ El correo electrónico no es válido. Inténtalo nuevamente.")
        return

    nombre = input("👤 ¿Cuál es tu nombre completo?: ").strip()
    telefono = input("📱 ¿Cuál es tu número de contacto?: ").strip()
    servicio = input("💼 ¿Qué servicio de ITELSA IA te interesa?: ").strip()
    comentario = input("📝 ¿Deseas dejar algún comentario adicional?: ").strip()

    print("\n✅ Confirma tus datos:")
    print(f"👤 Nombre: {nombre}")
    print(f"📧 Correo: {correo}")
    print(f"📱 Teléfono: {telefono}")
    print(f"💼 Servicio: {servicio}")
    print(f"📝 Comentario: {comentario}")

    confirmacion = input("\n¿Son correctos estos datos? (sí/no): ").strip().lower()
    if confirmacion in ["sí", "si", "s"]:
        guardar_datos(nombre, correo, telefono, servicio, comentario)
        print("\n✅ ¡Datos registrados con éxito! Ahora puedes hablar con el agente.\n")
        iniciar_chat_llm(nombre)
    else:
        print("\n❌ Registro cancelado.")

def iniciar_chat_llm(nombre_usuario):
    # Cargar contenido desde scraper (web)
    url_cliente = "https://itelsaia.com"  # 🔁 REEMPLAZAR con la URL del cliente si aplica
    contenido_web = extraer_contenido_web(url_cliente) or ""

    # Cargar contenido manual desde archivo .txt
    try:
        with open("contenido_fijo.txt", "r", encoding="utf-8") as file:
            contenido_manual = file.read()
    except FileNotFoundError:
        contenido_manual = "No hay contenido manual cargado."

    contexto_completo = contenido_manual + "\n\n" + contenido_web

    mensajes = [
        {
            "role": "system",
            "content": f"Eres un asistente amigable de ITELSA IA. Usa esta información para responder a {nombre_usuario}:\n\n{contexto_completo}"
        }
    ]

    while True:
        entrada = input(f"{nombre_usuario}: ").strip()
        if entrada.lower() in ["salir", "terminar", "adiós"]:
            print("👋 ¡Gracias por tu tiempo! Hasta pronto.")
            break

        mensajes.append({"role": "user", "content": entrada})

        try:
            respuesta = client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=mensajes,
                temperature=0.7,
                max_tokens=500
            )
            reply = respuesta.choices[0].message.content
            print(f"🤖 ITELSA IA: {reply}\n")
            mensajes.append({"role": "assistant", "content": reply})
        except Exception as e:
            print(f"❌ Error al contactar OpenAI: {e}")

if __name__ == "__main__":
    recolectar_datos_usuario()
