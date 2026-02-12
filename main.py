import os
import json
import time
import requests
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from flask import Flask, request, jsonify
from datetime import datetime, timedelta

app = Flask(__name__)

# --- VARIABLES DE ENTORNO ---
TOKEN_WHATSAPP = os.environ.get("TOKEN_WHATSAPP")
NUMERO_ID = os.environ.get("NUMERO_ID")  
VERIFY_TOKEN = os.environ.get("VERIFY_TOKEN")
GOOGLE_JSON = os.environ.get("GOOGLE_CREDENTIALS")

# --- CONFIGURACIÓN ---
BASE_URL = "https://raw.githubusercontent.com/invpeluches2812-coder/bot-whatsapp/main/multimedia"
IMG_LOGO = f"{BASE_URL}/logo.jpg"
AUDIO_SALUDO = f"{BASE_URL}/saludo.mp3"
IMG_INI_VE = f"{BASE_URL}/plan_ini_ve.jpg"
IMG_MED_VE = f"{BASE_URL}/plan_med_ve.jpg"
IMG_AVA_VE = f"{BASE_URL}/plan_ava_ve.jpg"
IMG_INI_CL = f"{BASE_URL}/plan_ini_cl.jpg"
IMG_MED_CL = f"{BASE_URL}/plan_med_cl.jpg"
IMG_AVA_CL = f"{BASE_URL}/plan_ava_cl.jpg"
IMG_DISENO = f"{BASE_URL}/catalogo_diseno.jpg" 

# TU NÚMERO PERSONAL (Aquí llegarán los códigos)
NUMERO_ADMIN = "584265168669" 

# --- FUNCIONES ---
usuarios_activos = {}
def es_spam(telefono):
    ahora = time.time()
    ultimo = usuarios_activos.get(telefono, 0)
    if ahora - ultimo < 2: return True
    usuarios_activos[telefono] = ahora
    return False

def registrar_lead(nombre, telefono, pais, interes):
    try:
        if not GOOGLE_JSON: return
        creds_dict = json.loads(GOOGLE_JSON)
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
        client = gspread.authorize(creds)
        sheet = client.open("Clientes_Bot").sheet1
        hora_vzla = datetime.utcnow() - timedelta(hours=4)
        sheet.append_row([hora_vzla.strftime("%Y-%m-%d"), hora_vzla.strftime("%H:%M:%S"), nombre, telefono, pais, interes])
    except Exception as e: print(f"Error Sheets: {e}")

def es_horario_laboral():
    hora = (datetime.utcnow() - timedelta(hours=4)).hour
    return 8 <= hora < 22

def enviar(telefono, tipo, contenido, caption=None):
    url = f"https://graph.facebook.com/v19.0/{NUMERO_ID}/messages"
    headers = {"Authorization": f"Bearer {TOKEN_WHATSAPP}", "Content-Type": "application/json"}
    data = {"messaging_product": "whatsapp", "to": telefono, "type": tipo}
    
    if tipo == "text": data["text"] = {"body": contenido}
    elif tipo == "image": 
        data["image"] = {"link": contenido}
        if caption: data["image"]["caption"] = caption
    elif tipo == "audio": data["audio"] = {"link": contenido}
    elif tipo == "interactive": data["interactive"] = contenido
    elif tipo == "reaction": 
        data["recipient_type"] = "individual"
        data["reaction"] = {"message_id": contenido, "emoji": caption}

    try: requests.post(url, headers=headers, json=data)
    except: pass

def marcar_leido(msg_id):
    url = f"https://graph.facebook.com/v19.0/{NUMERO_ID}/messages"
    headers = {"Authorization": f"Bearer {TOKEN_WHATSAPP}", "Content-Type": "application/json"}
    try: requests.post(url, headers=headers, json={"messaging_product": "whatsapp", "status": "read", "message_id": msg_id})
    except: pass

def gestionar_humano(numero, nombre, pais):
    registrar_lead(nombre, numero, pais, "🚨 Pidió Asesor")
    link = f"https://wa.me/{NUMERO_ADMIN}"
    if es_horario_laboral():
        enviar(numero, "text", f"✅ He avisado a mi director. Escribe aquí si es urgente: {link}")
        enviar(NUMERO_ADMIN, "text", f"🚨 *LEAD {pais.upper()}*\n👤 {nombre}\n📱 {numero}\n💬 Pide humano.")
    else:
        enviar(numero, "text", f"🌙 Estamos descansando. Te escribiremos mañana. Urgencias: {link}")
        enviar(NUMERO_ADMIN, "text", f"💤 *LEAD NOCTURNO*\n👤 {nombre}")

# --- RUTAS PRINCIPALES ---
def menu_pais(telefono, nombre):
    enviar(telefono, "audio", AUDIO_SALUDO)
    time.sleep(1)
    enviar(telefono, "image", IMG_LOGO)
    btns = {"type": "button", "body": {"text": f"👋 Hola {nombre}. Selecciona tu país:"}, "action": {"buttons": [{"type": "reply", "reply": {"id": "pais_ve", "title": "🇻🇪 Venezuela"}}, {"type": "reply", "reply": {"id": "pais_cl", "title": "🇨🇱 Chile"}}]}}
    enviar(telefono, "interactive", btns)

def menu_servicios(telefono, pais_code):
    bandera = "🇻🇪" if pais_code == "ve" else "🇨🇱"
    btns = {"type": "button", "body": {"text": f"{bandera} Menú {pais_code.upper()}"}, "action": {"buttons": [{"type": "reply", "reply": {"id": f"mkt_{pais_code}", "title": "📱 Redes"}}, {"type": "reply", "reply": {"id": f"dsn_{pais_code}", "title": "🎨 Diseño"}}, {"type": "reply", "reply": {"id": f"inf_{pais_code}", "title": "❓ Pagos"}}]}}
    enviar(telefono, "interactive", btns)

