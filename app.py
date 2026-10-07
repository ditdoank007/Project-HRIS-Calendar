from functools import wraps
from urllib.parse import urlparse

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
app.config["MAX_CONTENT_LENGTH"] = 1024 * 1024

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


def safe_next_url(value):
    value = str(value or "").strip()
    parsed = urlparse(value)
    if not value or parsed.scheme or parsed.netloc or not value.startswith("/") or value.startswith("//"):
        return "/dashboard"
    return value


@app.route("/")
@app.route("/login")
def login():
    next_url = safe_next_url(request.args.get("next"))
    if session.get("logged_in"):
        return redirect(next_url)

    return render_template("login.html", next_url=next_url)


@app.route("/api/login", methods=["POST"])
def api_login():
    data = request.get_json(silent=True) or {}

    username = str(data.get("username") or "").strip()
    password = str(data.get("password") or "").strip()
    remember = bool(data.get("remember"))
    next_url = safe_next_url(data.get("next"))

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
            "redirect_url": next_url,
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


@app.route("/rekam-medis-qrcode")
def rekam_medis_qrcode():
    token = str(request.args.get("token") or "").strip()
    if not token or len(token) > 150:
        return render_template(
            "rekam_medis_qrcode.html",
            token="",
            error="QR Rekam Medis tidak valid."
        ), 400

    return render_template(
        "rekam_medis_qrcode.html",
        token=token,
        logged_in=bool(session.get("logged_in")),
        nama=session.get("nama"),
        nip=session.get("nip"),
    )


@app.route("/api/rekam-medis-qrcode/info")
def api_rekam_medis_qrcode_info():
    token = str(request.args.get("token") or "").strip()
    if not token or len(token) > 150:
        return jsonify({"status": "error", "message": "Token QR tidak valid."}), 400

    try:
        response = requests.get(
            f"{Config.HRIS_INTERNAL_API_URL}/api/internal/calendar/agenda/rekam-medis/attendance-info",
            params={"token": token},
            headers=hris_internal_headers(),
            timeout=15,
            verify="/etc/ssl/certs/ca-certificates.crt",
        )
    except requests.RequestException:
        return jsonify({"status": "error", "message": "Layanan Rekam Medis HRIS tidak tersedia."}), 502

    try:
        payload = response.json()
    except Exception:
        payload = {"status": "error", "message": "Respons HRIS Rekam Medis tidak valid."}
    return jsonify(payload), response.status_code


@app.route("/api/rekam-medis-qrcode/employee", methods=["POST"])
@login_required
def api_rekam_medis_qrcode_employee():
    payload = request.get_json(silent=True) or {}
    token = str(payload.get("token") or "").strip()
    if not token:
        return jsonify({"status": "error", "message": "Token QR wajib diisi."}), 400

    try:
        response = requests.post(
            f"{Config.HRIS_INTERNAL_API_URL}/api/internal/calendar/agenda/rekam-medis/attendance/employee",
            json={"token": token},
            headers=hris_internal_headers(),
            timeout=15,
            verify="/etc/ssl/certs/ca-certificates.crt",
        )
    except requests.RequestException:
        return jsonify({"status": "error", "message": "Layanan Rekam Medis HRIS tidak tersedia."}), 502

    try:
        payload = response.json()
    except Exception:
        payload = {"status": "error", "message": "Respons HRIS Rekam Medis tidak valid."}
    return jsonify(payload), response.status_code


@app.route("/api/rekam-medis-qrcode/guest", methods=["POST"])
def api_rekam_medis_qrcode_guest():
    payload = request.get_json(silent=True) or {}
    token = str(payload.get("token") or "").strip()

    if not token:
        return jsonify({"status": "error", "message": "Token QR wajib diisi."}), 400

    try:
        response = requests.post(
            f"{Config.HRIS_INTERNAL_API_URL}/api/internal/calendar/agenda/rekam-medis/attendance/guest",
            json={
                "token": token,
                "nik": str(payload.get("nik") or "").strip(),
                "nama": str(payload.get("nama") or "").strip(),
                "jenis_kelamin": str(payload.get("jenis_kelamin") or "").strip().upper(),
                "instansi": str(payload.get("instansi") or "").strip(),
                "email": str(payload.get("email") or "").strip(),
                "no_handphone": str(payload.get("no_handphone") or "").strip(),
                "tanda_tangan": payload.get("tanda_tangan"),
            },
            headers={
                "X-Calendar-Internal-Key": Config.HRIS_INTERNAL_API_KEY,
            },
            timeout=20,
            verify="/etc/ssl/certs/ca-certificates.crt",
        )
    except requests.RequestException:
        return jsonify({"status": "error", "message": "Layanan Rekam Medis HRIS tidak tersedia."}), 502

    try:
        payload = response.json()
    except Exception:
        payload = {"status": "error", "message": "Respons HRIS Rekam Medis tidak valid."}
    return jsonify(payload), response.status_code


