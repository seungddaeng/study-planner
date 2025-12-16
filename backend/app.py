import os
import json
import uuid
from pathlib import Path
from flask import Flask, render_template, request, jsonify, make_response

from .gemini_client import GeminiClient, get_redis_client, load_history, save_history

TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "templates"

app = Flask(__name__, template_folder=str(TEMPLATES_DIR))
app.secret_key = "dev-not-secure"

client = GeminiClient()
rdb = get_redis_client()

SESSION_COOKIE = "sp_session_id"

@app.get("/health")
def health():
    return {"status": "ok"}

@app.get("/")
def index():
    resp = make_response(render_template("index.html"))
    # Simple session id cookie so Redis memory is per browser
    sid = request.cookies.get(SESSION_COOKIE)
    if not sid:
        sid = str(uuid.uuid4())
        resp.set_cookie(SESSION_COOKIE, sid, max_age=60 * 60 * 24 * 30)  # 30 days
    return resp

@app.post("/api/chat")
def chat():
    payload = request.get_json(silent=True) or {}
    user_message = (payload.get("message") or "").strip()
    if not user_message:
        return jsonify({"error": "No message provided"}), 400

    sid = request.cookies.get(SESSION_COOKIE) or "anon"
    history = load_history(rdb, sid)

    response_text, new_history = client.generate_response(user_message, history=history)
    save_history(rdb, sid, new_history)

    return jsonify({"response": response_text})
