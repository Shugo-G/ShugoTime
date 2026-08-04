"""
Script de prueba para envío de mensajes WhatsApp via Wasapi.
Uso: python test_wasapi.py <numero_destino>
     python test_wasapi.py 5492901234567
"""

import sys
import os
import requests
from dotenv import load_dotenv

# Cargar .env desde la raiz del proyecto
load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

WASAPI_API_KEY = os.environ.get("WASAPI_API_KEY", "")
WASAPI_FROM_ID = os.environ.get("WASAPI_FROM_ID", "")
BASE_URL = "https://api-ws.wasapi.io/api/v1"

HEADERS = {
    "Authorization": f"Bearer {WASAPI_API_KEY}",
    "Accept": "application/json",
    "Content-Type": "application/json",
}


def verificar_config():
    print("=== Configuración ===")
    print(f"API Key : {'*' * (len(WASAPI_API_KEY) - 6) + WASAPI_API_KEY[-6:] if WASAPI_API_KEY else 'NO CONFIGURADA'}")
    print(f"From ID : {WASAPI_FROM_ID or 'NO CONFIGURADO (se auto-descubrirá)'}")
    if not WASAPI_API_KEY:
        print("\nERROR: WASAPI_API_KEY no está en el .env")
        sys.exit(1)


def obtener_from_id():
    if WASAPI_FROM_ID:
        return int(WASAPI_FROM_ID)
    print("\nAuto-descubriendo from_id desde /whatsapp-numbers...")
    resp = requests.get(f"{BASE_URL}/whatsapp-numbers", headers=HEADERS, timeout=10)
    print(f"  HTTP {resp.status_code}")
    data = resp.json()
    print(f"  Respuesta: {data}")
    numeros = data.get("results") or (data if isinstance(data, list) else [])
    if not numeros:
        print("ERROR: No se encontraron líneas de WhatsApp en la cuenta.")
        sys.exit(1)
    from_id = int(numeros[0]["id"])
    print(f"  Usando from_id: {from_id} ({numeros[0].get('phone', '')})")
    return from_id


def verificar_cuenta():
    print("\n=== Verificando cuenta Wasapi ===")
    resp = requests.get(f"{BASE_URL}/user", headers=HEADERS, timeout=10)
    print(f"HTTP {resp.status_code}")
    print(resp.json())


def enviar_mensaje(wa_id, from_id):
    mensaje = (
        "✅ *Mensaje de prueba — ShugoTime*\n\n"
        "Si recibís este mensaje, la integración con Wasapi está funcionando correctamente."
    )
    print(f"\n=== Enviando mensaje de prueba ===")
    print(f"Destino  : {wa_id}")
    print(f"From ID  : {from_id}")
    print(f"Mensaje  :\n{mensaje}\n")

    resp = requests.post(
        f"{BASE_URL}/whatsapp-messages",
        json={"message": mensaje, "wa_id": wa_id, "from_id": from_id},
        headers=HEADERS,
        timeout=10,
    )
    print(f"HTTP {resp.status_code}")
    try:
        print(resp.json())
    except Exception:
        print(resp.text)

    if resp.ok:
        print("\n✅ Mensaje enviado correctamente.")
    else:
        print("\n❌ Error al enviar el mensaje.")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Uso: python test_wasapi.py <numero_destino>")
        print("     Ejemplo: python test_wasapi.py 5492901234567")
        print("     (código de país + número sin espacios ni +)")
        sys.exit(1)

    wa_id = sys.argv[1]

    verificar_config()
    verificar_cuenta()
    from_id = obtener_from_id()
    enviar_mensaje(wa_id, from_id)
