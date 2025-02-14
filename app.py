import logging
from flask import Flask, request, jsonify

# Configuración de logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

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
                    continue

                msg = change["value"]["messages"][0]
                if msg["type"] != "text":
                    continue

                sender = msg["from"]
                text = msg["text"]["body"]
                logger.info(f"📩 Mensaje de {sender}: {text}")

                # Obtener respuesta de OpenAI Assistant
                reply_text = get_gpt_response(text)

                # Enviar la respuesta de vuelta a WhatsApp
                send_whatsapp_message(sender, reply_text)

        return jsonify({"status": "success"}), 200

    except Exception as e:
        logger.error(f"⚠️ Error en receive_message: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500
