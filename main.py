import os
import requests
from flask import Flask, request, jsonify

app = Flask(__name__)

ESPO_URL = os.environ.get('ESPO_URL')
ESPO_API_KEY = os.environ.get('ESPO_API_KEY')

HEADERS_ESPO = {
    'X-Api-Key': ESPO_API_KEY,
    'Content-Type': 'application/json',
    'Accept': 'application/json'
}

@app.route('/webhook', methods=['POST'])
def webhook_whatsapp():
    data = request.json
    
    sender_raw = data.get('data', {}).get('key', {}).get('remoteJid', '')
    sender_number = sender_raw.split('@')[0]
    
    if not sender_number:
        return "Ignorado", 200

    # 1. Búsqueda con tu campo exacto: cWhatsappid
    search_params = {
        'where[0][type]': 'equals',
        'where[0][attribute]': 'cWhatsappid', 
        'where[0][value]': sender_number
    }
    
    try:
        res = requests.get(f"{ESPO_URL}/api/v1/Account", headers=HEADERS_ESPO, params=search_params)
        
        print(f"ESTADO BÚSQUEDA ESPOCRM: {res.status_code}")
        
        if res.status_code != 200:
            print(f"RESPUESTA ERROR: {res.text}")
            return "Error en búsqueda", 400

        search_results = res.json()
        
        if search_results['total'] > 0:
            account_id = search_results['list'][0]['id']
            print(f"Mensaje de cliente existente: {account_id}")
        else:
            # 2. Creación con tus campos exactos: cWhatsappid y cLabelnuevo
            new_account = {
                "name": f"Nuevo Contacto ({sender_number})",
                "cWhatsappid": sender_number,
                "cLabelnuevo": ["Nuevo"] # Asegúrate de que "Nuevo" sea una de las opciones válidas en tu lista de EspoCRM
            }
            res_post = requests.post(f"{ESPO_URL}/api/v1/Account", json=new_account, headers=HEADERS_ESPO)
            print(f"ESTADO CREACIÓN ESPOCRM: {res_post.status_code}")
            print(f"Creada nueva cuenta para: {sender_number}")

    except Exception as e:
        print(f"Error procesando integración: {e}")

    return "OK", 200

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 5000)))