import os
import json
import gspread
from flask import Flask, request, jsonify
from oauth2client.service_account import ServiceAccountCredentials
import requests
from datetime import datetime

app = Flask(__name__)

# CONFIGURACIÓN DE VARIABLES DESDE RENDER
TOKEN_WHATSAPP = os.environ.get('TOKEN_WHATSAPP')
NUMERO_ID = os.environ.get('NUMERO_ID')
VERIFY_TOKEN = os.environ.get('VERIFY_TOKEN')
GOOGLE_CREDENTIALS = os.environ.get('GOOGLE_CREDENTIALS')

# CONFIGURAR GOOGLE SHEETS
def guardar_en_excel(datos):
    try:
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        creds_dict = json.loads(GOOGLE_CREDENTIALS)
        creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
        client = gspread.authorize(creds)
        # Debe llamarse exactamente como la creamos
        sheet = client.open("Clientes_Bot").sheet1
        sheet.append_row(datos)
        return True
    except Exception as e:
        print(f"Error en Google Sheets: {e}")
        return False

# RUTA PARA QUE FACEBOOK VERIFIQUE EL BOT
@app.route('/webhook', methods=['GET'])
def verificar_webhook():
    token = request.args.get('hub.verify_token')
    challenge = request.args.get('hub.challenge')
    if token == VERIFY_TOKEN:
        return challenge
    return "Token de verificación incorrecto", 403

# RUTA DONDE LLEGAN LOS MENSAJES DE WHATSAPP
@app.route('/webhook', methods=['POST'])
def recibir_mensajes():
    try:
        body = request.get_json()
        entry = body['entry'][0]
        changes = entry['changes'][0]
        value = changes['value']
        
        if 'messages' in value:
            message = value['messages'][0]
            telefono = message['from']
            texto = message.get('text', {}).get('body', '').lower()
            nombre = value.get('contacts', [{}])[0].get('profile', {}).get('name', 'Cliente')

            # LÓGICA DEL BOT: Si el cliente escribe algo
            if texto:
                # 1. Guardar en el Excel
                ahora = datetime.now()
                fecha = ahora.strftime("%Y-%m-%d")
                hora = ahora.strftime("%H:%M:%S")
                # El bot asume país según el código de área (ej: 58 Venezuela, 56 Chile)
                pais = "Venezuela" if telefono.startswith('58') else "Chile" if telefono.startswith('56') else "Otro"
                
                guardar_en_excel([fecha, hora, nombre, telefono, pais, texto])

                # 2. Enviar respuesta automática
                enviar_mensaje_whatsapp(telefono, f"¡Hola {nombre}! 👋 Gracias por escribir a Peluches Marketing. Hemos recibido tu mensaje: '{texto}'. Un asesor te contactará pronto.")

        return jsonify({'status': 'success'}), 200
    except Exception as e:
        print(f"Error procesando mensaje: {e}")
        return jsonify({'status': 'error'}), 500

def enviar_mensaje_whatsapp(telefono, texto):
    url = f"https://graph.facebook.com/v18.0/{NUMERO_ID}/messages"
    headers = {
        "Authorization": f"Bearer {TOKEN_WHATSAPP}",
        "Content-Type": "application/json"
    }
    data = {
        "messaging_product": "whatsapp",
        "to": telefono,
        "type": "text",
        "text": {"body": texto}
    }
    requests.post(url, headers=headers, json=data)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
