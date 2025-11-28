from episodic_memory import memory_manager

recent_memories = memory_manager.get_recent(limit=50)

for m in reversed(recent_memories):
    print(f'[{m["timestamp"]}] {m["tags"]}: {m["description"]}')
