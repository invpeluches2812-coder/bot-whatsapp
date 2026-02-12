import os
import json
import time
import requests
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from flask import Flask, request, jsonify
from datetime import datetime, timedelta

app = Flask(__name__)

# --- VARIABLES DE ENTORNO (Configuradas en Render) ---
TOKEN_WHATSAPP = os.environ.get("TOKEN_WHATSAPP")
NUMERO_ID = os.environ.get("NUMERO_ID")  
VERIFY_TOKEN = os.environ.get("VERIFY_TOKEN")
GOOGLE_JSON = os.environ.get("GOOGLE_CREDENTIALS")

# ==========================================
#      ZONA DE EDICIÓN (PELUCHES MARKETING)
# ==========================================

# Repositorio de imágenes (Asegúrate de que existan en la carpeta multimedia de tu GitHub)
BASE_URL = "https://raw.githubusercontent.com/invpeluches2812-coder/bot-whatsapp/main/multimedia"

# Enlaces a imágenes y audios
IMG_LOGO = f"{BASE_URL}/logo.jpg"
AUDIO_SALUDO = f"{BASE_URL}/saludo.mp3"

# Imágenes Venezuela
IMG_INI_VE = f"{BASE_URL}/plan_ini_ve.jpg"
IMG_MED_VE = f"{BASE_URL}/plan_med_ve.jpg"
IMG_AVA_VE = f"{BASE_URL}/plan_ava_ve.jpg"

# Imágenes Chile
IMG_INI_CL = f"{BASE_URL}/plan_ini_cl.jpg"
IMG_MED_CL = f"{BASE_URL}/plan_med_cl.jpg"
IMG_AVA_CL = f"{BASE_URL}/plan_ava_cl.jpg"

# Diseño 
IMG_DISENO = f"{BASE_URL}/catalogo_diseno.jpg" 

# TU NÚMERO PERSONAL (Para recibir alertas)
NUMERO_ADMIN = "584265168669" 

# ==========================================

# --- ANTI-SPAM (Evita que el bot se vuelva loco si escriben muy rápido) ---
usuarios_activos = {}
def es_spam(telefono):
    ahora = time.time()
    ultimo = usuarios_activos.get(telefono, 0)
    if ahora - ultimo < 2: return True
    usuarios_activos[telefono] = ahora
    return False

# --- CRM GOOGLE SHEETS ---
def registrar_lead(nombre, telefono, pais, interes):
    try:
        if not GOOGLE_JSON: return
        # Conectar con Google Sheets
        creds_dict = json.loads(GOOGLE_JSON)
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
        client = gspread.authorize(creds)
        sheet = client.open("Clientes_Bot").sheet1
        
        # Fecha y Hora (Ajustado a hora Venezuela aprox UTC-4)
        hora_vzla = datetime.utcnow() - timedelta(hours=4)
        fecha = hora_vzla.strftime("%Y-%m-%d")
        hora = hora_vzla.strftime("%H:%M:%S")
        
        sheet.append_row([fecha, hora, nombre, telefono, pais, interes])
        print(f"✅ Lead guardado: {nombre}")
    except Exception as e:
        print(f"❌ Error Sheets: {e}")

# --- HERRAMIENTAS ---
def es_horario_laboral():
    # Define horario: de 8 AM a 10 PM (22:00) hora Venezuela
    hora_actual = (datetime.utcnow() - timedelta(hours=4)).hour
    return 8 <= hora_actual < 22

def enviar(telefono, tipo, contenido, caption=None):
    # Usamos la versión v19.0 de la API para asegurar compatibilidad
    url = f"https://graph.facebook.com/v19.0/{NUMERO_ID}/messages"
    headers = {
        "Authorization": f"Bearer {TOKEN_WHATSAPP}",
        "Content-Type": "application/json"
    }
    data = {
        "messaging_product": "whatsapp",
        "to": telefono,
        "type": tipo
    }
    
    if tipo == "text":
        data["text"] = {"body": contenido}
    elif tipo == "image":
        data["image"] = {"link": contenido}
        if caption: data["image"]["caption"] = caption
    elif tipo == "audio":
        data["audio"] = {"link": contenido}
    elif tipo == "interactive":
        data["interactive"] = contenido
    elif tipo == "reaction": 
        data["recipient_type"] = "individual"
        data["reaction"] = {"message_id": contenido, "emoji": caption}

    try:
        response = requests.post(url, headers=headers, json=data)
        if response.status_code != 200:
            print(f"⚠️ Error enviando mensaje a {telefono}: {response.text}")
    except Exception as e:
        print(f"❌ Error request: {e}")

def marcar_leido(msg_id):
    url = f"https://graph.facebook.com/v19.0/{NUMERO_ID}/messages"
    headers = {
        "Authorization": f"Bearer {TOKEN_WHATSAPP}",
        "Content-Type": "application/json"
    }
    try:
        requests.post(url, headers=headers, json={
            "messaging_product": "whatsapp", 
            "status": "read", 
            "message_id": msg_id
        })
    except Exception: pass

