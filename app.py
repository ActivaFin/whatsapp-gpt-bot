import os
import requests
import json
import logging
import time
from collections import deque
from flask import Flask, request, jsonify

# Configuración de logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Crear la instancia de Flask
app = Flask(__name__)

# Configuración de variables de entorno
required_env_vars = ["WHATSAPP_TOKEN", "WHATSAPP_PHONE_ID", "GPT_API_KEY", "VERIFY_TOKEN"]
for var in required_env_vars:
    if not os.getenv(var):
        logger.error(f"⚠️ Falta la variable de entorno: {var}")
        exit(1)

WHATSAPP_TOKEN = os.getenv('WHATSAPP_TOKEN')
WHATSAPP_PHONE_ID = os.getenv('WHATSAPP_PHONE_ID')
GPT_API_KEY = os.getenv('GPT_API_KEY')
VERIFY_TOKEN = os.getenv('VERIFY_TOKEN')
ASSISTANT_ID = "asst_JK0Nis5xePIfHSwV5HTSv2XW"  # Usa tu Assistant de OpenAI aquí

# URL de la API de WhatsApp
WHATSAPP_URL = f"https://graph.facebook.com/v16.0/{WHATSAPP_PHONE_ID}/messages"

# Lista global para evitar respuestas duplicadas
MAX_PROCESSED_MESSAGES = 1000
processed_messages = deque(maxlen=MAX_PROCESSED_MESSAGES)

# Webhook de verificación para Meta
@app.route("/webhook", methods=["GET"])
def verify_webhook():
    mode = request.args.get("hub.mode")
    token = request.args.get("hub.verify_token")
    challenge = request.args.get("hub.challenge")
    if mode == "subscribe" and token == VERIFY_TOKEN:
        return challenge, 200
    else:
        return jsonify({"status": "error", "message": "Verificación fallida"}), 403

# Webhook para recibir mensajes de WhatsApp
@app.route("/webhook", methods=["POST"])
def receive_message():
    try:
        data = request.get_json()
        logger.info("📩 Mensaje recibido: %s", json.dumps(data, indent=2))
        if "entry" not in data:
            return jsonify({"status": "error", "message": "Invalid payload"}), 400

        for entry in data["entry"]:
            for change in entry["changes"]:
                if "messages" not in change["value"]:
                    logger.info("ℹ️ Evento ignorado (no es un mensaje de usuario)")
                    continue

                msg = change["value"]["messages"][0]
                if msg.get("type") != "text":
                    logger.info("ℹ️ Evento ignorado (no es un mensaje de texto)")
                    continue

                message_id = msg.get("id")
                if message_id in processed_messages:
                    logger.info(f"⚠️ Mensaje ya procesado: {message_id}")
                    continue

                sender = msg["from"]
                text = msg["text"]["body"]
                logger.info(f"📩 Mensaje de {sender}: {text}")

                # Obtener respuesta de OpenAI
                reply_text = get_gpt_response(text)
                if not reply_text or reply_text.strip() == "":
                    reply_text = "Lo siento, hubo un problema con mi respuesta. ¿Puedes intentar reformular la pregunta?"

                logger.info(f"✅ Respuesta de OpenAI: {reply_text}")

                # Evitar responder con el mismo mensaje recibido
                if reply_text.strip().lower() == text.strip().lower():
                    reply_text = "Entiendo tu mensaje. ¿En qué puedo ayudarte específicamente?"

                # Enviar respuesta a WhatsApp
                send_whatsapp_message(sender, reply_text)
                logger.info(f"✅ Mensaje enviado a WhatsApp: {reply_text}")

                # Marcar el mensaje como procesado
                processed_messages.append(message_id)

        return jsonify({"status": "success"}), 200

    except Exception as e:
        logger.error(f"⚠️ Error en receive_message: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

# Función para enviar mensajes a WhatsApp
def send_whatsapp_message(to, text):
    headers = {
        "Authorization": f"Bearer {WHATSAPP_TOKEN}",
        "Content-Type": "application/json"
    }
    messages = split_message(text)
    for msg in messages:
        data = {
            "messaging_product": "whatsapp",
            "to": to,
            "type": "text",
            "text": {"body": msg}
        }
        try:
            response = requests.post(WHATSAPP_URL, headers=headers, json=data)
            response.raise_for_status()
        except requests.exceptions.HTTPError as e:
            logger.error(f"⚠️ Error al enviar mensaje a WhatsApp: {e.response.json()}")
            return None
        except Exception as e:
            logger.error(f"⚠️ Error inesperado al enviar mensaje a WhatsApp: {e}")
            return None
    return True

# Función para dividir mensajes largos
def split_message(text, max_length=4096):
    return [text[i:i + max_length] for i in range(0, len(text), max_length)]

# Función para obtener respuesta de OpenAI
def get_gpt_response(prompt):
    try:
        # Crear un nuevo hilo en OpenAI
        response = requests.post(
            "https://api.openai.com/v1/threads",
            headers={
                "Authorization": f"Bearer {GPT_API_KEY}",
                "OpenAI-Beta": "assistants=v2",
                "Content-Type": "application/json"
            },
            json={}
        )
        response.raise_for_status()
        thread_id = response.json().get("id")
        if not thread_id:
            logger.error("⚠️ No se obtuvo thread_id de OpenAI")
            return None

        # Enviar el mensaje del usuario al hilo
        response = requests.post(
            f"https://api.openai.com/v1/threads/{thread_id}/messages",
            headers={
                "Authorization": f"Bearer {GPT_API_KEY}",
                "OpenAI-Beta": "assistants=v2",
                "Content-Type": "application/json"
            },
            json={"role": "user", "content": prompt}
        )
        response.raise_for_status()

        # Esperar y verificar la respuesta con un retry
        max_retries = 5
        retry_delay = 3  # segundos
        for _ in range(max_retries):
            time.sleep(retry_delay)
            response = requests.get(
                f"https://api.openai.com/v1/threads/{thread_id}/messages",
                headers={
                    "Authorization": f"Bearer {GPT_API_KEY}",
                    "OpenAI-Beta": "assistants=v2"
                }
            )
            response.raise_for_status()
            messages = response.json().get("data", [])
            if messages:
                last_message = messages[-1].get("content")
                if isinstance(last_message, str):
                    return last_message
                elif isinstance(last_message, list) and len(last_message) > 0:
                    text_value = last_message[0].get("text", {}).get("value")
                    if text_value:
                        return text_value
                return str(last_message)

        logger.error("⚠️ No se pudo obtener una respuesta después de varios intentos")
        return "Lo siento, no se pudo obtener una respuesta de la IA."

    except requests.exceptions.RequestException as e:
        logger.error(f"⚠️ Error en OpenAI: {e}")
        return "Lo siento, hubo un problema con la IA."

# Iniciar la aplicación Flask
if __name__ == "__main__":
    from waitress import serve
    port = int(os.getenv("PORT", 8080))
    logger.info(f"🚀 Iniciando servidor en el puerto {port}...")
    serve(app, host="0.0.0.0", port=port)
