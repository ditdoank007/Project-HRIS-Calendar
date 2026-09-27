from functools import wraps

import requests
from flask import (
    Flask,
    jsonify,
    redirect,
    render_template,
    request,
    Response,
    session,
    url_for,
)

from config import Config
from werkzeug.middleware.proxy_fix import ProxyFix


app = Flask(__name__)
app.config.from_object(Config)

# Nginx Proxy Manager terminates HTTPS.
# Trust the forwarded scheme/host so Flask generates HTTPS URLs.
app.wsgi_app = ProxyFix(
    app.wsgi_app,
    x_for=1,
    x_proto=1,
    x_host=1,
)

app.config["PERMANENT_SESSION_LIFETIME"] = 7 * 24 * 60 * 60


def login_required(view_func):
    @wraps(view_func)
    def wrapped(*args, **kwargs):
        if not session.get("logged_in"):
            return redirect(url_for("login"))

        return view_func(*args, **kwargs)

    return wrapped


@app.route("/")
def login():
    if session.get("logged_in"):
        return redirect(url_for("dashboard"))

    return render_template("login.html")


@app.route("/api/login", methods=["POST"])
def api_login():
    data = request.get_json(silent=True) or {}

    username = str(data.get("username") or "").strip()
    password = str(data.get("password") or "").strip()
    remember = bool(data.get("remember"))

    if not username:
        return jsonify({
            "success": False,
            "message": "Username BDIP wajib diisi."
        }), 400

    if not password:
        return jsonify({
            "success": False,
            "message": "Password wajib diisi."
        }), 400

    try:
        response = requests.post(
            f"{app.config['BDIP_SSO_URL'].rstrip('/')}/api/auth/verify",
            json={
                "username": username,
                "password": password
            },
            timeout=15,
            verify="/etc/ssl/certs/ca-certificates.crt"
        )

        try:
            result = response.json()
        except Exception:
            result = {}

        if response.status_code != 200 or not result.get("success"):
            return jsonify({
                "success": False,
                "message": result.get(
                    "message",
                    "Username atau password BDIP tidak valid."
                )
            }), 401

        sso_data = result.get("data") or {}

        sso_username = (
            sso_data.get("username")
            or sso_data.get("userName")
            or username
        )

        sso_nip = str(
            sso_data.get("nip")
            or sso_data.get("NIP")
            or ""
        ).strip()

        sso_finger_id = str(
            sso_data.get("fingerId")
            or sso_data.get("fingerID")
            or sso_data.get("FingerID")
            or ""
        ).strip()

        sso_name = (
            sso_data.get("fullName")
            or sso_data.get("nama")
            or sso_data.get("name")
            or sso_username
        )

        if not sso_nip:
            return jsonify({
                "success": False,
                "message": (
                    "Login BDIP berhasil, tetapi NIP "
                    "tidak ditemukan pada identity BDIP."
                )
            }), 403

        session.clear()

        session["logged_in"] = True
        session["username"] = sso_username
        session["sso_username"] = sso_username
        session["nip"] = sso_nip
        session["nama"] = sso_name
        session["finger_id"] = sso_finger_id

        session.permanent = remember

        return jsonify({
            "success": True,
            "message": "Login SSO berhasil.",
            "user": {
                "username": sso_username,
                "nip": sso_nip,
                "nama": sso_name
            }
        })

    except requests.RequestException:
        return jsonify({
            "success": False,
            "message": "Server BDIP/SSO tidak dapat dihubungi."
        }), 502

    except Exception:
        app.logger.exception("Calendar SSO login error")

        return jsonify({
            "success": False,
            "message": "Terjadi kesalahan saat proses login SSO."
        }), 500


@app.route("/dashboard")
@login_required
def dashboard():
    return render_template(
        "dashboard.html",
        nama=session.get("nama"),
        nip=session.get("nip")
    )


@app.route("/calendar")
@login_required
def calendar_page():
    return render_template(
        "dashboard.html",
        nama=session.get("nama"),
        nip=session.get("nip"),
        active_menu="calendar"
    )


@app.route("/phone-calendar")
@login_required
def phone_calendar():
    return render_template(
        "dashboard.html",
        nama=session.get("nama"),
        nip=session.get("nip"),
        active_menu="phone"
    )


