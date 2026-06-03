import os
import json
import requests
from flask import Flask, request, jsonify
from datetime import datetime

app = Flask(__name__)

VERIFY_TOKEN = os.environ.get("VERIFY_TOKEN", "skladusa_secret_2024")
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN", "8861620877:AAGzp1G7UgzeIAsQC3Fdu6mje_qidhdKmuU")
KEYWORDS = ["skladusa", "skladu sa", "склад usa", "складusa"]

mentions = []

def is_mention(text):
    if not text:
        return False
    text_lower = text.lower()
    return any(kw in text_lower for kw in KEYWORDS)

@app.route("/", methods=["GET"])
def home():
    return "SkladUSA Social Monitor (Instagram + Facebook + Telegram) is running!", 200

@app.route("/webhook", methods=["GET"])
def verify_webhook():
    mode = request.args.get("hub.mode")
    token = request.args.get("hub.verify_token")
    challenge = request.args.get("hub.challenge")
    if mode == "subscribe" and token == VERIFY_TOKEN:
        return challenge, 200
    return "Forbidden", 403

@app.route("/webhook", methods=["POST"])
def receive_webhook():
    data = request.json
    if not data:
        return jsonify({"status": "ok"}), 200

    # Telegram updates
    if "message" in data or "channel_post" in data:
        msg = data.get("message") or data.get("channel_post", {})
        text = msg.get("text", "")
        chat = msg.get("chat", {})
        sender = msg.get("from", {})

        mention = {
            "platform": "telegram",
            "time": datetime.utcnow().isoformat(),
            "type": "channel_post" if "channel_post" in data else "message",
            "text": text,
            "from": sender.get("username") or sender.get("first_name", "unknown"),
            "chat_title": chat.get("title", ""),
            "chat_id": str(chat.get("id", "")),
            "is_keyword_match": is_mention(text),
        }

        # Save all posts from own channel + keyword matches from other chats
        if chat.get("type") == "channel" or is_mention(text):
            mentions.append(mention)
            print(f"[Telegram] {mention['chat_title']}: {text[:100]}")

        return jsonify({"status": "ok"}), 200

    # Meta (Instagram + Facebook) updates
    if "entry" in data:
        for entry in data["entry"]:
            if "changes" in entry:
                for change in entry["changes"]:
                    value = change.get("value", {})
                    field = change.get("field", "")

                    if field in ("feed", "mention"):
                        mention = {
                            "platform": "facebook",
                            "time": datetime.utcnow().isoformat(),
                            "type": field,
                            "text": value.get("message", value.get("text", "")),
                            "from": value.get("from", {}).get("name", "unknown"),
                            "post_id": value.get("post_id", ""),
                        }
                        mentions.append(mention)
                        print(f"[Facebook] {mention['from']}: {mention['text'][:100]}")

                    elif field in ("comments", "mentions"):
                        mention = {
                            "platform": "instagram",
                            "time": datetime.utcnow().isoformat(),
                            "type": field,
                            "text": value.get("text", ""),
                            "from": value.get("from", {}).get("username", "unknown"),
                            "media_id": value.get("media_id", ""),
                        }
                        mentions.append(mention)
                        print(f"[Instagram] @{mention['from']}: {mention['text'][:100]}")

            if "messaging" in entry:
                for msg_event in entry["messaging"]:
                    msg = msg_event.get("message", {})
                    mention = {
                        "platform": "instagram",
                        "time": datetime.utcnow().isoformat(),
                        "type": "direct_message",
                        "text": msg.get("text", ""),
                        "from": msg_event.get("sender", {}).get("id", "unknown"),
                    }
                    mentions.append(mention)

    return jsonify({"status": "ok"}), 200

@app.route("/mentions", methods=["GET"])
def get_mentions():
    platform = request.args.get("platform")
    if platform:
        filtered = [m for m in mentions if m.get("platform") == platform]
    else:
        filtered = mentions
    return jsonify({"total": len(filtered), "mentions": filtered[-50:]}), 200

@app.route("/setup-telegram", methods=["GET"])
def setup_telegram():
    webhook_url = request.host_url + "webhook"
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/setWebhook"
    r = requests.post(url, json={"url": webhook_url})
    return jsonify(r.json()), 200

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