@app.route("/absen-qrcode")
def absen_qrcode():
    token = str(request.args.get("token") or "").strip()
    if not token or len(token) > 150:
        return render_template(
            "absen_qrcode.html",
            token="",
            error="QR rapat tidak valid."
        ), 400

    return render_template(
        "absen_qrcode.html",
        token=token,
        logged_in=bool(session.get("logged_in")),
        nama=session.get("nama"),
        nip=session.get("nip"),
    )


@app.route("/api/absen-qrcode/info")
def api_absen_qrcode_info():
    token = str(request.args.get("token") or "").strip()
    if not token or len(token) > 150:
        return jsonify({"status": "error", "message": "Token QR tidak valid."}), 400

    headers = hris_internal_headers()
    try:
        response = requests.get(
            f"{Config.HRIS_INTERNAL_API_URL}/api/internal/calendar/agenda/rapat/attendance-info",
            params={"token": token},
            headers=headers,
            timeout=15,
            verify="/etc/ssl/certs/ca-certificates.crt",
        )
    except requests.RequestException:
        return jsonify({
            "status": "error",
            "message": "Layanan absensi rapat tidak tersedia."
        }), 502

    try:
        payload = response.json()
    except Exception:
        payload = {
            "status": "error",
            "message": "Respons HRIS tidak valid."
        }

    return jsonify(payload), response.status_code


@app.route("/api/absen-qrcode/employee", methods=["POST"])
@login_required
def api_absen_qrcode_employee():
    payload = request.get_json(silent=True) or {}
    token = str(payload.get("token") or "").strip()
    if not token:
        return jsonify({"status": "error", "message": "Token QR wajib diisi."}), 400

    try:
        response = requests.post(
            f"{Config.HRIS_INTERNAL_API_URL}/api/internal/calendar/agenda/rapat/attendance/employee",
            json={"token": token},
            headers=hris_internal_headers(),
            timeout=15,
            verify="/etc/ssl/certs/ca-certificates.crt",
        )
    except requests.RequestException:
        return jsonify({
            "status": "error",
            "message": "Layanan absensi rapat tidak tersedia."
        }), 502

    try:
        payload = response.json()
    except Exception:
        payload = {
            "status": "error",
            "message": "Respons HRIS tidak valid."
        }

    return jsonify(payload), response.status_code


@app.route("/api/absen-qrcode/guest", methods=["POST"])
def api_absen_qrcode_guest():
    payload = request.get_json(silent=True) or {}

    token = str(payload.get("token") or "").strip()
    name = str(payload.get("name") or "").strip()
    email = str(payload.get("email") or "").strip()
    nip_or_finger = str(payload.get("nip_or_finger") or "").strip()
    signature_data = payload.get("signature_data")
    attendance_key = str(payload.get("attendance_key") or "").strip()

    if not token or len(token) > 150:
        return jsonify({"status": "error", "message": "Token QR tidak valid."}), 400
    if len(name) > 150 or len(email) > 255 or len(nip_or_finger) > 50:
        return jsonify({"status": "error", "message": "Data tamu terlalu panjang."}), 400
    if not signature_data or len(str(signature_data)) > 750000:
        return jsonify({"status": "error", "message": "Tanda tangan tidak valid atau terlalu besar."}), 400

    try:
        response = requests.post(
            f"{Config.HRIS_INTERNAL_API_URL}/api/internal/calendar/agenda/rapat/attendance/guest",
            json={
                "token": token,
                "name": name,
                "email": email,
                "nip_or_finger": nip_or_finger,
                "signature_data": signature_data,
                "attendance_key": attendance_key,
            },
            headers={
                "X-Calendar-Internal-Key": Config.HRIS_INTERNAL_API_KEY,
            },
            timeout=20,
            verify="/etc/ssl/certs/ca-certificates.crt",
        )
    except requests.RequestException:
        return jsonify({
            "status": "error",
            "message": "Layanan absensi rapat tidak tersedia."
        }), 502

    try:
        payload = response.json()
    except Exception:
        payload = {
            "status": "error",
            "message": "Respons HRIS tidak valid."
        }

    return jsonify(payload), response.status_code


