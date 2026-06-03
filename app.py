import os
import json
from flask import Flask, request, jsonify
from datetime import datetime

app = Flask(__name__)

VERIFY_TOKEN = os.environ.get("VERIFY_TOKEN", "skladusa_secret_2024")

mentions = []

@app.route("/", methods=["GET"])
def home():
    return "SkladUSA Social Monitor (Instagram + Facebook) is running!", 200

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

    if not data or "entry" not in data:
        return jsonify({"status": "ok"}), 200

    for entry in data["entry"]:
        # Facebook Page events
        if "changes" in entry:
            for change in entry["changes"]:
                value = change.get("value", {})
                field = change.get("field", "")

                # Facebook comment or mention
                if field in ("feed", "mention", "comments"):
                    mention = {
                        "platform": "facebook",
                        "time": datetime.utcnow().isoformat(),
                        "type": field,
                        "text": value.get("message", value.get("text", "")),
                        "from": value.get("from", {}).get("name", "unknown"),
                        "post_id": value.get("post_id", ""),
                        "comment_id": value.get("comment_id", ""),
                    }
                    mentions.append(mention)
                    print(f"[Facebook] New {field} from {mention['from']}: {mention['text']}")

                # Instagram comment or mention
                elif field in ("comments", "mentions", "messages"):
                    mention = {
                        "platform": "instagram",
                        "time": datetime.utcnow().isoformat(),
                        "type": field,
                        "text": value.get("text", ""),
                        "from": value.get("from", {}).get("username", "unknown"),
                        "media_id": value.get("media_id", ""),
                    }
                    mentions.append(mention)
                    print(f"[Instagram] New {field} from @{mention['from']}: {mention['text']}")

        # Instagram messaging events
        if "messaging" in entry:
            for msg_event in entry["messaging"]:
                msg = msg_event.get("message", {})
                mention = {
                    "platform": "instagram",
                    "time": datetime.utcnow().isoformat(),
                    "type": "direct_message",
                    "text": msg.get("text", ""),
                    "from": msg_event.get("sender", {}).get("id", "unknown"),
                    "media_id": "",
                }
                mentions.append(mention)
                print(f"[Instagram DM] from {mention['from']}: {mention['text']}")

    return jsonify({"status": "ok"}), 200

@app.route("/mentions", methods=["GET"])
def get_mentions():
    platform = request.args.get("platform")
    if platform:
        filtered = [m for m in mentions if m.get("platform") == platform]
    else:
        filtered = mentions
    return jsonify({"total": len(filtered), "mentions": filtered[-50:]}), 200

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
