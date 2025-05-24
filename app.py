 app.py - Versión Mínima para WhatsApp Webhook
import os
from flask import Flask, request, jsonify
from datetime import datetime

# Inicializar Flask
app = Flask(__name__)

# Configuración básica
WHATSAPP_VERIFY_TOKEN = os.getenv("WHATSAPP_VERIFY_TOKEN", "mi_token_super_seguro_456")

@app.route('/webhook', methods=['GET'])
def verify_webhook():
    """Verificación del webhook de WhatsApp"""
    try:
        mode = request.args.get('hub.mode')
        token = request.args.get('hub.verify_token')
        challenge = request.args.get('hub.challenge')
        
        print(f"Webhook verification: mode={mode}, token={token}, challenge={challenge}")
        
        if mode == 'subscribe' and token == WHATSAPP_VERIFY_TOKEN:
            print("Webhook verificado exitosamente")
            return challenge
        else:
            print(f"Fallo en verificación. Token esperado: {WHATSAPP_VERIFY_TOKEN}, Token recibido: {token}")
            return 'Forbidden', 403
            
    except Exception as e:
        print(f"Error en verificación: {str(e)}")
        return 'Error', 500

@app.route('/webhook', methods=['POST'])
def handle_webhook():
    """Maneja mensajes entrantes de WhatsApp"""
    try:
        data = request.get_json()
        print(f"Mensaje recibido: {data}")
        
        # Por ahora solo registramos el mensaje
        # Aquí puedes agregar la lógica del chatbot después
        
        return jsonify({'status': 'success'}), 200
        
    except Exception as e:
        print(f"Error procesando webhook: {str(e)}")
        return jsonify({'status': 'error'}), 500

@app.route('/health', methods=['GET'])
def health_check():
    """Endpoint para verificar estado del servicio"""
    return jsonify({
        'status': 'healthy',
        'timestamp': datetime.now().isoformat(),
        'service': 'ITELSA IA Webhook'
    }), 200

@app.route('/')
def home():
    """Página principal"""
    return jsonify({
        'message': 'ITELSA IA WhatsApp Webhook',
        'status': 'running',
        'endpoints': {
            'webhook': '/webhook',
            'health': '/health'
        }
    })

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)