@app.route("/buku-tamu")
def buku_tamu():
    token = str(request.args.get("token") or "").strip()
    if not token or len(token) > 150:
        return render_template("buku_tamu.html", token="", error="QR Buku Tamu tidak valid."), 400
    return render_template("buku_tamu.html", token=token)


@app.route("/api/buku-tamu/info")
def api_buku_tamu_info():
    token = str(request.args.get("token") or "").strip()
    if not token or len(token) > 150:
        return jsonify({"status": "error", "message": "Token QR tidak valid."}), 400
    try:
        response = requests.get(
            f"{Config.HRIS_INTERNAL_API_URL}/api/internal/calendar/buku-tamu/info",
            params={"token": token},
            headers={"X-Calendar-Internal-Key": Config.HRIS_INTERNAL_API_KEY},
            timeout=15,
            verify="/etc/ssl/certs/ca-certificates.crt",
        )
    except requests.RequestException:
        return jsonify({"status": "error", "message": "Layanan Buku Tamu HRIS tidak tersedia."}), 502
    try:
        payload = response.json()
    except Exception:
        payload = {"status": "error", "message": "Respons HRIS tidak valid."}
    return jsonify(payload), response.status_code


@app.route("/api/buku-tamu/pegawai")
def api_buku_tamu_pegawai():
    q = str(request.args.get("q") or "").strip()
    if len(q) < 2:
        return jsonify({"status": "success", "data": []})
    try:
        response = requests.get(
            f"{Config.HRIS_INTERNAL_API_URL}/api/internal/calendar/buku-tamu/pegawai",
            params={"q": q},
            headers={"X-Calendar-Internal-Key": Config.HRIS_INTERNAL_API_KEY},
            timeout=15,
            verify="/etc/ssl/certs/ca-certificates.crt",
        )
    except requests.RequestException:
        return jsonify({"status": "error", "message": "Layanan data pegawai HRIS tidak tersedia."}), 502
    try:
        payload = response.json()
    except Exception:
        payload = {"status": "error", "message": "Respons HRIS tidak valid."}
    return jsonify(payload), response.status_code


@app.route("/api/buku-tamu/submit", methods=["POST"])
def api_buku_tamu_submit():
    payload = request.get_json(silent=True) or {}
    token = str(payload.get("token") or "").strip()
    signature_data = payload.get("signature_data")
    if not token or len(token) > 150:
        return jsonify({"status": "error", "message": "Token QR tidak valid."}), 400
    if not signature_data or len(str(signature_data)) > 750000:
        return jsonify({"status": "error", "message": "Tanda tangan tidak valid atau terlalu besar."}), 400
    safe_payload = {
        "token": token,
        "nama": str(payload.get("nama") or "").strip(),
        "instansi": str(payload.get("instansi") or "").strip(),
        "no_hp": str(payload.get("no_hp") or "").strip(),
        "keperluan": str(payload.get("keperluan") or "").strip(),
        "keterangan": str(payload.get("keterangan") or "").strip(),
        "pegawai_nip": str(payload.get("pegawai_nip") or "").strip(),
        "pegawai_nama": str(payload.get("pegawai_nama") or "").strip(),
        "signature_data": signature_data,
    }
    try:
        response = requests.post(
            f"{Config.HRIS_INTERNAL_API_URL}/api/internal/calendar/buku-tamu/submit",
            json=safe_payload,
            headers={"X-Calendar-Internal-Key": Config.HRIS_INTERNAL_API_KEY},
            timeout=20,
            verify="/etc/ssl/certs/ca-certificates.crt",
        )
    except requests.RequestException:
        return jsonify({"status": "error", "message": "Layanan Buku Tamu HRIS tidak tersedia."}), 502
    try:
        result = response.json()
    except Exception:
        result = {"status": "error", "message": "Respons HRIS tidak valid."}
    return jsonify(result), response.status_code