def submenu_planes(telefono, pais):
    btns = {"type": "button", "body": {"text": "Planes Redes"}, "action": {"buttons": [{"type": "reply", "reply": {"id": f"plan_ini_{pais}", "title": "🌱 Inicial"}}, {"type": "reply", "reply": {"id": f"plan_med_{pais}", "title": "🚀 Medio"}}, {"type": "reply", "reply": {"id": f"plan_ava_{pais}", "title": "💎 Avanzado"}}]}}
    enviar(telefono, "interactive", btns)

# --- SERVIDOR ---
@app.route("/webhook", methods=["GET"])
def verificar():
    if request.args.get("hub.verify_token") == VERIFY_TOKEN: return request.args.get("hub.challenge"), 200
    return "Error", 403

@app.route("/webhook", methods=["POST"])
def recibir():
    try:
        body = request.json
        if not body or "entry" not in body: return jsonify({"status": "error"}), 400
        entry = body["entry"][0]["changes"][0]["value"]
        
        if "messages" in entry:
            msg = entry["messages"][0]
            numero = msg["from"]
            msg_id = msg["id"]
            nombre = entry["contacts"][0]["profile"]["name"]
            
            if es_spam(numero): return "OK", 200
            marcar_leido(msg_id)

            if msg["type"] == "text":
                txt = msg["text"]["body"].lower()
                
                # --- AQUÍ ESTÁ EL CÓDIGO HÍBRIDO ---
                # 1. IMPRIMIR EN PANTALLA NEGRA (Con flush=True para que salga rápido)
                print(f"📩 MENSAJE SECRETO: {msg['text']['body']}", flush=True)
                # -----------------------------------

                # 1. SALUDO INICIAL
                if any(x in txt for x in ["hola", "info", "precio", "buenas"]):
                    enviar(numero, "reaction", msg_id, "👋")
                    menu_pais(numero, nombre)
                    registrar_lead(nombre, numero, "Inicio", "Saludo")
                
                # 2. PEDIR HUMANO
                elif "asesor" in txt or "humano" in txt:
                    gestionar_humano(numero, nombre, "General")
                
                # 3. REENVIAR A TU WHATSAPP (Repetidor)
                else:
                    mensaje_real = msg["text"]["body"]
                    if numero != NUMERO_ADMIN:
                        enviar(NUMERO_ADMIN, "text", f"📩 *MENSAJE DESCONOCIDO RECIBIDO*\n👤 De: {nombre} ({numero})\n💬 Dice: {mensaje_real}")

            elif msg["type"] == "interactive":
                btn = msg["interactive"]["button_reply"]["id"]
                enviar(numero, "reaction", msg_id, "✅")

                if btn == "pais_ve": 
                    menu_servicios(numero, "ve")
                    registrar_lead(nombre, numero, "Venezuela", "Selección País")
                elif btn == "pais_cl": 
                    menu_servicios(numero, "cl")
                    registrar_lead(nombre, numero, "Chile", "Selección País")
                
                elif "mkt_" in btn:
                    pais = "ve" if "_ve" in btn else "cl"
                    submenu_planes(numero, pais)

                elif "plan_" in btn:
                    pais = "ve" if "_ve" in btn else "cl"
                    img = IMG_INI_VE if "_ini_" in btn and pais == "ve" else (IMG_INI_CL if "_ini_" in btn else (IMG_MED_VE if "_med_" in btn and pais == "ve" else (IMG_MED_CL if "_med_" in btn else (IMG_AVA_VE if "_ava_" in btn and pais == "ve" else IMG_AVA_CL))))
                    enviar(numero, "image", img, caption="Mira el detalle en la imagen 👆")
                    botones = {"type": "button", "body": {"text": "¿Qué deseas hacer?"}, "action": {"buttons": [{"type": "reply", "reply": {"id": f"humano_{pais}", "title": "🙋 Contratar"}}]}}
                    enviar(numero, "interactive", botones)
                    registrar_lead(nombre, numero, "VE" if pais=="ve" else "CL", btn)

                elif "dsn_" in btn:
                    pais = "ve" if "_ve" in btn else "cl"
                    enviar(numero, "image", IMG_DISENO, caption="🎨 Catálogo de Diseño")
                    btns = {"type": "button", "body": {"text": "¿Te interesa?"}, "action": {"buttons": [{"type": "reply", "reply": {"id": f"humano_{pais}", "title": "🙋 Cotizar"}}]}}
                    enviar(numero, "interactive", btns)
                    registrar_lead(nombre, numero, "VE" if pais=="ve" else "CL", "Diseño")

                elif "inf_" in btn:
                    pais = "ve" if "_ve" in btn else "cl"
                    txt = "🇻🇪 Pagos VE: Binance, Pago Móvil" if pais == "ve" else "🇨🇱 Pagos CL: Banco Estado, RUT"
                    enviar(numero, "text", txt)
                    btns = {"type": "button", "body": {"text": "¿Dudas?"}, "action": {"buttons": [{"type": "reply", "reply": {"id": f"humano_{pais}", "title": "🙋 Hablar con Asesor"}}]}}
                    enviar(numero, "interactive", btns)
                
                elif "humano_" in btn:
                    pais = "Venezuela" if "_ve" in btn else "Chile"
                    gestionar_humano(numero, nombre, pais)

    except Exception as e:
        print(f"Error: {e}")
        return jsonify({"status": "error"}), 500
    return "OK", 200

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=5000)
