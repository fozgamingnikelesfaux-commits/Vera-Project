from typing import Dict, Any, Optional

# This function will be defined later in llm_wrapper, so we can't import it directly here at module level.
# We will define a wrapper here and assume llm_wrapper will be fully initialized when this is called.

def send_inference_prompt_for_personality(prompt_text: str, max_tokens: int = 256, custom_system_prompt: Optional[str] = None) -> Dict[str, Any]:
    """
    Wrapper function to send inference prompts to the LLM, specifically for personality system.
    This helps break circular import dependencies by centralizing the call.
    """
    # Import llm_wrapper here locally to avoid circular dependency at module level
    from llm_wrapper import send_inference_prompt 
    return send_inference_prompt(prompt_text, max_tokens, custom_system_prompt)