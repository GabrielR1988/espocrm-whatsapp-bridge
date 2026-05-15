import os
import requests
from flask import Flask, request, jsonify

app = Flask(__name__)

# --- CONFIGURACIÓN ---
ESPO_URL = os.environ.get('ESPO_URL')
ESPO_API_KEY = os.environ.get('ESPO_API_KEY')
# Define aquí tu palabra o frase mágica
KEYWORD_OPPORTUNITY = "crear prospecto" 

HEADERS = {
    'X-Api-Key': ESPO_API_KEY,
    'Content-Type': 'application/json',
    'Accept': 'application/json'
}

# --- FUNCIONES DE AYUDA (HELPERS) ---

def get_account_by_phone(phone):
    """ Busca si ya existe un Account con ese teléfono """
    url = f"{ESPO_URL}/api/v1/Account"
    params = {
        'where[0][type]': 'contains',
        'where[0][attribute]': 'phoneNumber',
        'where[0][value]': phone
    }
    response = requests.get(url, headers=HEADERS, params=params)
    if response.status_code == 200:
        data = response.json()
        if data.get('list') and len(data['list']) > 0:
            return data['list'][0]
    return None

def create_account(phone, name):
    """ Crea un nuevo Account en EspoCRM """
    url = f"{ESPO_URL}/api/v1/Account"
    payload = {
        "name": name,
        "phoneNumber": phone,
        "description": "Creado automáticamente desde WhatsApp"
    }
    response = requests.post(url, headers=HEADERS, json=payload)
    if response.status_code in [200, 201]:
        return response.json()
    return None

def create_opportunity(account_id, phone):
    """ Crea una oportunidad vinculada al Account """
    url = f"{ESPO_URL}/api/v1/Opportunity"
    payload = {
        "name": f"Oportunidad WA - {phone}",
        "stage": "Prospecting",  # <-- ASEGURATE QUE ESTA ETAPA EXISTA EN TU CRM
        "accountId": account_id,
        "amount": 0
    }
    response = requests.post(url, headers=HEADERS, json=payload)
    return response.status_code in [200, 201]

# --- ENDPOINT PRINCIPAL (WEBHOOK) ---

@app.route('/webhook', methods=['POST'])
def webhook():
    data = request.json
    
    # Validamos que sea un evento de mensaje nuevo
    if data.get('event') == 'messages.upsert':
        msg_payload = data.get('data', {}).get('message', {})
        
        # Evolution a veces manda una lista, manejamos ambos casos
        if isinstance(msg_payload, list):
            msg_payload = msg_payload[0] if len(msg_payload) > 0 else {}

        key = msg_payload.get('key', {})
        from_me = key.get('fromMe', False)
        remote_jid = key.get('remoteJid', '')
        push_name = data.get('data', {}).get('pushName', 'Cliente WhatsApp')
        
        # Extraer el texto del mensaje
        message_content = msg_payload.get('message', {})
        text = (message_content.get('conversation') or 
                message_content.get('extendedTextMessage', {}).get('text') or "")
        
        # Limpiar el número de teléfono
        phone = remote_jid.split('@')[0]

        # ---------------------------------------------------------
        # LÓGICA 1: MENSAJE DEL CLIENTE (Carga de Account)
        # ---------------------------------------------------------
        if not from_me:
            print(f"📥 Mensaje de cliente ({phone}). Verificando Account...")
            existing_account = get_account_by_phone(phone)
            
            if not existing_account:
                print(f"✨ Creando nuevo Account para: {push_name}")
                create_account(phone, push_name)
            else:
                print(f"✅ El Account ya existe: {existing_account['name']}")

        # ---------------------------------------------------------
        # LÓGICA 2: MENSAJE DEL AGENTE (Carga de Opportunity)
        # ---------------------------------------------------------
        elif from_me and KEYWORD_OPPORTUNITY.lower() in text.lower():
            print(f"🚀 Palabra clave detectada hacia {phone}. Generando oportunidad...")
            account = get_account_by_phone(phone)
            
            if account:
                success = create_opportunity(account['id'], phone)
                if success:
                    print("💰 Oportunidad creada con éxito en el Pipeline.")
                else:
                    print("❌ Error al crear la oportunidad en EspoCRM.")
            else:
                print("⚠️ No se encontró el Account. Primero el cliente debe escribir para ser registrado.")

    return jsonify({"status": "success"}), 200

if __name__ == '__main__':
    # Usamos el puerto que Railway nos asigne
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)