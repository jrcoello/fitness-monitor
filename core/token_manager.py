import os

import requests
from dotenv import load_dotenv

load_dotenv()

BUQ_TOKEN_URL = "https://buq.partners/oauth/token"

# La cuenta jrcoello@gmail.com está dada de alta en Casa Onze (company_id 146).
# El endpoint de token exige el header gafafit-company aunque no esté documentado
# en la API pública — sin él responde 422 "El email no concuerda con nuestros registros".
BUQ_HOME_COMPANY_ID = "146"
BUQ_HOME_ORIGIN = "https://casaonze.mx"


def get_buq_token() -> str:
    response = requests.post(
        BUQ_TOKEN_URL,
        json={
            "grant_type": "password",
            "client_id": os.environ["BUQ_API_CLIENT"],
            "client_secret": os.environ["BUQ_API_SECRET"],
            "username": os.environ["BUQ_EMAIL"],
            "password": os.environ["BUQ_PASSWORD"],
            "scope": "",
        },
        headers={
            "Accept": "application/json",
            "Origin": BUQ_HOME_ORIGIN,
            "gafafit-company": BUQ_HOME_COMPANY_ID,
        },
        timeout=15,
    )
    response.raise_for_status()
    return response.json()["access_token"]


# El login real de Síclo vive en api.siclo.plus (no api.siclo.com como el resto de
# la API) — se encontró interceptando fetch/XHR en el navegador, no está documentado.
SICLO_TOKEN_URL = "https://api.siclo.plus/auth/user/token"


def get_siclo_token() -> str:
    response = requests.post(
        SICLO_TOKEN_URL,
        json={
            "email": os.environ["SICLO_EMAIL"],
            "password": os.environ["SICLO_PASSWORD"],
        },
        headers={
            "Accept": "application/json",
            "Origin": "https://siclo.com",
        },
        timeout=15,
    )
    response.raise_for_status()
    return response.json()["token"]["access_token"]
