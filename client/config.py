"""Configuracao do cliente: IP do servidor e paths locais."""

# IP/porta do servidor central. Deixe vazio para modo LAN puro.
SERVER_HOST = "127.0.0.1"
SERVER_PORT = 9999

# Timeout (s) para decidir ONLINE vs LAN ao subir o cliente.
CONNECT_TIMEOUT = 3

# Path do banco local cifrado (nunca committar - ver .gitignore).
LOCAL_DB_PATH = "corvo_local.db"
