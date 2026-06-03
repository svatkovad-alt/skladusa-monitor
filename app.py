import os
import json
from flask import Flask, request, jsonify
from datetime import datetime

app = Flask(__name__)

VERIFY_TOKEN = os.environ.get("VERIFY_TOKEN", "skladusa_secret_2024")

mentions = []

@app.route("/", methods=["GET"])
def home():
    return "SkladUSA Instagram Monitor is running!", 200

@app.route("/webhook", methods=["GET"])
def verify_webhook():
    mode = request.args.get("hub.mode")
    token = request.args.get("hub.verify_token")
    challenge = request.args.get("hub.challenge")

    if mode == "subscribe" and token == VERIFY_TOKEN:
        print("Webhook verified!")
        return challenge, 200
    return "Forbidden", 403

@app.route("/webhook", methods=["POST"])
def receive_webhook():
    data = request.json
    print("Incoming webhook:", json.dumps(data, indent=2))

    if data and "entry" in data:
        for entry in data["entry"]:
            for change in entry.get("changes", []):
                value = change.get("value", {})
                mention = {
                    "time": datetime.utcnow().isoformat(),
                    "type": change.get("field"),
                    "text": value.get("text", ""),
                    "from": value.get("from", {}).get("username", "unknown"),
                    "media_id": value.get("media_id", ""),
                }
                mentions.append(mention)
                print(f"New mention from @{mention['from']}: {mention['text']}")

    return jsonify({"status": "ok"}), 200

@app.route("/mentions", methods=["GET"])
def get_mentions():
    return jsonify({"total": len(mentions), "mentions": mentions[-50:]}), 200

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
