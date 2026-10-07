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

    next_url = str(request.args.get("next") or "").strip()
    if not next_url.startswith("/") or next_url.startswith("//"):
        next_url = "/dashboard"

    return render_template("login.html", next_url=next_url)


@app.route("/api/login", methods=["POST"])
def api_login():
    data = request.get_json(silent=True) or {}

    username = str(data.get("username") or "").strip()
    password = str(data.get("password") or "").strip()
    remember = bool(data.get("remember"))
    next_url = str(data.get("next") or "").strip()
    if not next_url.startswith("/") or next_url.startswith("//"):
        next_url = "/dashboard"

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
            },
            "redirect_to": next_url
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


def _hris_rekam_medis_request(path, method="GET", **kwargs):
    """Proxy public QR scan requests to HRIS through the private internal API."""
    headers = kwargs.pop("headers", {}) or {}
    headers.update({
        "X-Calendar-Internal-Key": Config.HRIS_INTERNAL_API_KEY,
    })
    return requests.request(
        method,
        f"{Config.HRIS_INTERNAL_API_URL.rstrip('/')}{path}",
        headers=headers,
        timeout=20,
        verify="/etc/ssl/certs/ca-certificates.crt",
        **kwargs,
    )


@app.route("/rekam-medis/scan/<token>")
def rekam_medis_scan(token):
    token = str(token or "").strip()
    if not token or len(token) > 150:
        return render_template(
            "rekam_medis_scan.html",
            success=False,
            message="QR Code Rekam Medis tidak valid.",
        ), 400

    nip = str(session.get("nip") or "").strip()
    headers = {}
    if nip:
        headers["X-Calendar-NIP"] = nip

    try:
        response = _hris_rekam_medis_request(
            "/api/internal/calendar/agenda/rekam-medis/attendance-info",
            params={"token": token},
            headers=headers,
        )
        payload = response.json()
    except (requests.RequestException, ValueError):
        app.logger.exception("Rekam Medis QR info request failed")
        return render_template(
            "rekam_medis_scan.html",
            success=False,
            message="Layanan Rekam Medis HRIS tidak dapat dihubungi.",
        ), 502

    if response.status_code != 200 or payload.get("status") != "success":
        return render_template(
            "rekam_medis_scan.html",
            success=False,
            message=payload.get("message", "QR Rekam Medis tidak dapat diproses."),
        ), response.status_code

    info = payload.get("data") or {}
    mode = str(request.args.get("mode") or "").strip().lower()

    # QR Rekam Medis selalu menampilkan pilihan peserta terlebih dahulu.
    if mode == "pegawai":
        if not session.get("logged_in"):
            return redirect(
                url_for(
                    "login",
                    next=f"/rekam-medis/scan/{token}?mode=pegawai",
                )
            )

        try:
            response = _hris_rekam_medis_request(
                "/api/internal/calendar/agenda/rekam-medis/attendance/employee",
                method="POST",
                headers={"X-Calendar-NIP": str(session.get("nip") or "")},
                json={"token": token},
            )
            payload = response.json()
        except (requests.RequestException, ValueError):
            app.logger.exception("Rekam Medis employee scan request failed")
            return render_template(
                "rekam_medis_scan.html",
                success=False,
                message="Gagal mendaftarkan kehadiran pegawai.",
                info=info,
                token=token,
                mode=mode,
            ), 502

        return render_template(
            "rekam_medis_scan.html",
            success=response.status_code == 200 and payload.get("status") == "success",
            already=not bool(payload.get("created")),
            message=payload.get("message", "Scan QR berhasil."),
            info=info,
            token=token,
            mode=mode,
            peserta=payload.get("data"),
        ), response.status_code

    if mode == "non-pegawai":
        return render_template(
            "rekam_medis_scan.html",
            success=False,
            info=info,
            token=token,
            mode=mode,
        )

    return render_template(
        "rekam_medis_scan.html",
        success=False,
        info=info,
        token=token,
        mode="",
    )


