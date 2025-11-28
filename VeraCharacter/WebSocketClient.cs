using UnityEngine;
using System;
using System.Net.WebSockets;
using System.Threading;
using System.Threading.Tasks;
using System.Collections.Concurrent;

public class WebSocketClient : MonoBehaviour
{
    private ClientWebSocket ws;
    private CancellationTokenSource cts;

    // Une file d'attente sécurisée pour passer les messages du thread WebSocket au thread principal de Unity
    public static readonly ConcurrentQueue<string> ReceivedMessages = new ConcurrentQueue<string>();

    private async void OnEnable()
    {
        ws = new ClientWebSocket();
        cts = new CancellationTokenSource();
        Uri uri = new Uri("ws://localhost:8765");

        try
        {
            Debug.Log("Connexion au serveur WebSocket...");
            await ws.ConnectAsync(uri, cts.Token);
            Debug.Log("Connecté au serveur WebSocket !");

            // Lancer l'écoute des messages en arrière-plan
            _ = Task.Run(ListenForMessages);
        }
        catch (Exception e)
        {
            Debug.LogError($"Erreur de connexion WebSocket: {e.Message}");
        }
    }

    private async Task ListenForMessages()
    {
        var buffer = new byte[1024 * 4];
        while (ws.State == WebSocketState.Open)
        {
            try
            {
                var result = await ws.ReceiveAsync(new ArraySegment<byte>(buffer), cts.Token);
                if (result.MessageType == WebSocketMessageType.Text)
                {
                    string message = System.Text.Encoding.UTF8.GetString(buffer, 0, result.Count);
                    Debug.Log($"--- RAW MESSAGE REÇU SUR LE THREAD WEBSOCKET: {message} ---"); // Ligne de débogage ajoutée
                    ReceivedMessages.Enqueue(message);
                }
                else if (result.MessageType == WebSocketMessageType.Close)
                {
                    await ws.CloseAsync(WebSocketCloseStatus.NormalClosure, string.Empty, cts.Token);
                }
            }
            catch (Exception e)
            {
                Debug.LogError($"Erreur de réception WebSocket: {e.Message}");
                break;
            }
        }
        Debug.Log("La boucle d'écoute des messages est terminée.");
    }

    private async void OnDisable()
    {
        if (ws != null && ws.State == WebSocketState.Open)
        {
            cts.Cancel();
            await ws.CloseAsync(WebSocketCloseStatus.NormalClosure, "Client se déconnecte", CancellationToken.None);
            Debug.Log("Déconnecté du serveur WebSocket.");
        }
        ws?.Dispose();
        cts?.Dispose();
    }
}
