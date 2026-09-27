import os
from dotenv import load_dotenv

load_dotenv("/opt/calendar/.env")


class Config:
    SECRET_KEY = os.getenv("CALENDAR_SECRET_KEY")
    BDIP_SSO_URL = os.getenv(
        "BDIP_SSO_URL",
        "https://bdip.sarsurabaya.id"
    )
    HRIS_INTERNAL_API_URL = os.getenv(
        "HRIS_INTERNAL_API_URL"
    )
    HRIS_INTERNAL_API_KEY = os.getenv(
        "HRIS_INTERNAL_API_KEY"
    )

    SESSION_PERMANENT_LIFETIME = 7
