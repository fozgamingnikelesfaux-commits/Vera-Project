from typing import Dict, Any, List, Optional
from datetime import datetime
import threading
from tools.logger import VeraLogger
from db_manager import db_manager # NEW: Import DbManager
from db_config import TABLE_NAMES # NEW: Import TABLE_NAMES

logger = VeraLogger("attention_manager")

class AttentionManager:
    DECAY_RATE = 0.05  # Per minute
    SALIENCE_THRESHOLD = 0.1  # Salience below which an item is removed
    MAX_DAILY_PROACTIVE_LEARNING_TASKS = 3 # NEW: Define the maximum number of daily proactive learning tasks

    def __init__(self):
        self.lock = threading.RLock()  # Use RLock for re-entrant locking
        self.logger = VeraLogger("attention_manager") # Initialize logger first
        self.current_focus: Dict[str, Dict[str, Any]] = {}
        self._is_thinking_hard: bool = False # New: Separate flag for thinking hard state
        self._is_processing_user_input: bool = False # NEW: Flag for ongoing user input processing
        self.table_name = TABLE_NAMES["attention_focus"]
        self.doc_id = "current_focus"
        self._load_focus()

    def _load_focus(self):
        if self.current_focus: # Prevent re-loading if already populated
            self.logger.debug("AttentionManager.current_focus is already populated, skipping _load_focus to prevent reset.")
            return

        focus = db_manager.get_document("attention_focus", "current_focus")
        if focus and isinstance(focus, dict): # Ensure focus is a dictionary
            for key, content in focus.items():
                if isinstance(content, dict) and "timestamp" in content and "salience" in content: # Ensure content is a dict
                    
                    # Convert timestamp string to datetime object upon loading
                    if isinstance(content.get("timestamp"), str):
                        try:
                            content["timestamp"] = datetime.fromisoformat(content["timestamp"])
                        except ValueError:
                            self.logger.warning(f"Invalid timestamp format for '{key}': {content.get('timestamp')}. Setting to now.")
                            content["timestamp"] = datetime.now()
                    elif not isinstance(content.get("timestamp"), datetime): # If it's not a string and not datetime, assume now
                        content["timestamp"] = datetime.now()

                    # Recalculate expiry_timestamp for pre_computed_internal_context_summary upon loading
                    # This ensures consistency even if loaded from an old state
                    if key == "pre_computed_internal_context_summary" and content.get("timestamp"):
                        from datetime import timedelta
                        content["expiry_timestamp"] = content["timestamp"] + timedelta(seconds=3600 * 24)
                        self.logger.debug(f"Recalculated expiry_timestamp for pre_computed_internal_context_summary: {content['expiry_timestamp']}")
                    else: # Ensure other expiry timestamps are also datetime objects
                        if isinstance(content.get("expiry_timestamp"), str):
                            try:
                                content["expiry_timestamp"] = datetime.fromisoformat(content["expiry_timestamp"])
                            except ValueError:
                                self.logger.warning(f"Invalid expiry_timestamp format for '{key}': {content.get('expiry_timestamp')}. Setting to None.")
                                content["expiry_timestamp"] = None
                        elif not isinstance(content.get("expiry_timestamp"), datetime):
                            content["expiry_timestamp"] = None

                    self.current_focus[key] = content
                else:
                    self.logger.warning(f"Invalid focus item '{key}': expected dict, got {type(content)}. Item will be ignored.")
        
        # NEW: Ensure daily_proactive_learning_tasks_count is reset on application start
        now = datetime.now()
        # Always reset the daily count on application start for a fresh session
        self.current_focus["daily_proactive_learning_tasks_count"] = {
            "data": 0,
            "timestamp": now.isoformat(),
            "salience": 0.1, # Low salience for metadata
            "expiry_timestamp": None, # Never expires by time
            "last_reset_date": now.date().isoformat() # Store only the date
        }
        self.logger.info("Daily proactive learning task count reset for new application session.")
            
        self._save_focus() # Save any changes made during load

    def _save_focus(self):
        """Saves focus to DB, converting datetime objects to ISO format strings."""
        with self.lock:
            savable_focus = {}
            for source, content in self.current_focus.items():
                timestamp_value = content.get("timestamp")
                expiry_timestamp_value = content.get("expiry_timestamp")
                last_reset_date_value = content.get("last_reset_date") 

                # Convert datetime objects to ISO format strings, keep strings as is
                if isinstance(timestamp_value, datetime):
                    timestamp_value = timestamp_value.isoformat()
                
                if isinstance(expiry_timestamp_value, datetime):
                    expiry_timestamp_value = expiry_timestamp_value.isoformat()
                
                # Ensure last_reset_date is stored as a date string (YYYY-MM-DD)
                if isinstance(last_reset_date_value, datetime):
                    last_reset_date_value = last_reset_date_value.date().isoformat() # Convert to date string
                elif isinstance(last_reset_date_value, str):
                    try: # Validate it's a date string, otherwise convert it
                        datetime.fromisoformat(last_reset_date_value).date().isoformat()
                    except ValueError:
                        last_reset_date_value = datetime.now().date().isoformat() # Default to current date if invalid

                savable_focus[source] = {
                    "data": content.get("data"),
                    "timestamp": timestamp_value,
                    "salience": content.get("salience"),
                    "expiry_timestamp": expiry_timestamp_value,
                    "last_reset_date": last_reset_date_value # Save last_reset_date as date string
                }

            db_manager.insert_document(self.table_name, self.doc_id, savable_focus)
            self.logger.debug("Attention focus saved.") # Using self.logger here

    def increment_daily_learning_task_count(self):
        """Increments the daily proactive learning task count, handling daily reset."""
        with self.lock:
            now = datetime.now()
            daily_count_item = self.current_focus.get("daily_proactive_learning_tasks_count")

            self.logger.debug(f"increment_daily_learning_task_count: Initial daily_count_item: {daily_count_item}, Current date: {now.date().isoformat()}")

            # Ensure the item exists and is up-to-date
            # Compare stored date string directly with current date string
            if not daily_count_item or daily_count_item.get("last_reset_date") != now.date().isoformat():
                self.logger.info(f"increment_daily_learning_task_count: Resetting count before increment. Old item: {daily_count_item}, New date: {now.date().isoformat()}")
                self.current_focus["daily_proactive_learning_tasks_count"] = {
                    "data": 0,
                    "timestamp": now.isoformat(),
                    "salience": 0.1,
                    "expiry_timestamp": None,
                    "last_reset_date": now.date().isoformat() # Store only the date
                }
                self.logger.info(f"Daily proactive learning task count reset for increment. Count is now {self.current_focus['daily_proactive_learning_tasks_count']['data']}.")
            
            old_count = self.current_focus["daily_proactive_learning_tasks_count"]["data"]
            # NEW: Cap the count at MAX_DAILY_PROACTIVE_LEARNING_TASKS
            self.current_focus["daily_proactive_learning_tasks_count"]["data"] = min(old_count + 1, self.MAX_DAILY_PROACTIVE_LEARNING_TASKS)
            new_count = self.current_focus["daily_proactive_learning_tasks_count"]["data"]
            self.current_focus["daily_proactive_learning_tasks_count"]["timestamp"] = now.isoformat()
            self.logger.info(f"increment_daily_learning_task_count: Count updated from {old_count} to {new_count} (capped at {self.MAX_DAILY_PROACTIVE_LEARNING_TASKS}).")
            self._save_focus()
            self.logger.info(f"Daily proactive learning task count updated to {self.current_focus['daily_proactive_learning_tasks_count']['data']}.")

    def get_daily_learning_task_count(self) -> int:
        """Returns the current daily proactive learning task count, ensuring daily reset logic is applied."""
        with self.lock:
            now = datetime.now()
            daily_count_item = self.current_focus.get("daily_proactive_learning_tasks_count")
            
            self.logger.debug(f"get_daily_learning_task_count: Initial daily_count_item: {daily_count_item}, Current date: {now.date().isoformat()}")

            # Ensure the item exists and is up-to-date before returning
            # Compare stored date string directly with current date string
            if not daily_count_item or daily_count_item.get("last_reset_date") != now.date().isoformat():
                self.logger.info(f"get_daily_learning_task_count: Resetting count. Old item: {daily_count_item}, New date: {now.date().isoformat()}")
                self.current_focus["daily_proactive_learning_tasks_count"] = {
                    "data": 0,
                    "timestamp": now.isoformat(),
                    "salience": 0.1,
                    "expiry_timestamp": None,
                    "last_reset_date": now.date().isoformat() # Store only the date
                }
                self.logger.info(f"Daily proactive learning task count reset before retrieval due to new day. Count is now {self.current_focus['daily_proactive_learning_tasks_count']['data']}.")
                self._save_focus() # Save the reset if it happened
            
            count = self.current_focus.get("daily_proactive_learning_tasks_count", {}).get("data", 0)
            self.logger.debug(f"get_daily_learning_task_count: Returning count: {count}")
            return count

    def is_expired(self, source: str) -> bool:
        """Checks if a specific item in the focus has expired."""
        with self.lock:
            item = self.current_focus.get(source)
            if item and item.get("expiry_timestamp"):
                expiry_ts = item.get("expiry_timestamp")
                if isinstance(expiry_ts, str):
                    try:
                        expiry_ts = datetime.fromisoformat(expiry_ts)
                    except ValueError:
                        self.logger.warning(f"Invalid expiry_timestamp format for '{source}': {expiry_ts}. Treating as not expired.")
                        return False
                return datetime.now() > expiry_ts
            return False
    def set_thinking_hard(self, state: bool):
        """Sets the 'is_vera_thinking_hard' flag."""
        with self.lock:
            self._is_thinking_hard = state
            self._save_focus()
            self.logger.info(f"Vera is thinking hard: {state}")

    def is_thinking_hard(self) -> bool:
        """Returns the current state of the 'is_vera_thinking_hard' flag."""
        with self.lock:
            return self._is_thinking_hard

    def set_processing_user_input(self, state: bool):
        """Sets the 'is_processing_user_input' flag."""
        with self.lock:
            self._is_processing_user_input = state
            self._save_focus()
            self.logger.info(f"Vera is processing user input: {state}")

    def is_processing_user_input(self) -> bool:
        """Returns the current state of the 'is_processing_user_input' flag."""
        with self.lock:
            return self._is_processing_user_input

    def decay_focus(self):
        """
        Decays salience and removes expired or low-salience items.
        """
        with self.lock:
            now = datetime.now()
            items_to_remove = []
            
            # Create a copy to iterate, allowing modification of self.current_focus
            focus_copy = dict(self.current_focus) 

            for source, content in focus_copy.items():
                # 1. Check for expiry
                expiry_ts = content.get("expiry_timestamp")
                if expiry_ts: # Check if expiry_ts exists before comparing
                    # Convert to datetime object for comparison if it's a string
                    if isinstance(expiry_ts, str):
                        try:
                            expiry_ts = datetime.fromisoformat(expiry_ts)
                        except ValueError:
                            self.logger.warning(f"Invalid expiry_timestamp format for '{source}': {expiry_ts}. Ignoring expiry.")
                            expiry_ts = None # Treat as never expiring if format is bad

                if expiry_ts and now > expiry_ts:
                    items_to_remove.append(source)
                    self.logger.debug(f"Item '{source}' removed from focus due to expiration.")
                    continue

                # 2. Decay salience (don't decay critical items)
                # Ensure these items are not just in content but also part of the focus system logic
                if source in ["narrative_self_summary", "last_narrative_update_time", "last_monologue_time", 
                              "last_dream_time", "last_insight_generation_time", "metacognitive_state", 
                              "visual_analysis_cooldown", "daily_proactive_learning_tasks_count", # Existing critical items
                              "active_goals", "pending_answer_to_question", "last_user_interaction_time", 
                              "last_vera_response_time", "last_proactive_learning_proposal_time", "last_social_curiosity_time",
                              "pre_computed_internal_context_summary"]: # NEW: Critical item to prevent salience decay
                    continue
                
                # Check if timestamp is a datetime object before calculation
                timestamp_obj = content.get("timestamp")
                if isinstance(timestamp_obj, str):
                    try:
                        timestamp_obj = datetime.fromisoformat(timestamp_obj)
                    except ValueError:
                        self.logger.warning(f"Invalid timestamp format for '{source}': {timestamp_obj}. Skipping salience decay.")
                        continue # Skip decay if timestamp is invalid

                if timestamp_obj: # Only decay if we have a valid datetime object
                    age_minutes = (now - timestamp_obj).total_seconds() / 60
                    decay_amount = age_minutes * self.DECAY_RATE
                    new_salience = content["salience"] - decay_amount
                    self.current_focus[source]["salience"] = new_salience # Update original dict

                    # 3. Check for low salience
                    if new_salience < self.SALIENCE_THRESHOLD:
                        items_to_remove.append(source)
                        self.logger.debug(f"Item '{source}' removed from focus due to low salience.")
            
            if items_to_remove:
                for source in set(items_to_remove): # Use set to avoid duplicates
                    if source in self.current_focus:
                        del self.current_focus[source]
                self._save_focus() # Save after modifications
            elif focus_copy != self.current_focus: # If salience decay happened, but no removals
                 self._save_focus() # Save to persist decayed salience


    def update_focus(self, source: str, data: Any, salience: float = 0.5, expiry_seconds: Optional[int] = None):
        """
        Updates an item in the focus, optionally with an expiry time.
        """
        from datetime import timedelta
        with self.lock:
            # Decay focus first to clean up old items and adjust salience
            self.decay_focus()

            item = {
                "data": data,
                "timestamp": datetime.now(),
                "salience": salience,
                "expiry_timestamp": None
            }
            if expiry_seconds:
                item["expiry_timestamp"] = datetime.now() + timedelta(seconds=expiry_seconds)

            self.current_focus[source] = item
            
            try:
                self._save_focus()
            except Exception as e:
                self.logger.error(f"Failed to save focus after updating {source}: {e}")
            
            self.logger.debug(f"Focus updated for '{source}' with salience {salience}", source=source)

    def get_current_focus(self, salience_threshold: float = 0.2) -> Dict[str, Any]:
        """
        Returns a simplified view of the current focus for other modules.
        All datetime objects are converted to ISO format strings for JSON serialization.
        """
        with self.lock:
            # self.decay_focus() # REMOVED: Decay focus should be periodic, not on every get_current_focus
            
            serializable_focus = {}
            for source, content in self.current_focus.items():
                if content["salience"] >= salience_threshold and "timestamp" in content:
                    # Create a copy to avoid modifying the original internal dict
                    item_content = content.copy()
                    
                    # Convert datetime objects to ISO strings
                    if isinstance(item_content.get("timestamp"), datetime):
                        item_content["timestamp"] = item_content["timestamp"].isoformat()
                    if isinstance(item_content.get("expiry_timestamp"), datetime):
                        item_content["expiry_timestamp"] = item_content["expiry_timestamp"].isoformat()
                    
                    serializable_focus[source] = {
                        "data": item_content["data"],
                        "timestamp": item_content["timestamp"]
                        # We don't necessarily need to return salience or expiry_timestamp here
                        # if the consumer (core.py) only needs data and timestamp for context.
                        # However, for full fidelity, we can include them if needed.
                        # For now, let's keep it minimal as core.py only needs `data` and `timestamp`.
                    }
            return serializable_focus

    def get_focus_item(self, source: str) -> Optional[Dict[str, Any]]:
        """
        Returns the full data for a single item from the focus, if it exists.
        """
        with self.lock:
            item = self.current_focus.get(source)
            if source == "pre_computed_internal_context_summary" and item:
                self.logger.debug(f"Retrieving pre_computed_internal_context_summary. Timestamp: {item.get('timestamp')}")
            return item

    def clear_focus_item(self, source: str):
        """
        Removes a specific item from the focus.
        """
        with self.lock:
            if source in self.current_focus:
                del self.current_focus[source]
                self._save_focus()
                self.logger.info(f"Item '{source}' explicitly removed from focus.")

    def clear_focus(self):
        """
        Performs a hard reset of the attention focus.
        """
        with self.lock:
            self.current_focus = {}
            self._is_thinking_hard = False # Reset this flag as well
            self._is_processing_user_input = False # Reset this flag as well
            self._save_focus()
            self.logger.info("Attention focus has been completely cleared (hard reset).")

# Instance globale
attention_manager = AttentionManager()