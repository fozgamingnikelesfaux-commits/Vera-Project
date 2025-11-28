import time
from episodic_memory import memory_manager


def test_add_and_dedup(tmp_path):
    # backup
    orig = list(memory_manager.memories)
    try:
        memory_manager.memories = []
        e1 = memory_manager.ajouter_evenement("Test event", tags=["user_input"], importance=1.0)
        assert e1 in memory_manager.memories
        # add duplicate
        e2 = memory_manager.ajouter_evenement("Test event", tags=["user_input"], importance=0.5)
        # should dedup: still only one event and importance is max
        assert len(memory_manager.memories) == 1
        assert memory_manager.memories[0]["importance"] == 1.0

    finally:
        memory_manager.memories = orig


def test_search_keyword():
    orig = list(memory_manager.memories)
    try:
        memory_manager.memories = []
        memory_manager.ajouter_evenement("J'aime les chiens", tags=["user_input"], importance=1.0)
        memory_manager.ajouter_evenement("J'aime les chats", tags=["user_input"], importance=1.0)
        results = memory_manager.search("chien", limit=5)
        assert isinstance(results, list)
        assert any("chien" in r["memory"]["desc"].lower() for r in results)
    finally:
        memory_manager.memories = orig