# --- MENÚS DEL BOT ---
def menu_pais(telefono, nombre):
    # Primero enviamos audio y logo
    enviar(telefono, "audio", AUDIO_SALUDO)
    time.sleep(1) 
    enviar(telefono, "image", IMG_LOGO)
    
    botones = {
        "type": "button",
        "body": {"text": f"👋 *¡Hola {nombre}!* Gracias por escribir a Peluches Marketing.\n\nPara mostrarte los precios y moneda correcta, selecciona tu ubicación 👇"},
        "action": {
            "buttons": [
                {"type": "reply", "reply": {"id": "pais_ve", "title": "🇻🇪 Venezuela"}}, 
                {"type": "reply", "reply": {"id": "pais_cl", "title": "🇨🇱 Chile"}}
            ]
        }
    }
    enviar(telefono, "interactive", botones)

def menu_servicios(telefono, pais_code):
    bandera = "🇻🇪" if pais_code == "ve" else "🇨🇱"
    botones = {
        "type": "button",
        "body": {"text": f"{bandera} *Menú {pais_code.upper()}*\nSelecciona qué deseas cotizar:"},
        "action": {
            "buttons": [
                {"type": "reply", "reply": {"id": f"mkt_{pais_code}", "title": "📱 Redes Sociales"}},
                {"type": "reply", "reply": {"id": f"dsn_{pais_code}", "title": "🎨 Diseño Gráfico"}},
                {"type": "reply", "reply": {"id": f"inf_{pais_code}", "title": "❓ Info Pagos"}}
            ]
        }
    }
    enviar(telefono, "interactive", botones)

def submenu_planes_redes(telefono, pais_code):
    bandera = "🇻🇪" if pais_code == "ve" else "🇨🇱"
    botones = {
        "type": "button",
        "body": {"text": f"{bandera} *Planes de Redes Sociales*\n\nManejamos 3 estrategias integrales. Toca cada botón para ver qué incluye 👇"},
        "action": {
            "buttons": [
                {"type": "reply", "reply": {"id": f"plan_ini_{pais_code}", "title": "🌱 Plan Inicial"}},
                {"type": "reply", "reply": {"id": f"plan_med_{pais_code}", "title": "🚀 Plan Medio"}},
                {"type": "reply", "reply": {"id": f"plan_ava_{pais_code}", "title": "💎 Plan Avanzado"}}
            ]
        }
    }
    enviar(telefono, "interactive", botones)

def botones_navegacion(telefono, pais_code):
    botones = {
        "type": "button",
        "body": {"text": "¿Qué deseas hacer ahora?"},
        "action": {
            "buttons": [
                {"type": "reply", "reply": {"id": f"humano_{pais_code}", "title": "🙋 Contratar/Dudas"}},
                {"type": "reply", "reply": {"id": f"mkt_{pais_code}", "title": "🔙 Ver Otros Planes"}}
            ]
        }
    }
    enviar(telefono, "interactive", botones)

def gestionar_humano(numero, nombre, pais):
    registrar_lead(nombre, numero, pais, "🚨 Pidió Asesor")
    link = f"https://wa.me/{NUMERO_ADMIN}"
    
    if es_horario_laboral():
        enviar(numero, "text", f"✅ He avisado a mi director.\nSi deseas atención inmediata, escribe directo aquí: {link}")
        # AVISO AL DUEÑO (A TI)
        enviar(NUMERO_ADMIN, "text", f"🚨 *NUEVO LEAD {pais.upper()}*\n👤 {nombre}\n📱 {numero}\n💬 Quiere hablar con un humano.")
    else:
        enviar(numero, "text", f"🌙 En este momento estamos descansando, pero ya dejé tu nota. Te escribiremos mañana a primera hora.\n\nSi es urgente: {link}")
        enviar(NUMERO_ADMIN, "text", f"💤 *LEAD NOCTURNO*\n👤 {nombre} ({numero})")

# --- SERVIDOR FLASK ---
@app.route("/webhook", methods=["GET"])
def verificar():
    # Verificación de Token con Meta
    if request.args.get("hub.verify_token") == VERIFY_TOKEN:
        return request.args.get("hub.challenge"), 200
    return "Error de verificación", 403

