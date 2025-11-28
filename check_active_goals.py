from db_manager import db_manager
from db_config import TABLE_NAMES
import json

goals_table = TABLE_NAMES["goals"]
all_goals = db_manager.get_all_documents(goals_table, column_name="goal_json")

active_learning_goals = []
for goal in all_goals:
    if goal.get("status") == "active" and goal.get("description", "").startswith("Apprendre sur"):
        active_learning_goals.append(goal)

print(json.dumps(active_learning_goals, indent=2))
