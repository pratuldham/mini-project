import os
import json
import re
import time
import requests
from datetime import datetime
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS

# ─────────────────────────────────────────────
# CONFIG
# ─────────────────────────────────────────────
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
FRONTEND_DIR = os.path.join(BASE_DIR, "..", "frontend")

GROK_API_KEY = os.getenv("GROK_API_KEY") # ✅ secure
             
GROK_URL = "https://api.x.ai/v1/chat/completions"
GROK_MODEL = "grok-4.20-beta-latest-non-reasoning"
             # ✅ FIXED

app = Flask(__name__, static_folder=FRONTEND_DIR, static_url_path="")
CORS(app)

# ─────────────────────────────────────────────
# LOGGER
# ─────────────────────────────────────────────
LOGS = []

def log(event, data=None):
    entry = {
        "time": datetime.utcnow().isoformat(),
        "event": event,
        "data": data
    }
    LOGS.append(entry)
    print(f"[{entry['time']}] {event}: {data}")

# ─────────────────────────────────────────────
# GROK CALL (WITH RETRY)
# ─────────────────────────────────────────────
def call_grok(prompt: str, max_tokens: int = 2000) -> str:
    if not GROK_API_KEY:
        raise ValueError("Missing GROK_API_KEY")

    headers = {
        "Authorization": f"Bearer {GROK_API_KEY}",
        "Content-Type": "application/json",
    }

    payload = {
        "model": GROK_MODEL,
        "messages": [
            {"role": "system", "content": "You are a helpful tutor."},
            {"role": "user", "content": prompt}
        ],
        "temperature": 0.7,
        "max_tokens": max_tokens
    }

    for attempt in range(3):
        try:
            log("GROK_REQUEST", {"attempt": attempt + 1})

            res = requests.post(GROK_URL, headers=headers, json=payload, timeout=60)

            if res.status_code != 200:
                log("GROK_ERROR_FULL", res.text)
                res.raise_for_status()

            data = res.json()
            text = data["choices"][0]["message"]["content"]

            log("GROK_SUCCESS", text[:200])
            return text

        except Exception as e:
            log("GROK_RETRY_ERROR", str(e))
            time.sleep(2 ** attempt)

    raise Exception("Grok API failed after retries")

# ─────────────────────────────────────────────
# JSON FIXER
# ─────────────────────────────────────────────
def extract_json(raw: str) -> dict:
    log("RAW_RESPONSE", raw[:300])

    # Try direct
    try:
        return json.loads(raw)
    except:
        pass

    # Extract JSON block
    match = re.search(r"\{.*\}", raw, re.DOTALL)
    if match:
        try:
            return json.loads(match.group())
        except Exception as e:
            log("JSON_PARSE_FAIL", str(e))

    raise ValueError("Invalid JSON from AI")

# ─────────────────────────────────────────────
# ROUTES
# ─────────────────────────────────────────────
@app.route("/")
def index():
    return send_from_directory(FRONTEND_DIR, "index.html")

@app.route("/health")
def health():
    return jsonify({
        "status": "ok",
        "api_key": bool(GROK_API_KEY)
    })

@app.route("/logs")
def logs():
    return jsonify(LOGS[-50:])

# ─────────────────────────────────────────────
# GENERATE TEST
# ─────────────────────────────────────────────
@app.route("/api/generate-test", methods=["POST"])
def generate_test():
    try:
        body = request.get_json(force=True)
        log("REQUEST_generate", body)

        prompt = f"""
Generate 5 MCQ questions in JSON format.
Return ONLY JSON.
"""

        raw = call_grok(prompt)
        parsed = extract_json(raw)

        return jsonify({"ok": True, "data": parsed})

    except Exception as e:
        log("ERROR_generate", str(e))
        return jsonify({"ok": False, "error": str(e)}), 500

# ─────────────────────────────────────────────
# ADAPTIVE TEST
# ─────────────────────────────────────────────
@app.route("/api/adaptive-test", methods=["POST"])
def adaptive_test():
    try:
        body = request.get_json(force=True)
        log("REQUEST_adaptive", body)

        raw = call_grok("Generate adaptive MCQs JSON")
        parsed = extract_json(raw)

        return jsonify({"ok": True, "data": parsed})

    except Exception as e:
        log("ERROR_adaptive", str(e))
        return jsonify({"ok": False, "error": str(e)}), 500

# ─────────────────────────────────────────────
# FEEDBACK
# ─────────────────────────────────────────────
@app.route("/api/feedback", methods=["POST"])
def feedback():
    try:
        body = request.get_json(force=True)
        log("REQUEST_feedback", body)

        text = call_grok("Give short feedback", max_tokens=200)

        return jsonify({"ok": True, "feedback": text.strip()})

    except Exception as e:
        log("ERROR_feedback", str(e))
        return jsonify({"ok": False, "error": str(e)}), 500

# ─────────────────────────────────────────────
# RUN
# ─────────────────────────────────────────────
if __name__ == "__main__":
    print("🚀 Backend running at http://localhost:5000")
    app.run(debug=True, port=5000)
