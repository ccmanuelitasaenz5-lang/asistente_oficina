import os
import logging
from pathlib import Path
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials

# Configuración básica de logs


# Mismos scopes que en calendar_sync.py
SCOPES = ['https://www.googleapis.com/auth/calendar.events']

# Rutas
BASE_DIR = Path(__file__).parent.parent
CREDENTIALS_FILE = BASE_DIR / "credentials.json"
TOKEN_FILE = BASE_DIR / "token.json"

def main():
    creds = None
    
    if TOKEN_FILE.exists():
        logging.info("Se encontró un token.json existente. Verificando validez...")
        creds = Credentials.from_authorized_user_file(str(TOKEN_FILE), SCOPES)
        
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            logging.info("El token ha expirado. Refrescando...")
            try:
                creds.refresh(Request())
            except Exception as e:
                logging.error(f"Error al refrescar el token: {e}")
                creds = None
                
        if not creds:
            if not CREDENTIALS_FILE.exists():
                logging.error(f"¡FALTA EL ARCHIVO credentials.json! Asegúrate de descargarlo de Google Cloud y colocarlo en: {CREDENTIALS_FILE}")
                return
                
            logging.info("Iniciando flujo de autorización en el navegador...")
            try:
                flow = InstalledAppFlow.from_client_secrets_file(str(CREDENTIALS_FILE), SCOPES)
                # IMPORTANTE: Forzamos el host a 127.0.0.1 para evitar problemas de resolución 
                # de IPv6/IPv4 en Windows ('localhost' vs '127.0.0.1')
                creds = flow.run_local_server(
                    host='127.0.0.1', 
                    port=8088, 
                    success_message="¡Autorizacion completada! Puedes cerrar esta ventana y volver a la consola."
                )
            except Exception as e:
                logging.error(f"Error durante el flujo de autenticación: {e}")
                return
                
        with open(TOKEN_FILE, 'w') as token:
            token.write(creds.to_json())
        logging.info("¡Autorización exitosa! Se ha creado el archivo token.json.")
    else:
        logging.info("Las credenciales actuales en token.json son válidas. No es necesario volver a autorizar.")

if __name__ == '__main__':
    main()
