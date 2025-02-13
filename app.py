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
ASSISTANT_ID = "asst_JK0Nis5xePIfHSwV5HTSv2XW"  # 👈 Usa tu Assistant de OpenAI aquí

# URL de la API de WhatsApp
WHATSAPP_URL = f"https://graph.facebook.com/v16.0/{WHATSAPP_PHONE_ID}/messages"

# Función para enviar mensajes a WhatsApp
def get_gpt_response(prompt):
    try:
        # Crear un nuevo hilo en OpenAI Assistants API v2
        response = requests.post(
            "https://api.openai.com/v1/threads",
            headers={
                "Authorization": f"Bearer {GPT_API_KEY}",
                "OpenAI-Beta": "assistants=v2",
                "Content-Type": "application/json"
            },
            json={}
        )
        thread_data = response.json()
        thread_id = thread_data.get("id")

        if not thread_id:
            print(f"⚠️ Error: No se pudo crear un hilo en OpenAI → {thread_data}")
            return "Lo siento, hubo un problema con la IA."

        # Enviar mensaje al Assistant
        response = requests.post(
            f"https://api.openai.com/v1/threads/{thread_id}/messages",
            headers={
                "Authorization": f"Bearer {GPT_API_KEY}",
                "OpenAI-Beta": "assistants=v2",
                "Content-Type": "application/json"
            },
            json={"role": "user", "content": prompt}
        )

        # Iniciar la ejecución del Assistant
        response = requests.post(
            f"https://api.openai.com/v1/threads/{thread_id}/runs",
            headers={
                "Authorization": f"Bearer {GPT_API_KEY}",
                "OpenAI-Beta": "assistants=v2",
                "Content-Type": "application/json"
            },
            json={"assistant_id": ASSISTANT_ID}
        )

        run_data = response.json()
        run_id = run_data.get("id")

        if not run_id:
            print(f"⚠️ Error: No se pudo iniciar la ejecución del Assistant → {run_data}")
            return "Hubo un error con la respuesta de la IA."

        # Esperar la respuesta del Assistant
        import time
        for _ in range(10):  # Intentar durante 10 ciclos de espera
            time.sleep(2)  # Esperar 2 segundos entre intentos
            response = requests.get(
                f"https://api.openai.com/v1/threads/{thread_id}/runs/{run_id}",
                headers={
                    "Authorization": f"Bearer {GPT_API_KEY}",
                    "OpenAI-Beta": "assistants=v2"
                }
            )
            run_status = response.json().get("status")
            if run_status == "completed":
                break

        # Obtener la respuesta del Assistant
        response = requests.get(
            f"https://api.openai.com/v1/threads/{thread_id}/messages",
            headers={
                "Authorization": f"Bearer {GPT_API_KEY}",
                "OpenAI-Beta": "assistants=v2"
            }
        )
        messages = response.json().get("data", [])
        if messages:
            return messages[-1]["content"]  # Último mensaje del Assistant
        else:
            return "Hubo un error obteniendo la respuesta de la IA."
    
    except requests.exceptions.RequestException as e:
        print(f"⚠️ Error en OpenAI: {e}")  # Muestra errores en logs
        return "Hubo un error con la respuesta de la IA."

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
