import unittest
from datetime import datetime, timedelta
from pathlib import Path
import sys
import json
import os
from unittest.mock import patch, MagicMock

# Ajouter le dossier parent au path pour les imports
sys.path.append(str(Path(__file__).parent.parent))

from emotion_system import emotional_system
from meta_engine import metacognition
from core import process_user_input, _check_proactive_goals, _process_user_feedback, process_sensory_input
from time_manager import time_manager
from web_searcher import web_searcher
from goal_system import goal_system
from episodic_memory import memory_manager
from learning_system import learning_system
from llm_wrapper import send_inference_prompt

class TestEmotionalCore(unittest.TestCase):
    def setUp(self):
        self.emotion = emotional_system
        # Temporarily set emotional_inertia to 0.0 for direct testing of updates
        self.original_inertia = self.emotion.manager.load()["personality"]["emotional_inertia"]
        state = self.emotion.manager.load()
        state["personality"]["emotional_inertia"] = 0.0
        self.emotion.manager.save(state)
        
    def tearDown(self):
        # Restore original emotional_inertia
        state = self.emotion.manager.load()
        state["personality"]["emotional_inertia"] = self.original_inertia
        self.emotion.manager.save(state)
        
    def test_emotion_update(self):
        triggers = [{"valence": 0.7, "intensity": 0.6, "control": 0.3}]
        self.emotion.update_emotion(triggers)
        result = self.emotion.get_emotional_state()
        self.assertIsInstance(result, dict)
        self.assertIn("pleasure", result)
        self.assertIn("arousal", result)
        self.assertIn("dominance", result)
        self.assertIn("label", result)
        self.assertEqual(result["label"], "joie")

    def test_emotion_classification(self):
        # Set a specific emotional state for testing
        self.emotion.update_emotion([{"valence": 0.8, "intensity": 0.7, "control": 0.5}])
        state = self.emotion.get_emotional_state()
        self.assertIn("label", state)
        self.assertEqual(state["label"], "joie") # Based on _map_pad_to_label rules

        self.emotion.update_emotion([{"valence": -0.8, "intensity": 0.7, "control": 0.5}])
        state = self.emotion.get_emotional_state()
        self.assertIn("label", state)
        self.assertEqual(state["label"], "colère") # Based on _map_pad_to_label rules        
class TestMetaCognition(unittest.TestCase):
    def setUp(self):
        self.meta = metacognition
        
    def test_confidence_evaluation(self):
        context = {"required_capabilities": ["conversation"]}
        confidence = self.meta._evaluate_confidence(context)
        self.assertIsInstance(confidence, float)
        self.assertGreaterEqual(confidence, 0.0)
        self.assertLessEqual(confidence, 1.0)
        
    def test_response_decision(self):
        result = self.meta.decide_response(
            "Bonjour !",
            {"emotional_state": {}, "recent_context": []},
            [] # Add active_goals argument
        )
        self.assertIn("action", result)
        self.assertIn("confidence", result)
        
class TestTimeManager(unittest.TestCase):
    def setUp(self):
        self.time_mgr = time_manager
        # Clear all reminders to ensure a clean state for each test
        self.time_mgr.reminders = []
        self.time_mgr._save_reminders() # Persist the empty list
        
    def test_add_reminder(self):
        future = datetime.now() + timedelta(days=1)
        reminder = self.time_mgr.add_reminder(
            "Test reminder",
            future,
            "test_user"
        )
        self.assertIsInstance(reminder, dict)
        self.assertIn("id", reminder)
        self.assertIn("description", reminder)
        self.assertIn("target_date", reminder)
        
    def test_get_upcoming_reminders(self):
        # Add a reminder that should be upcoming
        future_reminder_date = datetime.now() + timedelta(days=2)
        self.time_mgr.add_reminder("Upcoming test", future_reminder_date, "test_user")
        
        reminders = self.time_mgr.get_upcoming_reminders()
        self.assertIsInstance(reminders, list)
        self.assertGreater(len(reminders), 0)
        self.assertEqual(reminders[0]["description"], "Upcoming test")
        
class TestWebSearcher(unittest.TestCase):
    def setUp(self):
        self.searcher = web_searcher
        
    def test_search_cache(self):
        result = self.searcher.search("test query")
        self.assertIsInstance(result, dict)
        
        # Vérifier que le résultat est mis en cache
        cached = self.searcher._check_cache("test query")
        self.assertIsNotNone(cached)
        
