"""
Vision Processor for Vera
"""
import mss
from PIL import Image
import io
import base64
from typing import Optional, Dict, List
import re
import json
from datetime import datetime

from tools.logger import VeraLogger # Re-add VeraLogger import
from json_manager import JSONManager # Import JSONManager for config access
import config as global_config_module # Import config module, alias to avoid name conflict
import system_monitor # Import the entire module
from llm_wrapper import send_inference_prompt # NEW: Import send_inference_prompt

logger = VeraLogger("vision_processor")

# Initialize JSONManager for config access
config_manager = JSONManager("config")

def take_screenshot() -> Optional[bytes]:
    """Takes a screenshot of the primary monitor and returns it as bytes."""
    try:
        with mss.mss() as sct:
            sct_img = sct.grab(sct.monitors[1])
            img = Image.frombytes("RGB", sct_img.size, sct_img.bgra, "raw", "BGRX")
            
            # Convert to bytes
            img_byte_arr = io.BytesIO()
            img.save(img_byte_arr, format='PNG')
            img_byte_arr = img_byte_arr.getvalue()
            return img_byte_arr
    except Exception as e:
        logger.error(f"Failed to take screenshot: {e}", exc_info=True)
        return None

def analyze_screenshot() -> Optional[Dict]:
    """
    Takes a screenshot, gets running processes, and asks the LLM to analyze.
    """
    current_config = config_manager.get() # Get the current config
    if not current_config.get("enable_vision", True):
        logger.debug("Vision processing est désactivé dans la configuration.")
        return None

    logger.info("Analyzing visual context...")
    
    
    # 1. Get running processes
    processes = system_monitor.get_running_processes()
    top_processes = [f"{p['name']} ({p['memory_percent']:.1f}%)" for p in processes[:5]]
    
    # 2. Take screenshot
    screenshot_bytes = take_screenshot()
    if not screenshot_bytes:
        return None
        
    # 3. Construct prompt for LLM
    encoded_image = base64.b64encode(screenshot_bytes).decode('utf-8')
    
    prompt = f"""
    Tu es l'œil de Vera. Analyse l'image ci-jointe.
    Contexte additionnel : les processus les plus actifs sur le système sont {top_processes}.
    En te basant sur l'image ET cette liste, identifie avec certitude le nom du processus de l'application au premier plan.
    Ensuite, décris en une phrase l'activité visible dans cette application.
    Réponds uniquement en format JSON avec les clés 'application_active' et 'resume_activite'.
    """
    
    user_content = [
        {"type": "text", "text": prompt},
        {
            "type": "image_url",
            "image_url": {
                "url": f"data:image/png;base64,{encoded_image}"
            }
        }
    ]
    
    # 4. Send to LLM
    try:
        response = send_inference_prompt(user_content, max_tokens=200) # Assuming send_inference_prompt can handle a list of content
        analysis_text = response.get("text", "{}")

        # 5. Parse the response
        json_match = re.search(r'\{.*\}', analysis_text, re.DOTALL)
        if not json_match:
            logger.error("Vision analysis did not return valid JSON.", received_text=analysis_text)
            return None

        analysis_data = json.loads(json_match.group(0))
        analysis_data['timestamp'] = datetime.now().isoformat()
        
        logger.info(f"Visual analysis complete: {analysis_data}")
        return analysis_data

    except Exception as e:
        logger.error(f"Failed to analyze screenshot with LLM: {e}", exc_info=True)
        return None
