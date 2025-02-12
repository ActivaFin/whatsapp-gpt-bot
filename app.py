import os
import requests
import json
from flask import Flask, request

app = Flask(__name__)

# Configuración de variables de entorno
WHATSAPP_TOKEN = os.getenv('WHATSAPP_TOKEN')
WHATSAPP_PHONE_ID = os.getenv('WHATSAPP_PHONE_ID')
GPT_API_KEY = os.getenv('GPT_API_KEY')
VERIFY_TOKEN = os.getenv('VERIFY_TOKEN')
ASSISTANT_ID = "asst_JK0Nis5xePIfHSwV5HTSv2XW"  # Reemplázalo con tu Assistant ID de OpenAI

# URL de la API de WhatsApp
WHATSAPP_URL = f"https://graph.facebook.com/v16.0/{WHATSAPP_PHONE_ID}/messages"

# Función para enviar mensajes a WhatsApp
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
    response = requests.post(WHATSAPP_URL, headers=headers, json=data)
    return response.json()

# Función para obtener respuesta del Assistant de OpenAI
def get_gpt_response(prompt):
    try:
        response = requests.post(
            f"https://api.openai.com/v1/assistants/{ASSISTANT_ID}/messages",
            headers={
                "Authorization": f"Bearer {GPT_API_KEY}",
                "Content-Type": "application/json"
            },
            json={
                "messages": [{"role": "user", "content": prompt}]
            }
        )
        response.raise_for_status()
        data = response.json()
        print("📡 Respuesta de GPT_Mundoliva:", json.dumps(data, indent=2))  # Verificar respuesta en logs
        return data["choices"][0]["message"]["content"]
    except requests.exceptions.RequestException as e:
        print(f"⚠️ Error en OpenAI: {e}")  # Muestra errores en logs
        return "Hubo un error con la respuesta de la IA."
    except KeyError:
        print("⚠️ OpenAI no devolvió una respuesta válida.")
        return "Lo siento, hubo un problema con la IA."

# Webhook de verificación para Meta
@app.route("/webhook", methods=["GET"])
def verify_webhook():
    mode = request.args.get("hub.mode")
    token = request.args.get("hub.verify_token")
    challenge = request.args.get("hub.challenge")

    if mode == "subscribe" and token == VERIFY_TOKEN:
        return challenge, 200
    else:
        return "Verificación fallida", 403

# Webhook para recibir mensajes de WhatsApp
@app.route("/webhook", methods=["POST"])
def receive_message():
    data = request.get_json()
    print("📩 Mensaje recibido:", json.dumps(data, indent=2))  # Verifica si WhatsApp está enviando mensajes

    if "entry" in data:
        for entry in data["entry"]:
            for change in entry["changes"]:
                if "messages" in change["value"]:
                    msg = change["value"]["messages"][0]
                    sender = msg["from"]
                    text = msg["text"]["body"]

                    print(f"📩 Mensaje de {sender}: {text}")  # Verifica si el bot recibe los mensajes

                    # Obtener respuesta de OpenAI Assistant
                    reply_text = get_gpt_response(text)

                    # Enviar la respuesta de vuelta a WhatsApp
                    send_whatsapp_message(sender, reply_text)

    return "OK", 200

# Iniciar la aplicación Flask
if __name__ == "__main__":
    from waitress import serve
    serve(app, host="0.0.0.0", port=8080)
