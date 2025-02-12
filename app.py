import os
import requests
import json
from flask import Flask, request

app = Flask(__name__)

# Variables de entorno (deben estar configuradas en Render)
WHATSAPP_TOKEN = os.getenv('WHATSAPP_TOKEN')
WHATSAPP_PHONE_ID = os.getenv('WHATSAPP_PHONE_ID')
GPT_API_KEY = os.getenv('GPT_API_KEY')
VERIFY_TOKEN = os.getenv('VERIFY_TOKEN')  # Asegúrate de que en Meta usaste este mismo token

# Ruta para verificar Webhook en Meta
@app.route("/webhook", methods=["GET"])
def verify_webhook():
    mode = request.args.get("hub.mode")
    token = request.args.get("hub.verify_token")
    challenge = request.args.get("hub.challenge")

    if mode == "subscribe" and token == VERIFY_TOKEN:
        return challenge, 200  # Meta espera recibir este "challenge"
    else:
        return "Verificación fallida", 403

# Ruta para recibir mensajes de WhatsApp
@app.route("/webhook", methods=["POST"])
def receive_message():
    data = request.get_json()
    
    if "entry" in data:
        for entry in data["entry"]:
            for change in entry["changes"]:
                if "messages" in change["value"]:
                    msg = change["value"]["messages"][0]
                    sender = msg["from"]
                    text = msg["text"]["body"]

                    # Llamar a GPT-4 para obtener respuesta
                    gpt_response = requests.post(
                        "https://api.openai.com/v1/chat/completions",
                        headers={
                            "Authorization": f"Bearer {GPT_API_KEY}",
                            "Content-Type": "application/json"
                        },
                        json={
                            "model": "gpt-4",
                            "messages": [{"role": "user", "content": text}]
                        }
                    ).json()

                    # Extraer respuesta y enviarla a WhatsApp
                   try:
                        reply_text = gpt_response["choices"][0]["message"]["content"]
                    except KeyError:
                        print(f"⚠️ Error: Respuesta inválida de OpenAI → {gpt_response}")  # Log de error en Render
                        reply_text = "Lo siento, hubo un problema con la respuesta de la IA."


    return "OK", 200

# Función para enviar mensajes de WhatsApp
def send_whatsapp_message(to, text):
    headers = {
        "Authorization": f"Bearer {WHATSAPP_TOKEN}",
        "Content-Type": "application/json"
    }
    data = {
        "messaging_product": "whatsapp",
        "to": to,
        "type": "text",
        "text": {"body": text}
    }
    requests.post(f"https://graph.facebook.com/v16.0/{WHATSAPP_PHONE_ID}/messages", headers=headers, json=data)

if __name__ == "__main__":
    from waitress import serve
    serve(app, host="0.0.0.0", port=8080)