@app.route("/dashboard")
@login_required
def dashboard():
    return render_template(
        "dashboard.html",
        nama=session.get("nama"),
        nip=session.get("nip")
    )


@app.route("/dashboard/infografis")
@login_required
def dashboard_infografis_page():
    return render_template(
        "dashboard.html",
        nama=session.get("nama"),
        nip=session.get("nip"),
        active_menu="infografis"
    )


@app.route("/dashboard/pelanggaran")
@login_required
def dashboard_pelanggaran_page():
    return render_template(
        "dashboard.html",
        nama=session.get("nama"),
        nip=session.get("nip"),
        active_menu="pelanggaran"
    )


@app.route("/dashboard/struktur-organisasi")
@login_required
def dashboard_struktur_organisasi_page():
    return render_template(
        "dashboard.html",
        nama=session.get("nama"),
        nip=session.get("nip"),
        active_menu="struktur-organisasi"
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
    agenda_tab = str(request.args.get("tab") or "overview").strip().lower()

    if agenda_tab not in {"overview", "rapat", "disposisi", "kesamaptaan"}:
        agenda_tab = "overview"

    return render_template(
        "dashboard.html",
        nama=session.get("nama"),
        nip=session.get("nip"),
        active_menu="agenda",
        agenda_tab=agenda_tab
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

@app.route("/benefit/tunjangan-kinerja")
@login_required
def benefit_tunjangan_kinerja():
    return render_template(
        "dashboard.html",
        nama=session.get("nama"),
        nip=session.get("nip"),
        active_menu="benefit-tunkin"
    )


@app.route("/benefit/uang-makan")
@login_required
def benefit_uang_makan():
    return render_template(
        "dashboard.html",
        nama=session.get("nama"),
        nip=session.get("nip"),
        active_menu="benefit-um"
    )


@app.route("/benefit/uang-siaga")
@login_required
def benefit_uang_siaga():
    return render_template(
        "dashboard.html",
        nama=session.get("nama"),
        nip=session.get("nip"),
        active_menu="benefit-siaga"
    )



def hris_internal_headers():
    nip = str(session.get("nip") or "").strip()
    return {
        "X-Calendar-Internal-Key": Config.HRIS_INTERNAL_API_KEY,
        "X-Calendar-NIP": nip,
    }


def _proxy_personal_benefit(path, params):
    nip = str(session.get("nip") or "").strip()
    if not nip:
        return jsonify({
            "status": "error",
            "message": "NIP tidak ditemukan."
        }), 401

    try:
        response = requests.get(
            f"{Config.HRIS_INTERNAL_API_URL}{path}",
            params=params,
            headers=hris_internal_headers(),
            timeout=20,
            verify="/etc/ssl/certs/ca-certificates.crt",
        )
    except requests.RequestException:
        return jsonify({
            "status": "error",
            "message": "Layanan Benefit HRIS tidak tersedia."
        }), 502

    try:
        payload = response.json()
    except Exception:
        return jsonify({
            "status": "error",
            "message": "Respons Benefit HRIS tidak valid."
        }), 502

    return jsonify(payload), response.status_code


@app.route("/api/benefit/tunjangan-kinerja")
@login_required
def api_benefit_tunjangan_kinerja():
    start = str(request.args.get("start") or "").strip()
    end = str(request.args.get("end") or "").strip()

    if not start or not end:
        return jsonify({
            "status": "error",
            "message": "Periode tunjangan belum lengkap."
        }), 400

    return _proxy_personal_benefit(
        "/api/internal/calendar/benefit/tunjangan-kinerja",
        {"start": start, "end": end},
    )


@app.route("/api/benefit/uang-makan")
@login_required
def api_benefit_uang_makan():
    return _proxy_personal_benefit(
        "/api/internal/calendar/benefit/uang-makan",
        {
            "year": request.args.get("year"),
            "month": request.args.get("month"),
        },
    )


@app.route("/api/benefit/uang-siaga")
@login_required
def api_benefit_uang_siaga():
    return _proxy_personal_benefit(
        "/api/internal/calendar/benefit/uang-siaga",
        {
            "year": request.args.get("year"),
            "month": request.args.get("month"),
        },
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


@app.route("/api/agenda/dinas-luar/pdf")
@login_required
def api_agenda_dinas_luar_pdf():
    import requests
    from config import Config

    guid_sprin = str(request.args.get("guid_sprin") or "").strip()
    if not guid_sprin or len(guid_sprin) > 150:
        return jsonify({
            "status": "error",
            "message": "SPRIN Dinas Luar tidak valid."
        }), 400

    try:
        response = requests.get(
            f"{Config.HRIS_INTERNAL_API_URL}/api/internal/calendar/dinas-luar/pdf",
            params={"guid_sprin": guid_sprin},
            headers=hris_internal_headers(),
            timeout=20,
            verify="/etc/ssl/certs/ca-certificates.crt",
        )
    except requests.RequestException:
        return jsonify({
            "status": "error",
            "message": "Layanan SPRIN Dinas Luar HRIS tidak tersedia."
        }), 502

    if response.status_code != 200:
        try:
            payload = response.json()
        except Exception:
            payload = {
                "status": "error",
                "message": "SPRIN Dinas Luar tidak dapat diakses."
            }
        return jsonify(payload), response.status_code

    return Response(
        response.content,
        status=200,
        mimetype=response.headers.get("Content-Type", "application/pdf"),
        headers={
            "Content-Disposition": response.headers.get(
                "Content-Disposition",
                "inline"
            )
        },
    )


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

    # Calendar subscription must always be revalidated by consumers such as
    # Google Calendar. Do not allow this proxy response to be stored as a
    # reusable/stale calendar snapshot.
    return Response(
        response.content,
        status=200,
        mimetype="text/calendar",
        headers={
            "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
            "Pragma": "no-cache",
            "Expires": "0",
            "Vary": "*",
        },
    )



@app.route("/api/agenda/kesamaptaan")
@login_required
def api_agenda_kesamaptaan():
    try:
        response = requests.get(
            f"{Config.HRIS_INTERNAL_API_URL}/api/internal/calendar/kesamaptaan/agenda",
            headers=hris_internal_headers(),
            timeout=15,
            verify="/etc/ssl/certs/ca-certificates.crt",
        )
    except requests.RequestException:
        return jsonify({
            "status": "error",
            "message": "Layanan Kesamaptaan HRIS tidak tersedia."
        }), 502

    try:
        payload = response.json()
    except Exception:
        payload = {"status": "error", "message": "Respons Kesamaptaan HRIS tidak valid."}

    return jsonify(payload), response.status_code


@app.route("/api/agenda/piket-siaga/pdf")
@login_required
def api_agenda_piket_siaga_pdf():
    key = str(request.args.get("key") or "").strip()
    if not key or len(key) > 200:
        return jsonify({"status": "error", "message": "Dokumen Piket Siaga tidak valid."}), 400

    try:
        response = requests.get(
            f"{Config.HRIS_INTERNAL_API_URL}/api/internal/calendar/piket-siaga/pdf",
            params={"key": key},
            headers=hris_internal_headers(),
            timeout=20,
            verify="/etc/ssl/certs/ca-certificates.crt",
        )
    except requests.RequestException:
        return jsonify({
            "status": "error",
            "message": "Layanan PDF Piket Siaga HRIS tidak tersedia."
        }), 502

    if response.status_code != 200:
        try:
            payload = response.json()
        except Exception:
            payload = {"status": "error", "message": "PDF Piket Siaga tidak dapat diakses."}
        return jsonify(payload), response.status_code

    return Response(
        response.content,
        status=200,
        mimetype=response.headers.get("Content-Type", "application/pdf"),
        headers={
            "Content-Disposition": response.headers.get(
                "Content-Disposition",
                "inline"
            )
        },
    )


@app.route("/api/agenda/kesamaptaan/<int:event_id>/pdf")
@login_required
def api_agenda_kesamaptaan_pdf(event_id):
    try:
        response = requests.get(
            f"{Config.HRIS_INTERNAL_API_URL}/api/internal/calendar/kesamaptaan/{event_id}/pdf",
            headers=hris_internal_headers(),
            timeout=20,
            verify="/etc/ssl/certs/ca-certificates.crt",
        )
    except requests.RequestException:
        return jsonify({
            "status": "error",
            "message": "Layanan PDF Kesamaptaan HRIS tidak tersedia."
        }), 502

    if response.status_code != 200:
        try:
            payload = response.json()
        except Exception:
            payload = {"status": "error", "message": "PDF Kesamaptaan tidak dapat diakses."}
        return jsonify(payload), response.status_code

    return Response(
        response.content,
        status=200,
        mimetype=response.headers.get("Content-Type", "application/pdf"),
        headers={
            "Content-Disposition": response.headers.get(
                "Content-Disposition",
                "inline"
            )
        },
    )


@app.route("/api/agenda/rapat")
@login_required
def api_agenda_rapat():
    headers = hris_internal_headers()

    if not headers["X-Calendar-NIP"]:
        return jsonify({
            "status": "error",
            "message": "Identitas pegawai tidak ditemukan."
        }), 401

    try:
        response = requests.get(
            f"{Config.HRIS_INTERNAL_API_URL}/api/internal/calendar/agenda/rapat",
            headers=headers,
            timeout=15,
            verify="/etc/ssl/certs/ca-certificates.crt",
        )
    except requests.RequestException:
        return jsonify({
            "status": "error",
            "message": "Layanan Agenda Rapat HRIS tidak tersedia."
        }), 502

    try:
        payload = response.json()
    except Exception:
        return jsonify({
            "status": "error",
            "message": "Respons Agenda Rapat HRIS tidak valid."
        }), 502

    return jsonify(payload), response.status_code


@app.route("/api/calendar/my-agenda")
@login_required
def api_calendar_my_agenda():
    try:
        response = requests.get(
            f"{Config.HRIS_INTERNAL_API_URL}/api/internal/calendar/my-agenda",
            headers=hris_internal_headers(),
            timeout=15,
            verify="/etc/ssl/certs/ca-certificates.crt",
        )
    except requests.RequestException:
        return jsonify({
            "status": "error",
            "message": "Layanan Agenda Kalender HRIS tidak tersedia."
        }), 502

    content_type = str(response.headers.get("Content-Type") or "").lower()

    if "application/json" not in content_type:
        app.logger.error(
            "HRIS personal agenda returned non-JSON response: status=%s content_type=%s",
            response.status_code,
            content_type,
        )
        return jsonify({
            "status": "error",
            "message": (
                "Respons Agenda Kalender HRIS tidak valid "
                f"(HTTP {response.status_code})."
            )
        }), 502

    try:
        payload = response.json()
    except ValueError:
        app.logger.error(
            "HRIS personal agenda returned invalid JSON: status=%s",
            response.status_code,
        )
        return jsonify({
            "status": "error",
            "message": "Respons Agenda Kalender HRIS tidak valid."
        }), 502

    return jsonify(payload), response.status_code


@app.route("/api/agenda/rapat/<int:event_id>/notulen")
@login_required
def api_agenda_rapat_notulen(event_id):
    headers = hris_internal_headers()

    if not headers["X-Calendar-NIP"]:
        return jsonify({
            "status": "error",
            "message": "Identitas pegawai tidak ditemukan."
        }), 401

    try:
        response = requests.get(
            f"{Config.HRIS_INTERNAL_API_URL}/api/internal/calendar/agenda/rapat/{event_id}/notulen",
            headers=headers,
            timeout=15,
            verify="/etc/ssl/certs/ca-certificates.crt",
        )
    except requests.RequestException:
        return jsonify({
            "status": "error",
            "message": "Layanan Notulen HRIS tidak tersedia."
        }), 502

    if response.status_code != 200:
        try:
            payload = response.json()
        except Exception:
            payload = {
                "status": "error",
                "message": "Notulen tidak dapat diakses."
            }
        return jsonify(payload), response.status_code

    return Response(
        response.content,
        status=200,
        mimetype=response.headers.get("Content-Type", "application/pdf"),
        headers={
            "Content-Disposition": response.headers.get(
                "Content-Disposition",
                "inline"
            )
        },
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



# Restored personal dashboard APIs and submission routes

@app.route("/api/submission-summary")
@login_required
def api_submission_summary():
    """
    Ringkasan hari CUTI / SAKIT / IJIN yang sudah masuk
    ke Personal Calendar pada tahun berjalan.

    Sumber data tetap HRIS melalui internal Personal Calendar API.
    """
    import concurrent.futures
    from datetime import datetime

    nip = session.get("nip")

    if not nip:
        return jsonify({
            "status": "error",
            "message": "NIP tidak ditemukan."
        }), 401

    year = datetime.now().year

    def load_month(month):
        try:
            response = requests.get(
                f"{Config.HRIS_INTERNAL_API_URL}/api/internal/calendar/personal",
                params={"year": year, "month": month},
                headers={
                    "X-Calendar-Internal-Key": Config.HRIS_INTERNAL_API_KEY,
                    "X-Calendar-NIP": nip,
                },
                timeout=10,
                verify="/etc/ssl/certs/ca-certificates.crt",
            )

            if response.status_code != 200:
                return []

            payload = response.json() or {}
            return payload.get("data") or []

        except requests.RequestException:
            return []

    events = []

    with concurrent.futures.ThreadPoolExecutor(max_workers=6) as executor:
        for month_events in executor.map(load_month, range(1, 13)):
            events.extend(month_events)

    summary = {
        "CUTI": 0,
        "SAKIT": 0,
        "IJIN": 0,
    }

    for event in events:
        event_type = str(
            event.get("type")
            or event.get("event_type")
            or ""
        ).strip().upper()

        if event_type in summary:
            summary[event_type] += 1

    return jsonify({
        "status": "success",
        "year": year,
        "data": summary,
    })


@app.route("/api/dashboard/pelanggaran")
@login_required
def api_dashboard_pelanggaran():
    tahun = request.args.get("tahun") or str(__import__("datetime").datetime.now().year)
    try:
        response = requests.get(
            f"{Config.HRIS_INTERNAL_API_URL}/api/internal/calendar/pelanggaran",
            params={"tahun": tahun},
            headers=hris_internal_headers(),
            timeout=20,
            verify="/etc/ssl/certs/ca-certificates.crt",
        )
    except requests.RequestException:
        return jsonify({"status":"error","message":"Layanan Pelanggaran HRIS tidak tersedia."}), 502
    try:
        payload = response.json()
    except Exception:
        return jsonify({"status":"error","message":"Respons Pelanggaran HRIS tidak valid."}), 502
    return jsonify(payload), response.status_code


@app.route("/api/dashboard/struktur-organisasi")
@login_required
def api_dashboard_struktur_organisasi():
    try:
        response = requests.get(
            f"{Config.HRIS_INTERNAL_API_URL}/api/internal/calendar/struktur-organisasi",
            headers=hris_internal_headers(),
            timeout=20,
            verify="/etc/ssl/certs/ca-certificates.crt",
        )
    except requests.RequestException:
        return jsonify({"status":"error","message":"Layanan Struktur Organisasi HRIS tidak tersedia."}), 502
    try:
        payload = response.json()
    except Exception:
        return jsonify({"status":"error","message":"Respons Struktur Organisasi HRIS tidak valid."}), 502
    return jsonify(payload), response.status_code


@app.route("/api/dashboard/infografis")
@login_required
def api_dashboard_infografis():
    try:
        response = requests.get(
            f"{Config.HRIS_INTERNAL_API_URL}/api/internal/calendar/infografis",
            headers=hris_internal_headers(),
            timeout=15,
            verify="/etc/ssl/certs/ca-certificates.crt",
        )
    except requests.RequestException:
        return jsonify({
            "status": "error",
            "message": "Layanan Infografis HRIS tidak tersedia."
        }), 502

    try:
        payload = response.json()
    except Exception:
        return jsonify({
            "status": "error",
            "message": "Respons Infografis HRIS tidak valid."
        }), 502

    return jsonify(payload), response.status_code


@app.route("/api/dashboard-summary")
@login_required
def api_dashboard_summary():
    """
    Ringkasan Dashboard Pribadi berbasis data real HRIS Reborn.

    Sumber utama:
    /api/internal/calendar/personal

    Event yang dihitung sampai dengan hari ini:
    - DINAS_LUAR: seluruh hari dalam rentang Dinas Luar
      (DL / OP / SD) dan dihitung unik per tanggal.
    - SAKIT: event SAKIT dari ABSENSI.
    - IJIN: event IJIN dari ABSENSI.
    - CUTI: event CUTI dari ABSENSI.

    Data diambil berdasarkan NIP pegawai yang sedang login.
    """
    import concurrent.futures
    from datetime import date, timedelta
    from zoneinfo import ZoneInfo

    nip = session.get("nip")

    if not nip:
        return jsonify({
            "status": "error",
            "message": "NIP tidak ditemukan."
        }), 401

    now_jakarta = __import__("datetime").datetime.now(
        ZoneInfo("Asia/Jakarta")
    )
    today = now_jakarta.date()
    current_hour = now_jakarta.hour

    year = today.year
    year_start = date(year, 1, 1)

    # Identitas pegawai untuk sapaan portal diambil dari Master Pegawai HRIS Reborn.
    # Jika NIP belum memiliki record master, UI menggunakan fallback "-".
    profile_name = "-"
    profile_gender = ""

    try:
        profile_response = requests.get(
            f"{Config.HRIS_INTERNAL_API_URL}/api/internal/calendar/employee-profile",
            headers={
                "X-Calendar-Internal-Key": Config.HRIS_INTERNAL_API_KEY,
                "X-Calendar-NIP": nip,
            },
            timeout=10,
            verify="/etc/ssl/certs/ca-certificates.crt",
        )

        if profile_response.status_code == 200:
            profile_payload = profile_response.json() or {}
            profile = profile_payload.get("data") or {}

            profile_name = str(
                profile.get("nama") or "-"
            ).strip() or "-"

            profile_gender = str(
                profile.get("jenis_kel") or ""
            ).strip()

    except (requests.RequestException, ValueError):
        app.logger.warning(
            "Dashboard HRIS employee profile unavailable for NIP %s",
            nip,
        )

    def load_month(month):
        try:
            response = requests.get(
                f"{Config.HRIS_INTERNAL_API_URL}/api/internal/calendar/personal",
                params={"year": year, "month": month},
                headers={
                    "X-Calendar-Internal-Key": Config.HRIS_INTERNAL_API_KEY,
                    "X-Calendar-NIP": nip,
                },
                timeout=10,
                verify="/etc/ssl/certs/ca-certificates.crt",
            )

            if response.status_code != 200:
                app.logger.warning(
                    "Dashboard HRIS calendar month %s returned %s",
                    month,
                    response.status_code,
                )
                return []

            payload = response.json() or {}
            return payload.get("data") or []

        except requests.RequestException:
            app.logger.exception(
                "Dashboard HRIS calendar request failed for month %s",
                month,
            )
            return []

    events = []

    with concurrent.futures.ThreadPoolExecutor(max_workers=6) as executor:
        for month_events in executor.map(load_month, range(1, 13)):
            events.extend(month_events)

    # Set tanggal dipakai supaya event yang muncul berulang pada
    # beberapa request bulan tidak dihitung dua kali.
    day_sets = {
        "DINAS_LUAR": set(),
        "SAKIT": set(),
        "IJIN": set(),
        "CUTI": set(),
    }

    def parse_date(value):
        try:
            return date.fromisoformat(str(value)[:10])
        except (TypeError, ValueError):
            return None

    for event in events:
        event_type = str(
            event.get("type")
            or event.get("event_type")
            or ""
        ).strip().upper()

        if event_type not in day_sets:
            continue

        start = parse_date(event.get("start"))
        end = parse_date(event.get("end")) or start

        if not start or not end:
            continue

        if end < start:
            end = start

        # Dashboard hanya menghitung hari yang sudah dijalani sampai hari ini.
        start = max(start, year_start)
        end = min(end, today)

        if end < start:
            continue

        current = start
        while current <= end:
            day_sets[event_type].add(current)
            current += timedelta(days=1)

    days_passed = max((today - year_start).days, 0)
    next_year_start = date(year + 1, 1, 1)
    days_remaining = max((next_year_start - today).days - 1, 0)

    return jsonify({
        "status": "success",
        "year": year,
        "today": today.isoformat(),
        "hour": current_hour,
        "days_passed": days_passed,
        "days_remaining": days_remaining,
        "nip": nip,
        "nama": profile_name,
        "jenis_kel": profile_gender,
        "data": {
            "DINAS_LUAR": len(day_sets["DINAS_LUAR"]),
            "SAKIT": len(day_sets["SAKIT"]),
            "IJIN": len(day_sets["IJIN"]),
            "CUTI": len(day_sets["CUTI"]),
        },
    })


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
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=80)
