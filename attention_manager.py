from typing import Dict, Any, List, Optional
from datetime import datetime
import threading
from tools.logger import VeraLogger
from db_manager import db_manager  # NEW: Import DbManager
from db_config import TABLE_NAMES  # NEW: Import TABLE_NAMES

logger = VeraLogger("attention_manager")


class AttentionManager:

    MAX_COGNITIVE_BUDGET = 100  # Maximum cognitive budget

    BUDGET_REGEN_RATE = 0.5   # Points per minute for regeneration

    DECAY_RATE = 0.05  # Per minute

    SALIENCE_THRESHOLD = 0.1  # Salience below which an item is removed

    def __init__(self):

        self.lock = threading.RLock()  # Use RLock for re-entrant locking

        # Initialize logger first
        self.logger = VeraLogger("attention_manager")

        self.current_focus: Dict[str, Dict[str, Any]] = {}

        # New: Separate flag for thinking hard state
        self._is_thinking_hard: bool = False

        # NEW: Flag for ongoing user input processing
        self._is_processing_user_input: bool = False

        self.table_name = TABLE_NAMES["attention_focus"]

        self.doc_id = "current_focus"

        self._load_focus()

    def _load_focus(self):

        if self.current_focus:  # Prevent re-loading if already populated

            self.logger.debug(
                "AttentionManager.current_focus is already populated, skipping _load_focus to prevent reset.")

            return

        focus = db_manager.get_document("attention_focus", "current_focus")

        if focus and isinstance(focus, dict):  # Ensure focus is a dictionary

            for key, content in focus.items():

                if isinstance(
                        content, dict) and "timestamp" in content and "salience" in content:  # Ensure content is a dict

                    # Convert timestamp string to datetime object upon loading

                    if isinstance(content.get("timestamp"), str):

                        try:

                            content["timestamp"] = datetime.fromisoformat(
                                content["timestamp"])

                        except ValueError:

                            self.logger.warning(
                                f"Invalid timestamp format for '{key}': {content.get('timestamp')}. Setting to now.")

                            content["timestamp"] = datetime.now()

                    # If it's not a string and not datetime, assume now
                    elif not isinstance(content.get("timestamp"), datetime):

                        content["timestamp"] = datetime.now()

                    # Recalculate expiry_timestamp for
                    # pre_computed_internal_context_summary upon loading

                    # This ensures consistency even if loaded from an old state

                    if key == "pre_computed_internal_context_summary" and content.get(
                            "timestamp"):

                        from datetime import timedelta

                        content["expiry_timestamp"] = content["timestamp"] + \
                            timedelta(seconds=3600 * 24)

                        self.logger.debug(
                            f"Recalculated expiry_timestamp for pre_computed_internal_context_summary: {content['expiry_timestamp']}")

                    else:  # Ensure other expiry timestamps are also datetime objects

                        if isinstance(content.get("expiry_timestamp"), str):

                            try:

                                content["expiry_timestamp"] = datetime.fromisoformat(
                                    content["expiry_timestamp"])

                            except ValueError:

                                self.logger.warning(
                                    f"Invalid expiry_timestamp format for '{key}': {content.get('expiry_timestamp')}. Setting to None.")

                                content["expiry_timestamp"] = None

                        elif not isinstance(content.get("expiry_timestamp"), datetime):

                            content["expiry_timestamp"] = None

                    self.current_focus[key] = content

                else:

                    self.logger.warning(
                        f"Invalid focus item '{key}': expected dict, got {type(content)}. Item will be ignored.")

                self._save_focus()  # Save any changes made during load

    def _save_focus(self):
        """Saves focus to DB, converting datetime objects to ISO format strings."""

        with self.lock:

            savable_focus = {}

            for source, content in self.current_focus.items():

                timestamp_value = content.get("timestamp")

                expiry_timestamp_value = content.get("expiry_timestamp")

                last_reset_date_value = content.get("last_reset_date")

                # Convert datetime objects to ISO format strings, keep strings
                # as is

                if isinstance(timestamp_value, datetime):

                    timestamp_value = timestamp_value.isoformat()

                if isinstance(expiry_timestamp_value, datetime):

                    expiry_timestamp_value = expiry_timestamp_value.isoformat()

                # Ensure last_reset_date is stored as a date string
                # (YYYY-MM-DD)

                if isinstance(last_reset_date_value, datetime):

                    last_reset_date_value = last_reset_date_value.date(
                    ).isoformat()  # Convert to date string

                elif isinstance(last_reset_date_value, str):

                    try:  # Validate it's a date string, otherwise convert it

                        datetime.fromisoformat(
                            last_reset_date_value).date().isoformat()

                    except ValueError:

                        # Default to current date if invalid
                        last_reset_date_value = datetime.now().date().isoformat()

                savable_focus[source] = {

                    "data": content.get("data"),

                    "timestamp": timestamp_value,

                    "salience": content.get("salience"),

                    "expiry_timestamp": expiry_timestamp_value,

                    "last_reset_date": last_reset_date_value  # Save last_reset_date as date string

                }

            db_manager.insert_document(
                self.table_name, self.doc_id, savable_focus)

            # Using self.logger here
            self.logger.debug("Attention focus saved.")

    def reset_daily_tool_proposal_count(self):
        """Resets the daily tool proposal count."""

        with self.lock:

            now = datetime.now()

            self.current_focus["daily_tool_proposal_count"] = {

                "data": 0,

                "timestamp": now.isoformat(),

                "salience": 0.1,

                "expiry_timestamp": None,

                "last_reset_date": now.date().isoformat()

            }

            self.logger.info("Daily tool proposal count reset to 0.")

            self._save_focus()

    def _initialize_cognitive_budget(self):
        """Initializes the cognitive budget if it doesn't exist."""

        with self.lock:

            if "cognitive_budget" not in self.current_focus:

                self.current_focus["cognitive_budget"] = {

                    "data": {"current": self.MAX_COGNITIVE_BUDGET, "max": self.MAX_COGNITIVE_BUDGET},

                    "timestamp": datetime.now(),

                    "salience": 1.0,

                    "expiry_timestamp": None,

                    "last_regen_time": datetime.now()  # Track last regeneration time

                }

                self.logger.info(
                    f"Cognitive budget initialized to {self.MAX_COGNITIVE_BUDGET} points.")
                self._save_focus()

    def get_cognitive_budget(self) -> Dict[str, Any]:
        """Returns the current cognitive budget data (current, max)."""
        with self.lock:
            # First, ensure the budget item exists
            budget_item = self.current_focus.get("cognitive_budget")
            if not budget_item:
                self._initialize_cognitive_budget()
                budget_item = self.current_focus["cognitive_budget"]
            # Now, regenerate the budget
            self.regenerate_cognitive_budget()
            # Ensure last_regen_time is a datetime object
            if isinstance(budget_item.get("last_regen_time"), str):
                try:
                    budget_item["last_regen_time"] = datetime.fromisoformat(
                        budget_item["last_regen_time"])
                except ValueError:
                    self.logger.warning(
                        f"Invalid last_regen_time format: {budget_item.get('last_regen_time')}. Resetting.")
                    budget_item["last_regen_time"] = datetime.now()
                    self._save_focus()
            return budget_item["data"]

    def spend_cognitive_budget(self, cost: int) -> bool:
        """
        Spends a given cost from the cognitive budget.
        Returns True if successful, False if budget is insufficient.
        """
        with self.lock:
            self.regenerate_cognitive_budget()  # Regenerate before spending
            budget_item = self.current_focus.get("cognitive_budget")
            if not budget_item:
                self.logger.warning(
                    "Attempted to spend from an uninitialized cognitive budget. Initializing.")
                self._initialize_cognitive_budget()
                budget_item = self.current_focus["cognitive_budget"]

            current_budget = budget_item["data"]["current"]
            if current_budget >= cost:
                budget_item["data"]["current"] -= cost
                budget_item["timestamp"] = datetime.now()
                self.current_focus["cognitive_budget"] = budget_item
                self.logger.info(
                    f"Cognitive budget spent: -{cost}. Remaining: {budget_item['data']['current']}")
                self._save_focus()
                return True
            else:
                self.logger.warning(
                    f"Insufficient cognitive budget to spend {cost}. Current: {current_budget}")
                return False

    def regenerate_cognitive_budget(self):
        """
        Regenerates the cognitive budget over time. Called periodically.
        """
        with self.lock:
            budget_item = self.current_focus.get("cognitive_budget")
            if not budget_item:
                self.logger.debug(
                    "Cognitive budget not initialized, skipping regeneration.")
                return

            last_regen_time = budget_item.get("last_regen_time")

            # NEW: Handle case where last_regen_time might be None
            if last_regen_time is None:
                self.logger.warning("last_regen_time is None. Resetting to now for regen calculation.")
                last_regen_time = datetime.now()
                self._save_focus() # Save to persist the reset time

            if isinstance(last_regen_time, str):
                try:
                    last_regen_time = datetime.fromisoformat(
                        last_regen_time)
                except ValueError:
                    self.logger.warning(
                        f"Invalid last_regen_time format for budget: {last_regen_time}. Resetting to now for regen calculation.")
                    last_regen_time = datetime.now()
                    self._save_focus()

            now = datetime.now()

            time_since_last_regen = (
                now - last_regen_time).total_seconds() / 60  # In minutes

            if time_since_last_regen > 0:

                regen_amount = time_since_last_regen * self.BUDGET_REGEN_RATE

                current_budget = budget_item["data"]["current"]

                max_budget = budget_item["data"]["max"]

                new_budget = min(
                    current_budget + regen_amount, max_budget)

                if new_budget > current_budget:

                    budget_item["data"]["current"] = new_budget

                    budget_item["timestamp"] = now

                    # Update last regen time
                    budget_item["last_regen_time"] = now

                    self.current_focus["cognitive_budget"] = budget_item

                    self.logger.debug(
                        f"Cognitive budget regenerated: +{regen_amount:.2f}. New budget: {new_budget:.2f}")

                    self._save_focus()

            else:

                self.logger.debug(
                    "Not enough time passed for cognitive budget regeneration.")

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

                        self.logger.warning(
                            f"Invalid expiry_timestamp format for '{source}': {expiry_ts}. Treating as not expired.")

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

    def capture_consciousness_snapshot(self) -> Dict[str, Any]:
        """
        Captures the current internal state of Vera from various cognitive modules.
        This creates a rich, multi-modal "snapshot" of her consciousness at a point in time.

        Returns:
            A dictionary representing the complete snapshot.
        """
        # Use local imports to prevent circular dependency issues at module
        # load time
        from somatic_system import somatic_system
        from emotion_system import emotional_system, get_mood_state
        from personality_system import personality_system

        with self.lock:
            snapshot = {
                "timestamp": datetime.now().isoformat(),
                # Get all items for a full snapshot
                "attention_focus": self.get_current_focus(salience_threshold=0.0),
                "somatic_state": somatic_system.get_somatic_state(),
                "emotional_state": emotional_system.get_emotional_state(),
                "mood": get_mood_state(),
                "current_desires": personality_system.get_active_desires()
            }
            logger.info("Consciousness snapshot captured.")
            return snapshot

    def decay_focus(self):
        """
        Decays salience and removes expired or low-salience items.
        """
        with self.lock:
            now = datetime.now()
            items_to_remove = []

            # Create a copy to iterate, allowing modification of
            # self.current_focus
            focus_copy = dict(self.current_focus)

            for source, content in focus_copy.items():
                # 1. Check for expiry
                expiry_ts = content.get("expiry_timestamp")
                if expiry_ts:  # Check if expiry_ts exists before comparing
                    # Convert to datetime object for comparison if it's a
                    # string
                    if isinstance(expiry_ts, str):
                        try:
                            expiry_ts = datetime.fromisoformat(expiry_ts)
                        except ValueError:
                            self.logger.warning(
                                f"Invalid expiry_timestamp format for '{source}': {expiry_ts}. Ignoring expiry.")
                            expiry_ts = None  # Treat as never expiring if format is bad

                if expiry_ts and now > expiry_ts:
                    items_to_remove.append(source)
                    self.logger.debug(
                        f"Item '{source}' removed from focus due to expiration.")
                    continue

                # 2. Decay salience (don't decay critical items)
                # Ensure these items are not just in content but also part of
                # the focus system logic
                if source in ["narrative_self_summary", "last_narrative_update_time", "last_monologue_time",
                              "last_dream_time", "last_insight_generation_time", "metacognitive_state",
                              # Existing critical items
                              "visual_analysis_cooldown", "daily_proactive_learning_tasks_count",
                              "active_goals", "pending_answer_to_question", "last_user_interaction_time",
                              "last_vera_response_time", "last_proactive_learning_proposal_time", "last_social_curiosity_time",
                              "pre_computed_internal_context_summary"]:  # NEW: Critical item to prevent salience decay
                    continue

                # Check if timestamp is a datetime object before calculation
                timestamp_obj = content.get("timestamp")
                if isinstance(timestamp_obj, str):
                    try:
                        timestamp_obj = datetime.fromisoformat(timestamp_obj)
                    except ValueError:
                        self.logger.warning(
                            f"Invalid timestamp format for '{source}': {timestamp_obj}. Skipping salience decay.")
                        continue  # Skip decay if timestamp is invalid

                if timestamp_obj:  # Only decay if we have a valid datetime object
                    age_minutes = (now - timestamp_obj).total_seconds() / 60
                    decay_amount = age_minutes * self.DECAY_RATE
                    new_salience = content["salience"] - decay_amount
                    # Update original dict
                    self.current_focus[source]["salience"] = new_salience

                    # 3. Check for low salience
                    if new_salience < self.SALIENCE_THRESHOLD:
                        items_to_remove.append(source)
                        self.logger.debug(
                            f"Item '{source}' removed from focus due to low salience.")

            if items_to_remove:
                for source in set(
                        items_to_remove):  # Use set to avoid duplicates
                    if source in self.current_focus:
                        del self.current_focus[source]
                self._save_focus()  # Save after modifications
            elif focus_copy != self.current_focus:  # If salience decay happened, but no removals
                self._save_focus()  # Save to persist decayed salience

    def update_focus(self, source: str, data: Any,
                     salience: float = 0.5, expiry_seconds: Optional[int] = None):
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
                item["expiry_timestamp"] = datetime.now(
                ) + timedelta(seconds=expiry_seconds)

            self.current_focus[source] = item

            try:
                self._save_focus()
            except Exception as e:
                self.logger.error(
                    f"Failed to save focus after updating {source}: {e}")

            self.logger.debug(
                f"Focus updated for '{source}' with salience {salience}",
                source=source)

    def get_current_focus(
            self, salience_threshold: float = 0.2) -> Dict[str, Any]:
        """
        Returns a simplified view of the current focus for other modules.
        All datetime objects are converted to ISO format strings for JSON serialization.
        """
        with self.lock:
            # self.decay_focus() # REMOVED: Decay focus should be periodic, not
            # on every get_current_focus

            serializable_focus = {}
            for source, content in self.current_focus.items():
                if content["salience"] >= salience_threshold and "timestamp" in content:
                    # Create a copy to avoid modifying the original internal
                    # dict
                    item_content = content.copy()

                    # Convert datetime objects to ISO strings
                    if isinstance(item_content.get("timestamp"), datetime):
                        item_content["timestamp"] = item_content["timestamp"].isoformat(
                        )
                    if isinstance(item_content.get(
                            "expiry_timestamp"), datetime):
                        item_content["expiry_timestamp"] = item_content["expiry_timestamp"].isoformat(
                        )

                    serializable_focus[source] = {
                        "data": item_content["data"],
                        "timestamp": item_content["timestamp"]
                        # We don't necessarily need to return salience or expiry_timestamp here
                        # if the consumer (core.py) only needs data and timestamp for context.
                        # However, for full fidelity, we can include them if needed.
                        # For now, let's keep it minimal as core.py only needs
                        # `data` and `timestamp`.
                    }
            return serializable_focus

    def get_focus_item(self, source: str) -> Optional[Dict[str, Any]]:
        """
        Returns the full data for a single item from the focus, if it exists.
        """
        with self.lock:
            item = self.current_focus.get(source)
            if source == "pre_computed_internal_context_summary" and item:
                self.logger.debug(
                    f"Retrieving pre_computed_internal_context_summary. Timestamp: {item.get('timestamp')}")
            return item

    def clear_focus_item(self, source: str):
        """
        Removes a specific item from the focus.
        """
        with self.lock:
            if source in self.current_focus:
                del self.current_focus[source]
                self._save_focus()
                self.logger.info(
                    f"Item '{source}' explicitly removed from focus.")

    def clear_focus(self):
        """
        Performs a hard reset of the attention focus.
        """
        with self.lock:
            self.current_focus = {}
            self._is_thinking_hard = False  # Reset this flag as well
            self._is_processing_user_input = False  # Reset this flag as well
            self._save_focus()
            self.logger.info(
                "Attention focus has been completely cleared (hard reset).")

    def log_mistake(self, mistake_details: Dict[str, Any],
                    salience: float = 0.8, expiry_seconds: int = 3600 * 24):
        """
        Logs a mistake event in the attention focus.
        Args:
            mistake_details: A dictionary containing details about the mistake (e.g., "reason", "context", "action_taken").
            salience: The salience of this mistake in Vera's attention.
            expiry_seconds: How long this mistake should remain in focus (default: 24 hours).
        """
        self.update_focus(
            "last_mistake_info",
            mistake_details,
            salience,
            expiry_seconds)
        self.logger.warning(
            f"Mistake logged in attention focus: {mistake_details.get('reason', 'Unknown mistake')}")


# Instance globale
attention_manager = AttentionManager()
