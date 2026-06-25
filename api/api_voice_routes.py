"""
api_voice_routes.py — Voice-related Flask API endpoints
========================================================
Mount this blueprint on the main Flask app:

    from api_voice_routes import voice_bp
    app.register_blueprint(voice_bp)

New endpoints
-------------
  GET  /voice/challenge          → random prompt for the user to speak
  POST /users/<id>/enrol/voice   → trigger voice enrolment sequence
  GET  /users/<id>/enrol/status  → returns both face + voice enrolment flags
  POST /dispense/request         → user submits chosen auth mode before dose
"""

from flask import Blueprint, jsonify, request, current_app
from functools import wraps

from core import voice_recogniser as vr

voice_bp = Blueprint("voice", __name__)


# ── Auth middleware (reuse existing token check pattern) ───────────────────

def require_token(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = current_app.config.get("API_TOKEN", "")
        auth  = request.headers.get("Authorization", "")
        if auth != f"Bearer {token}":
            return jsonify({"status": "error", "error": "Unauthorized"}), 401
        return f(*args, **kwargs)
    return decorated


# ── Endpoints ──────────────────────────────────────────────────────────────

@voice_bp.route("/voice/challenge", methods=["GET"])
@require_token
def get_challenge():
    """
    Returns a random passphrase for the user to speak.
    The app displays this text on screen; the Pi starts recording
    when the user taps 'Speak'.

    Response:
        { "status": "success", "data": { "prompt": "open my medicine" } }
    """
    prompt = vr.get_random_challenge()
    return jsonify({"status": "success", "data": {"prompt": prompt}}), 200


@voice_bp.route("/users/<int:user_id>/enrol/voice", methods=["POST"])
@require_token
def enrol_voice(user_id: int):
    """
    Initiates voice enrolment for a registered user.
    The Pi will record ENROL_SAMPLES utterances (3 by default).
    The app should display the current challenge prompt and instruct
    the user to speak it for each repetition.

    Response (success):
        { "status": "success", "data": { "user_id": 1 } }

    Response (failure):
        { "status": "error", "error": "<reason>" }
    """
    result = vr.enrol_user(user_id)
    if result["success"]:
        # TODO: update voice_enrolled = 1 in Users table via db helper
        return jsonify({"status": "success", "data": result}), 200
    return jsonify({"status": "error", "error": result["error"]}), 500


@voice_bp.route("/users/<int:user_id>/enrol/status", methods=["GET"])
@require_token
def enrol_status(user_id: int):
    """
    Returns enrolment status for both face and voice modalities.

    Response:
        {
          "status": "success",
          "data": {
            "user_id": 1,
            "face_enrolled": true,
            "voice_enrolled": false
          }
        }
    """
    # face_enrolled comes from DB (existing); voice_enrolled from file presence
    from database import get_user   # existing DB helper
    user = get_user(user_id)
    if not user:
        return jsonify({"status": "error", "error": "User not found"}), 404

    return jsonify({
        "status": "success",
        "data": {
            "user_id": user_id,
            "face_enrolled": bool(user["enrolment_status"]),
            "voice_enrolled": vr.is_enrolled(user_id),
        }
    }), 200


@voice_bp.route("/dispense/request", methods=["POST"])
@require_token
def dispense_request():
    """
    Called by the app when a dose is due and the user has chosen
    their preferred auth mode.

    Request body:
        { "user_id": 1, "schedule_id": 3, "auth_mode": "voice" }

    The Pi main loop reads this pending request and uses the specified
    mode when the next DispensEvent fires.

    Response:
        { "status": "success", "data": { "accepted": true } }
    """
    body = request.get_json(silent=True) or {}
    user_id     = body.get("user_id")
    schedule_id = body.get("schedule_id")
    auth_mode   = body.get("auth_mode", "face")

    if auth_mode not in ("face", "voice"):
        return jsonify({"status": "error", "error": "Invalid auth_mode"}), 400
    if not user_id:
        return jsonify({"status": "error", "error": "user_id required"}), 400

    # Store pending mode in app config so main loop can read it
    current_app.config["PENDING_AUTH"] = {
        "user_id": user_id,
        "schedule_id": schedule_id,
        "mode": auth_mode,
    }

    return jsonify({"status": "success", "data": {"accepted": True}}), 200
