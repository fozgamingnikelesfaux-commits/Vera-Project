using UnityEngine;
using System.Collections; // Needed for Coroutines
using System.Collections.Concurrent;

// Updated command structure
[System.Serializable]
public class AvatarCommand
{
    public string type;
    public string name;
    public float value; // Changed from intensity to value
}

public class AvatarController : MonoBehaviour
{
    private Animator animator;

    // Public reference to the SkinnedMeshRenderer that has the blend shapes.
    // This must be assigned in the Unity Inspector.
    public SkinnedMeshRenderer bodyMeshRenderer;

    // Store blend shape indices for performance
    private int eyeBlinkL_Index = -1;
    private int eyeBlinkR_Index = -1;

    void Start()
    {
        animator = GetComponent<Animator>();
        if (animator == null)
        {
            Debug.LogError("Animator component not found!");
        }

        if (bodyMeshRenderer == null)
        {
            Debug.LogError("bodyMeshRenderer is not assigned in the Inspector! Please assign the SkinnedMeshRenderer of CC_Base_Body.");
        }
        else
        {
            // Get blend shape indices once at the start
            eyeBlinkL_Index = bodyMeshRenderer.sharedMesh.GetBlendShapeIndex("Eye_Blink_L");
            eyeBlinkR_Index = bodyMeshRenderer.sharedMesh.GetBlendShapeIndex("Eye_Blink_R");
        }
    }

    void Update()
    {
        while (WebSocketClient.ReceivedMessages.TryDequeue(out string message))
        {
            ProcessCommand(message);
        }
    }

    void ProcessCommand(string jsonMessage)
    {
        try
        {
            Debug.Log($"Processing JSON command: {jsonMessage}");
            AvatarCommand command = JsonUtility.FromJson<AvatarCommand>(jsonMessage);

            if (command.type == "animation")
            {
                Debug.Log($"Executing animation trigger: {command.name}");
                animator.SetTrigger(command.name);
            }
            else if (command.type == "expression")
            {
                Debug.Log($"Setting blend shape: {command.name} to value: {command.value}");
                SetBlendShapeWeight(command.name, command.value);
            }
            else if (command.type == "blink")
            {
                Debug.Log("Executing blink coroutine.");
                StartCoroutine(BlinkCoroutine());
            }
        }
        catch (System.Exception e)
        {
            Debug.LogError($"Error processing JSON command: {e.Message}");
        }
    }

    // New function to control a blend shape by its name
    void SetBlendShapeWeight(string shapeName, float weight)
    {
        if (bodyMeshRenderer == null) return;

        int shapeIndex = bodyMeshRenderer.sharedMesh.GetBlendShapeIndex(shapeName);

        if (shapeIndex != -1)
        {
            // The weight must be between 0 and 100
            bodyMeshRenderer.SetBlendShapeWeight(shapeIndex, weight);
        }
        else
        {
            Debug.LogWarning($"Blend shape '{shapeName}' not found on the assigned mesh renderer.");
        }
    }

    // Overloaded version for performance using pre-cached index
    void SetBlendShapeWeight(int shapeIndex, float weight)
    {
        if (bodyMeshRenderer != null && shapeIndex != -1)
        {
            bodyMeshRenderer.SetBlendShapeWeight(shapeIndex, weight);
        }
    }

    // Coroutine to handle a smooth blink
    IEnumerator BlinkCoroutine()
    {
        float blinkInDuration = 0.08f;
        float blinkOutDuration = 0.12f;
        float timer = 0f;

        // Blink In (Close eyes)
        while (timer < blinkInDuration)
        {
            timer += Time.deltaTime;
            float weight = Mathf.Lerp(0, 100, timer / blinkInDuration);
            SetBlendShapeWeight(eyeBlinkL_Index, weight);
            SetBlendShapeWeight(eyeBlinkR_Index, weight);
            yield return null; // Wait for the next frame
        }
        
        // Ensure eyes are fully closed
        SetBlendShapeWeight(eyeBlinkL_Index, 100);
        SetBlendShapeWeight(eyeBlinkR_Index, 100);

        // Blink Out (Open eyes)
        timer = 0f;
        while (timer < blinkOutDuration)
        {
            timer += Time.deltaTime;
            float weight = Mathf.Lerp(100, 0, timer / blinkOutDuration);
            SetBlendShapeWeight(eyeBlinkL_Index, weight);
            SetBlendShapeWeight(eyeBlinkR_Index, weight);
            yield return null; // Wait for the next frame
        }

        // Ensure eyes are fully open
        SetBlendShapeWeight(eyeBlinkL_Index, 0);
        SetBlendShapeWeight(eyeBlinkR_Index, 0);
    }
}