@app.route("/api/rekam-medis/scan/non-pegawai", methods=["POST"])
def api_rekam_medis_scan_non_pegawai():
    payload = request.get_json(silent=True) or {}
    token = str(payload.get("token") or "").strip()

    try:
        response = _hris_rekam_medis_request(
            "/api/internal/calendar/agenda/rekam-medis/attendance/guest",
            method="POST",
            json=payload,
        )
        try:
            result = response.json()
        except ValueError:
            result = {
                "status": "error",
                "message": "Respons layanan Rekam Medis HRIS tidak valid.",
            }
        return jsonify(result), response.status_code
    except requests.RequestException:
        app.logger.exception("Rekam Medis non-employee scan request failed")
        return jsonify({
            "status": "error",
            "message": "Layanan Rekam Medis HRIS tidak dapat dihubungi.",
        }), 502


@app.route("/absen-qrcode")
def absen_qrcode():
    """Public QR gateway for Agenda Rapat/Kesamaptaan attendance."""
    token = str(request.args.get("token") or "").strip()
    if not token or len(token) > 150:
        return render_template(
            "absen_qrcode.html",
            success=False,
            message="QR Code absensi tidak valid.",
        ), 400

    nip = str(session.get("nip") or "").strip()
    headers = {"X-Calendar-NIP": nip} if nip else {}

    try:
        response = _hris_rekam_medis_request(
            "/api/internal/calendar/agenda/rapat/attendance-info",
            params={"token": token},
            headers=headers,
        )
        payload = response.json()
    except (requests.RequestException, ValueError):
        app.logger.exception("Agenda QR info request failed")
        return render_template(
            "absen_qrcode.html",
            success=False,
            message="Layanan absensi HRIS tidak dapat dihubungi.",
        ), 502

    if response.status_code != 200 or payload.get("status") != "success":
        return render_template(
            "absen_qrcode.html",
            success=False,
            message=payload.get("message", "QR absensi tidak dapat diproses."),
        ), response.status_code

    info = payload.get("data") or {}
    mode = str(request.args.get("mode") or "").strip().lower()

    if mode == "pegawai":
        if not session.get("logged_in"):
            return redirect(
                url_for(
                    "login",
                    next=f"/absen-qrcode?token={token}&mode=pegawai",
                )
            )

        try:
            response = _hris_rekam_medis_request(
                "/api/internal/calendar/agenda/rapat/attendance/employee",
                method="POST",
                headers={"X-Calendar-NIP": str(session.get("nip") or "")},
                json={"token": token},
            )
            result = response.json()
        except (requests.RequestException, ValueError):
            app.logger.exception("Agenda employee QR request failed")
            return render_template(
                "absen_qrcode.html",
                success=False,
                message="Gagal mencatat kehadiran pegawai.",
                info=info,
                token=token,
                mode=mode,
            ), 502

        return render_template(
            "absen_qrcode.html",
            success=response.status_code == 200 and result.get("status") == "success",
            already=not bool(result.get("created")),
            message=result.get("message", "Scan QR berhasil."),
            info=info,
            token=token,
            mode=mode,
            attendee=result.get("data"),
        ), response.status_code

    if mode == "non-pegawai":
        return render_template(
            "absen_qrcode.html",
            success=False,
            info=info,
            token=token,
            mode=mode,
        )

    return render_template(
        "absen_qrcode.html",
        success=False,
        info=info,
        token=token,
        mode="",
    )


@app.route("/api/absen-qrcode/guest", methods=["POST"])
def api_absen_qrcode_guest():
    payload = request.get_json(silent=True) or {}
    try:
        response = _hris_rekam_medis_request(
            "/api/internal/calendar/agenda/rapat/attendance/guest",
            method="POST",
            json=payload,
        )
        try:
            result = response.json()
        except ValueError:
            result = {
                "status": "error",
                "message": "Respons layanan absensi HRIS tidak valid.",
            }
        return jsonify(result), response.status_code
    except requests.RequestException:
        app.logger.exception("Agenda guest QR request failed")
        return jsonify({
            "status": "error",
            "message": "Layanan absensi HRIS tidak dapat dihubungi.",
        }), 502


