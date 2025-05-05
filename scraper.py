import requests
from bs4 import BeautifulSoup

def extraer_contenido_web(url):
    try:
        # Enviar solicitud a la página
        response = requests.get(url)
        response.raise_for_status()

        # Procesar el contenido con BeautifulSoup
        soup = BeautifulSoup(response.text, 'html.parser')

        # Extraer solo el texto visible (evitar scripts, estilos)
        for script in soup(["script", "style"]):
            script.decompose()

        texto = soup.get_text(separator=' ', strip=True)
        return texto

    except Exception as e:
        print(f"Error al extraer contenido: {str(e)}")
        return None

if __name__ == "__main__":
    url = "https://itelsaia.com"  # Cambia esto si quieres probar otra página
    contenido = extraer_contenido_web(url)
    if contenido:
        # Guardamos el contenido en un archivo para usarlo después
        with open('contenido_web.txt', 'w', encoding='utf-8') as f:
            f.write(contenido)
        print("✅ Contenido extraído y guardado en 'contenido_web.txt'")
    else:
        print("❌ No se pudo extraer el contenido.")
