import os
import requests
from flask import Flask, request, jsonify

app = Flask(__name__)

# CONFIGURACIÓN (Usa variables de entorno en Railway)
ESPO_URL = os.environ.get('ESPO_URL')       # Tu URL de EspoCRM
ESPO_API_KEY = os.environ.get('ESPO_API_KEY') # La que generamos en el Paso 1

HEADERS_ESPO = {
    'X-Api-Key': os.environ.get('ESPO_API_KEY'),
    'Content-Type': 'application/json',
    'Accept': 'application/json'
}

@app.route('/webhook', methods=['POST'])
def webhook_whatsapp():
    data = request.json
    
    # 1. Extraemos el número y el mensaje (Formato Evolution API)
    # El número suele venir como '56912345678@s.whatsapp.net'
    sender_raw = data.get('data', {}).get('key', {}).get('remoteJid', '')
    sender_number = sender_raw.split('@')[0]
    message_text = data.get('data', {}).get('message', {}).get('conversation', '')

    if not sender_number:
        return "Ignorado", 200

    # 2. Buscamos al cliente en EspoCRM por su whatsapp_id (el Varchar que creaste)
    # Filtramos por el campo exacto
    search_url = f"{ESPO_URL}/api/v1/Account?where[0][type]=equals&where[0][attribute]=whatsapp_id&where[0][value]={sender_number}"
    
    try:
        res = requests.get(search_url, headers=HEADERS_ESPO)
        # AGREGAR ESTAS DOS LÍNEAS:
        print(f"ESTADO ESPOCRM: {res.status_code}")
        print(f"RESPUESTA CRUDA ESPOCRM: {res.text}")
        search_results = res.json()
        
        if search_results['total'] > 0:
            # CLIENTE EXISTE: Actualizamos o registramos mensaje
            account_id = search_results['list'][0]['id']
            print(f"Mensaje de cliente existente: {account_id}")
            # Aquí podrías agregar lógica para cambiar etiqueta a "EN PROCESO"
        else:
            # CLIENTE NO EXISTE: Lo creamos con etiqueta "NUEVO"
            new_account = {
                "name": f"Nuevo Contacto ({sender_number})",
                "whatsapp_id": sender_number,
                "etiquetas": ["NUEVO"] # El Multi-Enum que creaste
            }
            requests.post(f"{ESPO_URL}/api/v1/Account", json=new_account, headers=HEADERS_ESPO)
            print(f"Creada nueva cuenta para: {sender_number}")

    except Exception as e:
        print(f"Error procesando integración: {e}")

    return "OK", 200

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 5000)))