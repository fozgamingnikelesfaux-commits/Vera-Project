import sys
import os
from pathlib import Path
import shutil
from datetime import datetime, timedelta

# Add the project root to the Python path
sys.path.insert(0, os.path.abspath('.'))

from self_evolution_engine import self_evolution_engine as see_instance

def run_test():
    print("Starting test for tool and documentation creation...")

    # Define a dummy task description
    test_task_description = "Créer un outil pour saluer l'utilisateur de manière personnalisée"
    
    # Call the propose_new_tool method directly
    # This will trigger the LLM calls and file generation
    print(f"Proposing new tool for task: '{test_task_description}'")
    try:
        result = see_instance.propose_new_tool(test_task_description)
    except Exception as e:
        print(f"An error occurred during tool proposal: {e}")
        print("Test failed.")
        return

    if not result:
        print("Tool proposal did not return a result. This might indicate a problem or a cooldown.")
        print("Test failed.")
        return

    # Extract the tool name from the parsed plan
    parsed_plan = result.get("parsed_plan", {})
    tool_design = parsed_plan.get("tool_design", {})
    tool_name = tool_design.get("name")

    if not tool_name:
        print("Failed to extract tool name from the parsed plan.")
        print("Test failed.")
        return

    print(f"Tool name extracted: '{tool_name}'")

    # Construct the expected paths
    project_dir = see_instance.PROJECTS_ROOT_DIR / tool_name
    expected_md_path = project_dir / f"{tool_name}.md"
    expected_py_path = project_dir / f"{tool_name}.py"

    print(f"Checking for .md file at: {expected_md_path}")
    print(f"Checking for .py file at: {expected_py_path}")

    # Verify if the files exist
    md_exists = expected_md_path.exists()
    py_exists = expected_py_path.exists()

    if md_exists and py_exists:
        print("\nSUCCESS: Both .md and .py files were created successfully!")
        print(f"  .md file: {expected_md_path}")
        print(f"  .py file: {expected_py_path}")
        
        # Optional: Read and print content for verification
        # with open(expected_md_path, 'r', encoding='utf-8') as f:
        #     print("\n--- .md Content ---")
        #     print(f.read())
        # with open(expected_py_path, 'r', encoding='utf-8') as f:
        #     print("\n--- .py Content ---")
        #     print(f.read())

    else:
        print("\nFAILURE: One or both files were not created.")
        if not md_exists:
            print(f"  .md file NOT found at: {expected_md_path}")
        if not py_exists:
            print(f"  .py file NOT found at: {expected_py_path}")

    # Clean up the created directory
    if project_dir.exists():
        print(f"\nCleaning up test directory: {project_dir}")
        shutil.rmtree(project_dir)
        print("Cleanup complete.")
    
    print("\nTest finished.")

if __name__ == "__main__":
    # Temporarily disable the daily proposal limit for this test
    # This is a hack for testing purposes. In a real scenario, you'd mock attention_manager.
    # For now, we'll just ensure the count is reset.
    from attention_manager import attention_manager
    attention_manager.update_focus("daily_tool_proposal_count", 0, salience=0.1, expiry_seconds=None)
    attention_manager.update_focus("last_tool_proposal_date", (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d"), salience=0.1, expiry_seconds=None)
    
    run_test()