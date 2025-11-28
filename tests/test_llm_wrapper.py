from llm_wrapper import _is_echo
from episodic_memory import memory_manager


def test_is_echo_simple():
    orig = list(memory_manager.memories)
    try:
        memory_manager.memories = []
        memory_manager.ajouter_evenement("Bonjour, je suis Vera.", tags=["vera_response"], importance=1.0)
        is_echo, matched = _is_echo("Bonjour, je suis Vera.")
        assert is_echo
        assert "Vera" in matched
    finally:
        memory_manager.memories = orig
