import asyncio
import websockets
import json
import threading
import time
from tools.logger import VeraLogger

# Logger pour ce module
logger = VeraLogger("websocket_server")

# --- Variables Globales ---
CONNECTED_CLIENTS = set()
SERVER_LOOP = None

async def _handler(websocket):
    """Gère les connexions entrantes et les maintient en vie."""
    logger.info(f"Client Unity connecté depuis {websocket.remote_address}")
    CONNECTED_CLIENTS.add(websocket)
    try:
        await websocket.wait_closed()
    finally:
        logger.info(f"Client Unity déconnecté.")
        CONNECTED_CLIENTS.remove(websocket)

def run_server_in_thread(host='localhost', port=8765):
    """Lance le serveur WebSocket dans un thread séparé avec un pattern asyncio.run()."""
    
    def thread_target():
        async def main():
            global SERVER_LOOP
            # La boucle est gérée par asyncio.run(), on la récupère simplement.
            SERVER_LOOP = asyncio.get_running_loop()
            logger.info(f"Serveur WebSocket démarrant sur ws://{host}:{port}")
            async with websockets.serve(lambda ws: _handler(ws), host, port):
                await asyncio.Future()  # Tourne à l'infini

        try:
            asyncio.run(main())
        except Exception as e:
            logger.error(f"Erreur critique dans le thread du serveur WebSocket: {e}", exc_info=True)

    server_thread = threading.Thread(target=thread_target, daemon=True)
    server_thread.name = "WebSocketServerThread"
    server_thread.start()
    logger.info("Thread du serveur WebSocket lancé.")
    return server_thread

async def _send_to_all(message):
    """Envoie un message à tous les clients connectés."""
    if CONNECTED_CLIENTS:
        clients = list(CONNECTED_CLIENTS)
        tasks = [client.send(message) for client in clients]
        await asyncio.gather(*tasks)

def send_command_to_avatar(command: dict):
    """Fonction principale à appeler depuis l'extérieur pour envoyer une commande à l'avatar."""
    if SERVER_LOOP and SERVER_LOOP.is_running():
        try:
            message = json.dumps(command)
            # Planifier l'exécution de la coroutine dans la boucle du serveur de manière thread-safe
            asyncio.run_coroutine_threadsafe(_send_to_all(message), SERVER_LOOP)
        except Exception as e:
            logger.error(f"Erreur lors de l'envoi de la commande WebSocket: {e}")
    else:
        logger.warning("Le serveur WebSocket n'est pas prêt, impossible d'envoyer la commande.")

# --- Exemple d'utilisation ---
if __name__ == '__main__':
    run_server_in_thread()
    print("Serveur démarré. Envoi d'une commande de test dans 5 secondes...")
    time.sleep(5)
    test_command = {"type": "animation", "name": "wave"}
    print(f"Envoi de la commande: {test_command}")
    send_command_to_avatar(test_command)
    # Garder le script principal en vie pour que le serveur continue de tourner
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("Arrêt du serveur de test.")
