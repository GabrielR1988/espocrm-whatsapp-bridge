import os
import requests
from flask import Flask, request, jsonify
from datetime import datetime, timedelta


app = Flask(__name__)

# --- CONFIGURACIÓN ---
ESPO_URL = os.environ.get('ESPO_URL')
ESPO_API_KEY = os.environ.get('ESPO_API_KEY')
KEYWORD_OPPORTUNITY = "crear oportunidad" 

HEADERS = {
    'X-Api-Key': ESPO_API_KEY,
    'Content-Type': 'application/json',
    'Accept': 'application/json'
}

# --- FUNCIONES DE AYUDA (HELPERS) ---

def get_account_by_phone(phone):
    """ Busca si ya existe un Account comparando el campo personalizado cWhatsappid """
    url = f"{ESPO_URL}/api/v1/Account"
    
    # Buscamos específicamente en tu campo personalizado
    params = {
        'where[0][type]': 'equals',
        'where[0][attribute]': 'cWhatsappid',
        'where[0][value]': phone
    }
    
    print(f"Buscando Account con cWhatsappid = {phone}...")
    response = requests.get(url, headers=HEADERS, params=params)
    
    if response.status_code == 200:
        data = response.json()
        if data.get('list') and len(data['list']) > 0:
            print(f"✅ Account encontrado: {data['list'][0]['name']} (ID: {data['list'][0]['id']})")
            return data['list'][0]
        else:
            print("❌ No se encontró ningún Account con ese WhatsApp ID.")
    else:
        print(f"Error API Espo: {response.status_code} - {response.text}")
    return None

def create_account(phone, name):
    """ Crea un nuevo Account usando el campo personalizado cWhatsappid """
    url = f"{ESPO_URL}/api/v1/Account"
    payload = {
        "name": name,
        "cWhatsappid": phone, # Usamos tu campo personalizado aquí también
        "description": "Contacto creado automáticamente desde Evolution API"
    }
    print(f"Intentando crear Account para {name}...")
    response = requests.post(url, headers=HEADERS, json=payload)
    if response.status_code in [200, 201]:
        print(f"✨ Account '{name}' creado con éxito.")
        return response.json()
    else:
        print(f"Error al crear Account: {response.text}")
    return None

def create_opportunity(account_id, phone):
    """ Crea una oportunidad vinculada al ID del Account con fecha de cierre automática """
    url = f"{ESPO_URL}/api/v1/Opportunity"
    
    # Generamos una fecha de cierre para dentro de 30 días (formato YYYY-MM-DD)
    fecha_cierre = (datetime.now() + timedelta(days=30)).strftime('%Y-%m-%d')
    
    payload = {
        "name": f"Oportunidad WA - {phone}",
        "stage": "Prospecting",  # <-- Asegúrate que 'Prospecting' sea el VALOR correcto en tu CRM
        "accountId": account_id,
        "closeDate": fecha_cierre, # <--- AQUÍ ESTÁ EL CAMPO QUE FALTABA
        "amount": 0
    }
    
    print(f"Enviando datos a EspoCRM con fecha de cierre: {fecha_cierre}")
    response = requests.post(url, headers=HEADERS, json=payload)
    
    if response.status_code in [200, 201]:
        return True
    else:
        print(f"Error de EspoCRM ({response.status_code}): {response.text}")
        return False

# --- ENDPOINT PRINCIPAL ---

@app.route('/webhook', methods=['POST'])
def webhook():
    data = request.json
    
    if data.get('event') == 'messages.upsert':
        event_data = data.get('data', {})
        if isinstance(event_data, list):
            event_data = event_data[0] if len(event_data) > 0 else {}

        key = event_data.get('key', {})
        from_me = key.get('fromMe', False)
        remote_jid = key.get('remoteJid', '')
        push_name = event_data.get('pushName', 'Cliente WhatsApp')
        
        message_content = event_data.get('message', {})
        text = (message_content.get('conversation') or 
                message_content.get('extendedTextMessage', {}).get('text') or "")
        
        phone = remote_jid.split('@')[0] if remote_jid else ""

        if not phone:
            return jsonify({"status": "no_phone"}), 200

        # ---------------------------------------------------------
        # ESCENARIO 1: Mensaje del CLIENTE -> Registro Automático
        # ---------------------------------------------------------
        if not from_me:
            account = get_account_by_phone(phone)
            if not account:
                create_account(phone, push_name)
            
        # ---------------------------------------------------------
        # ESCENARIO 2: Mensaje del AGENTE -> Palabra Clave
        # ---------------------------------------------------------
        elif from_me and KEYWORD_OPPORTUNITY.lower() in text.lower():
            print(f"🚀 Palabra clave detectada hacia {phone}.")
            account = get_account_by_phone(phone)
            
            if account:
                if create_opportunity(account['id'], phone):
                    print("💰 Oportunidad cargada en el Pipeline.")
                else:
                    print("❌ Error al crear oportunidad.")
            else:
                print("⚠️ No existe el Account. El cliente debe escribir primero.")

    return jsonify({"status": "success"}), 200

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)