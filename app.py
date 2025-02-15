import os
import requests
import json
import logging
import time
from flask import Flask, request, jsonify

# Configuración de logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Crear la instancia de Flask
app = Flask(__name__)

# Configuración de variables de entorno
WHATSAPP_TOKEN = os.getenv('WHATSAPP_TOKEN')
WHATSAPP_PHONE_ID = os.getenv('WHATSAPP_PHONE_ID')
GPT_API_KEY = os.getenv('GPT_API_KEY')
VERIFY_TOKEN = os.getenv('VERIFY_TOKEN')
ASSISTANT_ID = "asst_JK0Nis5xePIfHSwV5HTSv2XW"

# URL de la API de WhatsApp
WHATSAPP_URL = f"https://graph.facebook.com/v16.0/{WHATSAPP_PHONE_ID}/messages"

# Lista global para evitar respuestas duplicadas
processed_messages = set()

# 📌 Webhook de verificación para Meta
@app.route("/webhook", methods=["GET"])
def verify_webhook():
    mode = request.args.get("hub.mode")
    token = request.args.get("hub.verify_token")
    challenge = request.args.get("hub.challenge")

    if mode == "subscribe" and token == VERIFY_TOKEN:
        return challenge, 200
    else:
        return "Verificación fallida", 403

# 📌 Webhook para recibir mensajes de WhatsApp
@app.route("/webhook", methods=["POST"])
def receive_message():
    try:
        data = request.get_json()
        logger.info("📩 Mensaje recibido: %s", json.dumps(data, indent=2))

        if "entry" not in data:
            return jsonify({"status": "error", "message": "Invalid payload"}), 400

        for entry in data["entry"]:
            for change in entry["changes"]:
                
                # 📌 Filtrar mensajes de estado (sent, delivered, read)
                if "messages" not in change["value"]:
                    logger.info("ℹ️ Evento ignorado (no es un mensaje de usuario)")
                    continue
                
                msg = change["value"]["messages"][0]

                # 📌 Filtrar eventos de estado
                if msg.get("type") != "text":
                    logger.info("ℹ️ Evento ignorado (no es un mensaje de texto)")
                    continue

                message_id = msg.get("id")
                
                # 📌 Evitar responder dos veces al mismo mensaje
                if message_id in processed_messages:
                    logger.info(f"⚠️ Mensaje ya procesado: {message_id}")
                    return jsonify({"status": "success"}), 200

                sender = msg["from"]
                text = msg["text"]["body"]
                logger.info(f"📩 Mensaje de {sender}: {text}")

                # 📌 Obtener respuesta de OpenAI
                reply_text = get_gpt_response(text)
                
                # 📌 Si OpenAI falla, usar respuesta predeterminada
                if not reply_text or reply_text.strip() == "":
                    reply_text = "Lo siento, hubo un problema con mi respuesta. ¿Puedes intentar reformular la pregunta?"

                logger.info(f"✅ Respuesta de OpenAI: {reply_text}")

                # 📌 Evitar responder con el mismo mensaje recibido
                if reply_text.strip().lower() == text.strip().lower():
                    reply_text = "Entiendo tu mensaje. ¿En qué puedo ayudarte específicamente?"

                # 📌 Enviar respuesta a WhatsApp
                send_whatsapp_message(sender, reply_text)
                logger.info(f"✅ Mensaje enviado a WhatsApp: {reply_text}")

                # 📌 Marcar el mensaje como procesado
                processed_messages.add(message_id)

        return jsonify({"status": "success"}), 200

    except Exception as e:
        logger.error(f"⚠️ Error en receive_message: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

# 📌 Función para enviar mensajes a WhatsApp
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
    try:
        response = requests.post(WHATSAPP_URL, headers=headers, json=data)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.HTTPError as e:
        logger.error(f"⚠️ Error al enviar mensaje a WhatsApp: {e.response.json()}")
        return None
    except Exception as e:
        logger.error(f"⚠️ Error inesperado al enviar mensaje a WhatsApp: {e}")
        return None

# 📌 Función para obtener respuesta de OpenAI
def get_gpt_response(prompt):
    try:
        response = requests.post(
            "https://api.openai.com/v1/threads",
            headers={
                "Authorization": f"Bearer {GPT_API_KEY}",
                "OpenAI-Beta": "assistants=v2",
                "Content-Type": "application/json"
            },
            json={}
        )
        if response.status_code != 200:
            logger.error(f"⚠️ Error al crear hilo en OpenAI: {response.json()}")
            return None

        thread_id = response.json().get("id")
        if not thread_id:
            return None

        response = requests.post(
            f"https://api.openai.com/v1/threads/{thread_id}/messages",
            headers={
                "Authorization": f"Bearer {GPT_API_KEY}",
                "OpenAI-Beta": "assistants=v2",
                "Content-Type": "application/json"
            },
            json={"role": "user", "content": prompt}
        )

        if response.status_code != 200:
            logger.error(f"⚠️ Error al enviar mensaje a OpenAI: {response.json()}")
            return None

        # Espera 3 segundos antes de verificar
        time.sleep(3)
        response = requests.get(
            f"https://api.openai.com/v1/threads/{thread_id}/messages",
            headers={
                "Authorization": f"Bearer {GPT_API_KEY}",
                "OpenAI-Beta": "assistants=v2"
            }
        )

        if response.status_code != 200:
            logger.error(f"⚠️ Error al obtener mensajes de OpenAI: {response.json()}")
            return None

        messages = response.json().get("data", [])
        if messages:
            # 📌 Se extrae correctamente el texto de la respuesta de OpenAI
            content = messages[-1].get("content", [])
            if isinstance(content, list) and len(content) > 0:
                return content[0].get("text", {}).get("value", "Lo siento, no tengo una respuesta en este momento.")
            return "Lo siento, no tengo una respuesta en este momento."

        return "Lo siento, no tengo una respuesta en este momento."

    except requests.exceptions.RequestException as e:
        logger.error(f"⚠️ Error en OpenAI: {e}")
        return "Lo siento, hubo un problema con la IA."

# 📌 Iniciar la aplicación Flask
if __name__ == "__main__":
    from waitress import serve
    port = int(os.getenv("PORT", 8080))
    serve(app, host="0.0.0.0", port=port)