class TestCore(unittest.TestCase):
    def test_basic_response(self):
        response = process_user_input("Bonjour !")
        self.assertIsInstance(response, str)
        self.assertGreater(len(response), 0)
        
    def test_error_handling(self):
        # Tester avec une entrée problématique
        response = process_user_input("")
        self.assertIsInstance(response, str)
        self.assertGreater(len(response), 0)
        
class TestCoreNewFeatures(unittest.TestCase):

    @patch('core.goal_system')
    @patch('core.memory_manager')
    @patch('core.metacognition')
    def test_check_proactive_goals_no_goals(self, mock_metacognition, mock_memory_manager, mock_goal_system):
        mock_goal_system.get_active_goals.return_value = []
        self.assertIsNone(_check_proactive_goals())

    @patch('core.goal_system')
    @patch('core.memory_manager')
    @patch('core.metacognition')
    def test_check_proactive_goals_unmentioned_goal(self, mock_metacognition, mock_memory_manager, mock_goal_system):
        mock_goal_system.get_active_goals.return_value = [
            {"id": "1", "description": "Apprendre le Python", "status": "active", "priority": 1, "deadline": None}
        ]
        mock_memory_manager.search.return_value = [] # Goal not mentioned recently
        response = _check_proactive_goals()
        self.assertIsNotNone(response)
        self.assertIn("Apprendre le Python", response)
        mock_metacognition.introspect.assert_called_once()

    @patch('core.goal_system')
    @patch('core.memory_manager')
    @patch('core.metacognition')
    def test_check_proactive_goals_approaching_deadline(self, mock_metacognition, mock_memory_manager, mock_goal_system):
        future_deadline = (datetime.now() + timedelta(days=1)).isoformat()
        mock_goal_system.get_active_goals.return_value = [
            {"id": "2", "description": "Finir le projet", "status": "active", "priority": 2, "deadline": future_deadline}
        ]
        mock_memory_manager.search.return_value = [
            {"memory": {"desc": "Finir le projet", "timestamp": datetime.now().isoformat()}, "score": 1.0} # Mentioned recently
        ]
        response = _check_proactive_goals()
        self.assertIsNotNone(response)
        self.assertIn("Finir le projet", response)
        mock_metacognition.introspect.assert_called_once()

    @patch('core.personality_system')
    def test_process_user_feedback_add_preference(self, mock_personality_system):
        response = _process_user_feedback("Je préfère les pommes")
        self.assertIsNotNone(response)
        self.assertIn("pommes", response)
        mock_personality_system.add_preference.assert_called_once_with("pommes", is_like=True)

    @patch('core.personality_system')
    def test_process_user_feedback_update_preference(self, mock_personality_system):
        response = _process_user_feedback("Ma préférence est les oranges, pas les pommes")
        self.assertIsNotNone(response)
        self.assertIn("oranges", response)
        mock_personality_system.add_preference.assert_called_once_with("oranges", is_like=True)
        mock_personality_system.remove_preference.assert_called_once_with("pommes", is_like=True)

    @patch('core.send_inference_prompt')
    @patch('core.emotional_system')
    @patch('core.memory_manager')
    @patch('core.update_working_memory')
    def test_process_sensory_input(self, mock_update_working_memory, mock_memory_manager, mock_emotional_system, mock_send_inference_prompt):
        mock_send_inference_prompt.return_value = {"text": '{"emotion": {"valence": 0.5, "intensity": 0.6, "control": 0.7}, "objects": ["chat"], "context": "ambiance joyeuse"}'}
        
        sensory_desc = "L'utilisateur sourit et un chat joue à côté."
        response = process_sensory_input(sensory_desc)
        
        self.assertIsNotNone(response)
        self.assertIn("Observation sensorielle traitée", response)
        mock_send_inference_prompt.assert_called_once()
        mock_emotional_system.update_emotion.assert_called_once()
        mock_memory_manager.ajouter_evenement.assert_called_once()
        mock_update_working_memory.assert_any_call("last_observed_objects", ["chat"])
        mock_update_working_memory.assert_any_call("last_sensory_context", "ambiance joyeuse")

if __name__ == '__main__':
    unittest.main()