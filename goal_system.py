"""
Système unifié de gestion des objectifs
"""
from datetime import datetime
from typing import List, Dict, Optional
# Removed JSONManager
from attention_manager import attention_manager # Import the global attention manager
from tools.logger import VeraLogger # Import VeraLogger
from db_manager import db_manager # NEW: Import DbManager
from db_config import TABLE_NAMES # NEW: Import TABLE_NAMES

class GoalSystem:
    def __init__(self):
        self.table_name = TABLE_NAMES["goals"]
        db_manager._create_tables_if_not_exist() # Ensure table is created
        self.logger = VeraLogger("goal_system") # Initialize logger for this module
        
    def _ensure_default_structure(self):
        """No longer needed to initialize a default JSON structure, table is ensured by DbManager."""
        pass # Table creation handled by DbManager init

    def _update_attention_focus(self):
        """Pushes the current active goals to the attention manager."""
        active_goals = self.get_active_goals()
        attention_manager.update_focus(
            "active_goals",
            active_goals,
            salience=0.85  # Goals are highly salient
        )
            
    def add_goal(self, description: str, priority: int = 1, deadline: Optional[str] = None, originating_event_id: Optional[int] = None) -> Dict:
        """Ajoute un nouvel objectif"""
        goal = {
            "id": datetime.now().strftime("%Y%m%d%H%M%S%f"), # Ensure unique ID
            "description": description,
            "priority": priority,
            "creation_time": datetime.now().isoformat(),
            "deadline": deadline,
            "status": "active"
        }
        if originating_event_id is not None:
            goal["originating_event_id"] = originating_event_id
        
        db_manager.insert_document(self.table_name, goal["id"], goal, column_name="goal_json")
        self._update_attention_focus()  # Proactively update attention
        return goal
        
    def complete_goal(self, goal_id: str, success: bool = True) -> bool:
        """Marque un objectif comme complété"""
        goal = db_manager.get_document(self.table_name, goal_id, column_name="goal_json")
        if goal:
            goal["completion_time"] = datetime.now().isoformat()
            goal["success"] = success
            goal["status"] = "completed"
            
            db_manager.insert_document(self.table_name, goal_id, goal, column_name="goal_json")
            self._update_attention_focus()  # Proactively update attention
            return True
                
        return False
        
    def update_goal_status(self, goal_id: str, status: str) -> Optional[Dict]:
        """Met à jour le statut d'un objectif"""
        valid_statuses = ["active", "completed", "archived"]
        if status not in valid_statuses:
            return None
            
        goal = db_manager.get_document(self.table_name, goal_id, column_name="goal_json")
        if goal:
            goal["status"] = status
            goal["update_time"] = datetime.now().isoformat()
            
            db_manager.insert_document(self.table_name, goal_id, goal, column_name="goal_json")
            self._update_attention_focus()  # Proactively update attention
            return goal
                    
        return None
        
    def get_goal_by_description_and_status(self, description: str, status: str) -> List[Dict]:
        """Récupère tous les objectifs correspondant à une description et un statut donnés."""
        all_goals = db_manager.get_all_documents(self.table_name, column_name="goal_json")
        matching_goals = [
            goal for goal in all_goals 
            if goal.get("description", "").lower() == description.lower() and goal.get("status") == status
        ]
        return matching_goals
        
    def get_goal_by_id(self, goal_id: str) -> Optional[Dict]:
        """Récupère un objectif par son ID."""
        return db_manager.get_document(self.table_name, goal_id, column_name="goal_json")
        
        
    def get_active_goals(self) -> List[Dict]:
        """Récupère les objectifs actifs."""
        all_goals = db_manager.get_all_documents(self.table_name, column_name="goal_json")
        return [goal for goal in all_goals if goal.get("status") == "active"]
        
    def get_completed_goals(self) -> List[Dict]:
        """Récupère les objectifs complétés."""
        all_goals = db_manager.get_all_documents(self.table_name, column_name="goal_json")
        return [goal for goal in all_goals if goal.get("status") == "completed"]
        
    def get_all_goals(self) -> Dict[str, List[Dict]]:
        """Récupère tous les objectifs et les retourne regroupés par statut pour compatibilité."""
        all_goals = db_manager.get_all_documents(self.table_name, column_name="goal_json")
        
        grouped_goals = {
            "active": [],
            "completed": [],
            "archived": []
        }
        for goal in all_goals:
            status = goal.get("status", "unknown")
            if status in grouped_goals:
                grouped_goals[status].append(goal)
            else:
                self.logger.warning(f"Goal with unknown status '{status}' found: {goal.get('id')}")
        return grouped_goals

# Instance globale
goal_system = GoalSystem()

# Fonctions de compatibilité pour l'ancien code
def get_active_goals():
    return goal_system.get_active_goals()

def get_all_goals():
    # This will return the grouped dictionary now
    return goal_system.get_all_goals()

def update_goal_status(goal_id, status):
    return goal_system.update_goal_status(goal_id, status)