@app.route("/agenda")
@login_required
def agenda():
    return render_template(
        "dashboard.html",
        nama=session.get("nama"),
        nip=session.get("nip"),
        active_menu="agenda"
    )


@app.route("/plans")
@login_required
def plans():
    return render_template(
        "dashboard.html",
        nama=session.get("nama"),
        nip=session.get("nip"),
        active_menu="plans"
    )


@app.route("/plans/<jenis>")
@login_required
def plan_submission(jenis):
    jenis = str(jenis or "").strip().lower()

    if jenis not in {"cuti", "sakit", "ijin"}:
        return redirect(url_for("plans"))

    return render_template(
        "dashboard.html",
        nama=session.get("nama"),
        nip=session.get("nip"),
        active_menu=jenis
    )


@app.route("/api/phone-calendar-info")
@login_required
def api_phone_calendar_info():
    import requests
    from config import Config

    nip = session.get("nip")

    if not nip:
        return jsonify({
            "status": "error",
            "message": "NIP tidak ditemukan."
        }), 401

    try:
        response = requests.get(
            f"{Config.HRIS_INTERNAL_API_URL}/api/internal/calendar/sync-token",
            headers={
                "X-Calendar-Internal-Key": Config.HRIS_INTERNAL_API_KEY,
                "X-Calendar-NIP": nip,
            },
            timeout=15,
            verify="/etc/ssl/certs/ca-certificates.crt",
        )
    except requests.RequestException:
        return jsonify({
            "status": "error",
            "message": "Layanan kalender HRIS tidak tersedia."
        }), 502

    if response.status_code != 200:
        return jsonify({
            "status": "error",
            "message": "Gagal mendapatkan kalender handphone."
        }), response.status_code

    data = response.json()
    feed_path = data.get("feed_url")

    if not feed_path:
        return jsonify({
            "status": "error",
            "message": "Feed kalender tidak tersedia."
        }), 502

    feed_url = (
        f"{request.host_url.rstrip('/')}"
        f"/api/calendar/{feed_path.rsplit('/', 1)[-1]}"
    )

    return jsonify({
        "status": "success",
        "feed_url": feed_url,
        "webcal_url": feed_url.replace("https://", "webcal://", 1),
    })


@app.route("/api/personal-calendar")
@login_required
def api_personal_calendar():
    import requests
    from config import Config

    nip = session.get("nip")

    if not nip:
        return jsonify({
            "status": "error",
            "message": "NIP tidak ditemukan."
        }), 401

    try:
        year = int(request.args.get("year"))
        month = int(request.args.get("month"))
    except (TypeError, ValueError):
        return jsonify({
            "status": "error",
            "message": "Parameter year dan month wajib."
        }), 400

    try:
        response = requests.get(
            f"{Config.HRIS_INTERNAL_API_URL}/api/internal/calendar/personal",
            params={"year": year, "month": month},
            headers={
                "X-Calendar-Internal-Key": Config.HRIS_INTERNAL_API_KEY,
                "X-Calendar-NIP": nip,
            },
            timeout=15,
            verify="/etc/ssl/certs/ca-certificates.crt",
        )

        return jsonify(response.json()), response.status_code

    except Exception:
        app.logger.exception("Personal Calendar HRIS API error")
        return jsonify({
            "status": "error",
            "message": "Gagal mengambil data Personal Calendar."
        }), 502


@app.route("/api/calendar/<token>.ics")
def api_calendar_feed_proxy(token):

    if not token or len(token) > 150:
        return "Invalid calendar token", 400

    try:
        response = requests.get(
            f"{Config.HRIS_INTERNAL_API_URL}/api/calendar/feed/{token}.ics",
            timeout=15,
            verify="/etc/ssl/certs/ca-certificates.crt"
        )

    except requests.RequestException:
        return "Calendar feed unavailable", 502

    if response.status_code != 200:
        return "Calendar feed unavailable", response.status_code

    return Response(
        response.content,
        status=200,
        mimetype="text/calendar"
    )


@app.route("/api/logout", methods=["POST"])
def api_logout():
    session.clear()

    return jsonify({
        "success": True,
        "message": "Logout berhasil."
    })


@app.route("/health")
def health():
    return {
        "status": "ok",
        "service": "HRIS Reborn Calendar Portal"
    }


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=80)
