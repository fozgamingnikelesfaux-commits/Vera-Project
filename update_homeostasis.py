import sys
import os

# Add the project root to the sys.path to allow imports
sys.path.insert(0, os.path.abspath('.'))

from db_manager import db_manager
from db_config import TABLE_NAMES
from homeostasis_system import HomeostasisSystem # Import the class to get defaults

def update_homeostasis_curiosity_in_db():
    print("Starting update of homeostasis 'curiosity' in DB...")
    
    # Get the table name and doc ID from the HomeostasisSystem instance
    homeostasis_instance = HomeostasisSystem()
    table_name = homeostasis_instance.table_name
    doc_id = homeostasis_instance.doc_id

    # Get the new default values for curiosity from the code
    new_defaults = homeostasis_instance._get_default_state()
    new_curiosity_params = new_defaults["needs"]["curiosity"]

    # Load the current state from the database
    current_state = db_manager.get_document(table_name, doc_id)

    if current_state is None:
        print(f"No existing homeostasis state found for doc_id: {doc_id}. Initializing with new defaults.")
        # If no state exists, it will be created with new defaults on next Vera run
        # but we can also force it here for consistency
        db_manager.insert_document(table_name, doc_id, new_defaults)
        print("Homeostasis state initialized with new default values.")
    else:
        # Update only the 'curiosity' parameters
        current_state["needs"]["curiosity"].update(new_curiosity_params)
        db_manager.insert_document(table_name, doc_id, current_state)
        print(f"Successfully updated 'curiosity' parameters in homeostasis state for doc_id: {doc_id}.")
        print(f"New 'curiosity' parameters: {current_state['needs']['curiosity']}")

    print("Homeostasis update script finished.")

if __name__ == "__main__":
    update_homeostasis_curiosity_in_db()