@app.route("/webhook", methods=["POST"])
def recibir():
    try:
        body = request.json
        # Verificar estructura del mensaje
        if not body or "entry" not in body:
            return jsonify({"status": "error", "message": "No entry found"}), 400

        entry = body["entry"][0]["changes"][0]["value"]
        
        if "messages" in entry:
            msg = entry["messages"][0]
            numero = msg["from"]
            msg_id = msg["id"]
            nombre = entry["contacts"][0]["profile"]["name"]
            
            # Anti-Spam
            if es_spam(numero): return "Spam", 200
            
            # Marcar como leído
            marcar_leido(msg_id)

            # 1. SI ES TEXTO
            if msg["type"] == "text":
                txt = msg["text"]["body"].lower()
                
                # Palabras clave de inicio
                if any(x in txt for x in ["hola", "info", "buenas", "precio", "cotizar", "buenos"]):
                    enviar(numero, "reaction", msg_id, "👋")
                    menu_pais(numero, nombre)
                    registrar_lead(nombre, numero, "Inicio", "Saludo")
                
                elif "asesor" in txt or "humano" in txt:
                    gestionar_humano(numero, nombre, "General")

            # 2. SI ES RESPUESTA A BOTÓN (INTERACTIVO)
            elif msg["type"] == "interactive":
                btn_id = msg["interactive"]["button_reply"]["id"]
                enviar(numero, "reaction", msg_id, "✅")

                # A. SELECCIÓN DE PAÍS
                if btn_id == "pais_ve": 
                    menu_servicios(numero, "ve")
                    registrar_lead(nombre, numero, "Venezuela", "Selección País")
                elif btn_id == "pais_cl": 
                    menu_servicios(numero, "cl")
                    registrar_lead(nombre, numero, "Chile", "Selección País")

                # B. SUB-MENU REDES
                elif "mkt_" in btn_id:
                    pais = "ve" if "_ve" in btn_id else "cl"
                    submenu_planes_redes(numero, pais)

                # C. DETALLE DE PLANES (TEXTO + IMAGEN)
                elif "plan_" in btn_id:
                    pais_nombre = "Venezuela" if "_ve" in btn_id else "Chile"
                    pais_code = "ve" if "_ve" in btn_id else "cl"
                    
                    if "_ini_" in btn_id:
                        img = IMG_INI_VE if pais_code == "ve" else IMG_INI_CL
                        texto = (
                            f"🌱 *Plan Inicial ({pais_nombre})*\n\n"
                            "✅ 3 Posts semanales\n"
                            "✅ 2 Historias semanales\n"
                            "✅ Copy + Diseños + Perfil\n\n"
                            "👇 *Mira el detalle en la imagen:*"
                        )
                        nombre_plan = "Plan Inicial"
                    elif "_med_" in btn_id:
                        img = IMG_MED_VE if pais_code == "ve" else IMG_MED_CL
                        texto = (
                            f"🚀 *Plan Medio ({pais_nombre})*\n\n"
                            "✅ 4 Posts semanales\n"
                            "✅ 1 Reel + 2 Historias sem.\n"
                            "✅ Copy + Diseños + Perfil\n\n"
                            "👇 *Mira el detalle en la imagen:*"
                        )
                        nombre_plan = "Plan Medio"
                    elif "_ava_" in btn_id:
                        img = IMG_AVA_VE if pais_code == "ve" else IMG_AVA_CL
                        texto = (
                            f"💎 *Plan Avanzado ({pais_nombre})*\n\n"
                            "✅ 5 Posts semanales\n"
                            "✅ 2 Reels + 3 Historias sem.\n"
                            "✅ Copy + Diseños + Perfil\n"
                            "🎁 Stickers Personalizados\n\n"
                            "👇 *Mira el detalle en la imagen:*"
                        )
                        nombre_plan = "Plan Avanzado"

                    registrar_lead(nombre, numero, pais_nombre, nombre_plan)
                    enviar(numero, "image", img, caption=texto) 
                    botones_navegacion(numero, pais_code)

                # D. DISEÑO GRÁFICO
                elif "dsn_" in btn_id:
                    pais = "VE" if "_ve" in btn_id else "CL"
                    enviar(numero, "image", IMG_DISENO, caption=f"🎨 *Diseño Gráfico ({pais})*\nLogos, Flyers, Videos y más.\nMira nuestro catálogo visual 👆")
                    registrar_lead(nombre, numero, "Venezuela" if pais=="VE" else "Chile", "Diseño")
                    
                    botones = {"type": "button", "body": {"text": "¿Qué deseas hacer?"}, "action": {"buttons": [{"type": "reply", "reply": {"id": f"humano_{'ve' if pais=='VE' else 'cl'}", "title": "🙋 Cotizar"}}]}}
                    enviar(numero, "interactive", botones)

                # E. INFO PAGOS
                elif "inf_" in btn_id:
                    if "_ve" in btn_id:
                        enviar(numero, "text", "🇻🇪 *Pagos VE*\n- Binance (USDT)\n- Efectivo ($/Bs)\n- Pago Móvil")
                    else:
                        enviar(numero, "text", "🇨🇱 *Pagos CL*\n- Transferencia Banco Estado / RUT\n- Pesos Chilenos")
                    
                    botones = {"type": "button", "body": {"text": "¿Dudas?"}, "action": {"buttons": [{"type": "reply", "reply": {"id": f"humano_{'ve' if '_ve' in btn_id else 'cl'}", "title": "🙋 Hablar con Asesor"}}]}}
                    enviar(numero, "interactive", botones)
                
                # F. CONTACTAR HUMANO
                elif "humano_" in btn_id:
                    pais = "Venezuela" if "_ve" in btn_id else "Chile"
                    gestionar_humano(numero, nombre, pais)

    except Exception as e:
        print(f"Error procesando mensaje: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500
    
    return jsonify({"status": "success"}), 200

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=5000)
