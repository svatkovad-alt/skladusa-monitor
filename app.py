import os
import json
import requests
import anthropic
from flask import Flask, request, jsonify
from datetime import datetime, timedelta
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

VERIFY_TOKEN = os.environ.get("VERIFY_TOKEN", "skladusa_secret_2024")
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN", "8861620877:AAGzp1G7UgzeIAsQC3Fdu6mje_qidhdKmuU")
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "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")
KEYWORDS = ["skladusa", "skladu sa", "склад usa", "складusa"]

mentions = []
cached_ideas = []
ideas_last_updated = None

def is_mention(text):
    if not text:
        return False
    return any(kw in text.lower() for kw in KEYWORDS)

def generate_ideas():
    global cached_ideas, ideas_last_updated
    if not mentions:
        return []

    recent = mentions[-100:]
    texts = [m.get("text", "") for m in recent if m.get("text")]
    if not texts:
        return []

    sample = "\n".join(f"- [{m.get('platform','?')}] {m.get('text','')}" for m in recent[-30:] if m.get("text"))

    try:
        client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
        response = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=800,
            messages=[{
                "role": "user",
                "content": f"""Ти маркетолог для компанії SkladUSA — склад і доставка з США в Україну.

Ось останні згадки про компанію в соціальних мережах:
{sample}

На основі цих згадок згенеруй 4 ідеї для контент-постів. Для кожної ідеї вкажи:
1. Назву посту (коротко, до 60 символів)
2. Пояснення чому ця ідея актуальна (1 речення)
3. Платформи: instagram, facebook, telegram (одна або кілька)

Відповідь строго у форматі JSON масиву:
[
  {{"title": "...", "meta": "...", "platforms": ["instagram", "telegram"]}},
  ...
]
Тільки JSON, без пояснень."""
            }]
        )

        text = response.content[0].text.strip()
        if text.startswith("```"):
            text = text.split("```")[1]
            if text.startswith("json"):
                text = text[4:]
        ideas = json.loads(text.strip())
        cached_ideas = ideas
        ideas_last_updated = datetime.utcnow().isoformat()
        return ideas
    except Exception as e:
        print(f"Claude API error: {e}")
        return cached_ideas

@app.route("/", methods=["GET"])
def home():
    return "SkladUSA Social Monitor (Instagram + Facebook + Telegram + AI) is running!", 200

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
        }
        if chat.get("type") == "channel" or is_mention(text):
            mentions.append(mention)
        return jsonify({"status": "ok"}), 200

    if "entry" in data:
        for entry in data["entry"]:
            if "changes" in entry:
                for change in entry["changes"]:
                    value = change.get("value", {})
                    field = change.get("field", "")
                    if field in ("feed", "mention"):
                        mentions.append({
                            "platform": "facebook",
                            "time": datetime.utcnow().isoformat(),
                            "type": field,
                            "text": value.get("message", value.get("text", "")),
                            "from": value.get("from", {}).get("name", "unknown"),
                        })
                    elif field in ("comments", "mentions"):
                        mentions.append({
                            "platform": "instagram",
                            "time": datetime.utcnow().isoformat(),
                            "type": field,
                            "text": value.get("text", ""),
                            "from": value.get("from", {}).get("username", "unknown"),
                        })
            if "messaging" in entry:
                for msg_event in entry["messaging"]:
                    msg = msg_event.get("message", {})
                    mentions.append({
                        "platform": "instagram",
                        "time": datetime.utcnow().isoformat(),
                        "type": "direct_message",
                        "text": msg.get("text", ""),
                        "from": msg_event.get("sender", {}).get("id", "unknown"),
                    })

    return jsonify({"status": "ok"}), 200

@app.route("/mentions", methods=["GET"])
def get_mentions():
    platform = request.args.get("platform")
    filtered = [m for m in mentions if m.get("platform") == platform] if platform else mentions
    return jsonify({"total": len(filtered), "mentions": filtered[-50:]}), 200

@app.route("/ideas", methods=["GET"])
def get_ideas():
    global ideas_last_updated
    force = request.args.get("force") == "1"
    need_update = (
        force or
        not cached_ideas or
        not ideas_last_updated or
        (datetime.utcnow() - datetime.fromisoformat(ideas_last_updated)) > timedelta(hours=6)
    )
    if need_update:
        ideas = generate_ideas()
    else:
        ideas = cached_ideas
    return jsonify({"ideas": ideas, "updated": ideas_last_updated}), 200

@app.route("/setup-telegram", methods=["GET"])
def setup_telegram():
    webhook_url = request.host_url + "webhook"
    r = requests.post(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/setWebhook", json={"url": webhook_url})
    return jsonify(r.json()), 200

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
