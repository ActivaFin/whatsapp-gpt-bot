import requests
import json
from flask import Flask, request

app = Flask(__name__)

# Variables de entorno (se configuran en Render)
WHATSAPP_TOKEN = "TU_TOKEN_DE_META"
WHATSAPP_PHONE_ID = "TU_PHONE_ID_DE_WHATSAPP"
GPT_API_KEY = "TU_CLAVE_OPENAI"

# URL de la API de WhatsApp
WHATSAPP_URL = f"https://graph.facebook.com/v16.0/{WHATSAPP_PHONE_ID}/messages"

# Función para enviar respuestas a WhatsApp
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
    requests.post(WHATSAPP_URL, headers=headers, json=data)

# Webhook para recibir mensajes de WhatsApp
@app.route("/webhook", methods=["POST"])
def webhook():
    data = request.get_json()
    if data["entry"]:
        for entry in data["entry"]:
            for message in entry["changes"]:
                if "messages" in message["value"]:
                    msg = message["value"]["messages"][0]
                    sender = msg["from"]
                    text = msg["text"]["body"]

                    # Enviar la consulta a OpenAI
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

                    reply_text = gpt_response["choices"][0]["message"]["content"]
                    send_whatsapp_message(sender, reply_text)

    return "OK", 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)
