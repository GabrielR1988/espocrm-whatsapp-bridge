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
            # AGREGAMOS ESTO PARA VER EL ERROR EXACTO:
            if res_post.status_code != 200:
                print(f"ERROR DE CREACIÓN: {res_post.text}")
            else:
                print(f"Creada nueva cuenta para: {sender_number}")

    except Exception as e:
        print(f"Error procesando integración: {e}")

    return "OK", 200

def get_contact_by_phone(phone_number):
    """
    Busca al contacto en EspoCRM a partir de su número de teléfono.
    Retorna el ID del contacto si existe, o None si no se encuentra.
    """
    url = f"{ESPO_URL}/api/v1/Contact"
    params = {
        'where[0][type]': 'contains',
        'where[0][attribute]': 'phoneNumber',
        'where[0][value]': phone_number
    }
    
    response = requests.get(url, headers=HEADERS, params=params)
    if response.status_code == 200:
        data = response.json()
        if data.get('list') and len(data['list']) > 0:
            return data['list'][0]['id']
    return None

def create_opportunity(contact_id, phone_number):
    """
    Crea una nueva Opportunity asociada al ID del contacto.
    """
    url = f"{ESPO_URL}/api/v1/Opportunity"
    payload = {
        "name": f"Oportunidad - WA {phone_number}",
        "stage": "Prospecting", # Cambia esto por la etapa inicial real de tu pipeline
        "contactId": contact_id,
        "amount": 0
    }
    
    response = requests.post(url, headers=HEADERS, json=payload)
    if response.status_code in [200, 201]:
        print("¡Oportunidad creada con éxito en EspoCRM!")
        return True
    else:
        print("Error creando oportunidad:", response.text)
        return False

@app.route('/webhook/evolution', methods=['POST'])
def evolution_webhook():
    data = request.json
    
    # 1. Asegurarnos de que el evento entrante es de un nuevo mensaje (messages.upsert)
    if data.get('event') == 'messages.upsert':
        # Evolution API anida la información dentro de 'data' -> 'message'
        msg_data = data.get('data', {}).get('message', {})
        
        # En Evolution v2 suele venir como un dict, pero por precaución manejamos si es array
        if isinstance(msg_data, list) and len(msg_data) > 0:
            msg_data = msg_data[0]
            
        key = msg_data.get('key', {})
        from_me = key.get('fromMe', False)
        remote_jid = key.get('remoteJid', '')
        
        # Extraer el texto del mensaje (puede venir en diferentes atributos dependiendo del formato)
        content = msg_data.get('message', {})
        text = content.get('conversation') or content.get('extendedTextMessage', {}).get('text') or ''
        
        # 2 y 3. Filtrar: Solo mensajes enviados por el agente que contengan la "palabra clave"
        # Usamos .lower() para que no discrimine mayúsculas y minúsculas
        keyword = "palabra clave" # <-- Define tu palabra/frase mágica aquí
        
        if from_me and keyword.lower() in text.lower():
            # Limpiamos el número de teléfono (quitamos el sufijo @s.whatsapp.net)
            phone_number = remote_jid.split('@')[0]
            print(f"Palabra clave detectada por el agente hacia el número {phone_number}")
            
            # 4. Buscamos el ID de contacto en EspoCRM
            contact_id = get_contact_by_phone(phone_number)
            
            if contact_id:
                # 5. Creamos la Oportunidad asignada a ese contacto
                create_opportunity(contact_id, phone_number)
            else:
                print(f"No se encontró un contacto registrado con el teléfono {phone_number}.")
                # (Opcional): Si quieres que aquí además se cree el contacto, podrías llamar a 
                # la misma función que ya usas actualmente para crear contactos nuevos.

    return jsonify({"status": "success"}), 200

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 5000)))