@app.route("/absen-qrcode/pegawai")
def absen_qrcode_pegawai():
    token = str(request.args.get("token") or "").strip()
    if not token or len(token) > 150:
        return redirect(url_for("login"))
    if not session.get("logged_in"):
        return redirect(url_for("login", next=f"/absen-qrcode?token={token}&mode=pegawai"))
    return redirect(url_for("absen_qrcode", token=token))


@app.route("/rekam-medisku")
@login_required
def rekam_medisku():
    return render_template(
        "dashboard.html",
        nama=session.get("nama"),
        nip=session.get("nip"),
        active_menu="rekam_medisku"
    )


@app.route("/api/rekam-medisku")
@login_required
def api_rekam_medisku():
    nip = session.get("nip")

    if not nip:
        return jsonify({
            "status": "error",
            "message": "NIP tidak ditemukan."
        }), 401

    try:
        response = requests.get(
            f"{Config.HRIS_INTERNAL_API_URL}/api/internal/calendar/rekam-medis/history",
            headers={
                "X-Calendar-Internal-Key": Config.HRIS_INTERNAL_API_KEY,
                "X-Calendar-NIP": nip,
            },
            timeout=15,
            verify="/etc/ssl/certs/ca-certificates.crt",
        )

        return jsonify(response.json()), response.status_code

    except requests.RequestException:
        app.logger.exception("Rekam Medis HRIS API unavailable")
        return jsonify({
            "status": "error",
            "message": "Layanan Rekam Medis HRIS tidak tersedia."
        }), 502

    except Exception:
        app.logger.exception("Rekam Medis history API error")
        return jsonify({
            "status": "error",
            "message": "Gagal mengambil riwayat Rekam Medis."
        }), 502


@app.route("/profilku")
@login_required
def profilku():
    return render_template(
        "dashboard.html",
        nama=session.get("nama"),
        nip=session.get("nip"),
        active_menu="profilku"
    )


def _hris_profile_headers():
    return {
        "X-Calendar-Internal-Key": Config.HRIS_INTERNAL_API_KEY,
        "X-Calendar-NIP": str(session.get("nip") or ""),
    }


@app.route("/api/profilku")
@login_required
def api_profilku():
    if not session.get("nip"):
        return jsonify({"success": False, "message": "NIP tidak ditemukan."}), 401
    try:
        response = requests.get(
            f"{Config.HRIS_INTERNAL_API_URL}/api/internal/calendar/profile",
            headers=_hris_profile_headers(),
            timeout=15,
            verify="/etc/ssl/certs/ca-certificates.crt",
        )
        return jsonify(response.json()), response.status_code
    except requests.RequestException:
        app.logger.exception("HRIS Profilku unavailable")
        return jsonify({"success": False, "message": "Layanan profil HRIS tidak tersedia."}), 502


@app.route("/api/profilku", methods=["PUT"])
@login_required
def api_profilku_update():
    try:
        response = requests.put(
            f"{Config.HRIS_INTERNAL_API_URL}/api/internal/calendar/profile",
            headers={**_hris_profile_headers(), "Content-Type": "application/json"},
            json=request.get_json(silent=True) or {},
            timeout=15,
            verify="/etc/ssl/certs/ca-certificates.crt",
        )
        return jsonify(response.json()), response.status_code
    except requests.RequestException:
        app.logger.exception("HRIS Profilku update unavailable")
        return jsonify({"success": False, "message": "Gagal menyimpan profil."}), 502


@app.route("/api/profilku/photo")
@login_required
def api_profilku_photo():
    try:
        response = requests.get(
            f"{Config.HRIS_INTERNAL_API_URL}/api/internal/calendar/profile-photo",
            headers=_hris_profile_headers(),
            timeout=15,
            verify="/etc/ssl/certs/ca-certificates.crt",
        )
        if response.status_code != 200:
            return ("", response.status_code)
        return Response(
            response.content,
            status=200,
            content_type=response.headers.get("Content-Type", "image/jpeg"),
            headers={"Cache-Control": "no-store"},
        )
    except requests.RequestException:
        return ("", 502)


@app.route("/api/profilku/photo", methods=["POST"])
@login_required
def api_profilku_photo_upload():
    file = request.files.get("photo")
    if not file:
        return jsonify({"success": False, "message": "Foto wajib dipilih."}), 400
    try:
        response = requests.post(
            f"{Config.HRIS_INTERNAL_API_URL}/api/internal/calendar/profile-photo",
            headers=_hris_profile_headers(),
            files={"photo": (file.filename, file.stream, file.mimetype)},
            timeout=30,
            verify="/etc/ssl/certs/ca-certificates.crt",
        )
        return jsonify(response.json()), response.status_code
    except requests.RequestException:
        app.logger.exception("HRIS Profilku photo upload unavailable")
        return jsonify({"success": False, "message": "Gagal menyimpan foto profil."}), 502


@app.route("/api/profilku/password", methods=["POST"])
@login_required
def api_profilku_password():
    payload = request.get_json(silent=True) or {}
    payload["username"] = session.get("sso_username") or session.get("username") or ""
    try:
        response = requests.post(
            f"{Config.HRIS_INTERNAL_API_URL}/api/internal/calendar/profile-password",
            headers={**_hris_profile_headers(), "Content-Type": "application/json"},
            json=payload,
            timeout=20,
            verify="/etc/ssl/certs/ca-certificates.crt",
        )
        return jsonify(response.json()), response.status_code
    except requests.RequestException:
        app.logger.exception("HRIS Profilku password unavailable")
        return jsonify({"success": False, "message": "Gagal mengubah password."}), 502


@app.route("/api/profilku/signature")
@login_required
def api_profilku_signature_file():
    try:
        response = requests.get(
            f"{Config.HRIS_INTERNAL_API_URL}/api/internal/calendar/profile-signature",
            headers=_hris_profile_headers(),
            timeout=15,
            verify="/etc/ssl/certs/ca-certificates.crt",
        )
        if response.status_code != 200:
            return ("", response.status_code)
        return Response(
            response.content,
            status=200,
            content_type="image/png",
            headers={"Cache-Control": "no-store"},
        )
    except requests.RequestException:
        return ("", 502)


@app.route("/api/profilku/signature", methods=["POST"])
@login_required
def api_profilku_signature():
    try:
        response = requests.post(
            f"{Config.HRIS_INTERNAL_API_URL}/api/internal/calendar/profile-signature",
            headers={**_hris_profile_headers(), "Content-Type": "application/json"},
            json=request.get_json(silent=True) or {},
            timeout=20,
            verify="/etc/ssl/certs/ca-certificates.crt",
        )
        return jsonify(response.json()), response.status_code
    except requests.RequestException:
        app.logger.exception("HRIS Profilku signature unavailable")
        return jsonify({"success": False, "message": "Gagal menyimpan tanda tangan."}), 502


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

    today = datetime_now = __import__("datetime").datetime.now(
        ZoneInfo("Asia/Jakarta")
    ).date()

    year = today.year
    year_start = date(year, 1, 1)

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
    year_end = date(year, 12, 31)
    days_remaining = max((year_end - today).days, 0)

    return jsonify({
        "status": "success",
        "year": year,
        "today": today.isoformat(),
        "days_passed": days_passed,
        "days_remaining": days_remaining,
        "nip": nip,
        "nama": session.get("nama"),
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


def hris_internal_headers():
    nip = str(session.get("nip") or "").strip()
    return {
        "X-Calendar-Internal-Key": Config.HRIS_INTERNAL_API_KEY,
        "X-Calendar-NIP": nip,
    }


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

    return Response(
        response.content,
        status=200,
        mimetype="text/calendar"
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


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=80)
