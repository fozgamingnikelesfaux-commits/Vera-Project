from websocket_server import send_command_to_avatar
import logging

logger = logging.getLogger(__name__)

# New, more powerful recipe structure
# Each recipe is a dictionary containing 'blend_shapes' and 'animations'
EXPRESSION_RECIPES = {
    "neutral": {
        "blend_shapes": [
            ("Mouth_Smile_L", 0.0),
            ("Mouth_Smile_R", 0.0),
            ("Cheek_Raise_L", 0.0),
            ("Cheek_Raise_R", 0.0),
            ("Eye_Squint_L", 0.0),
            ("Eye_Squint_R", 0.0),
            ("Eyebrow_Raise_L", 0.0),
            ("Eyebrow_Raise_R", 0.0),
        ],
        "animations": []
    },
    "happy": {
        "blend_shapes": [
            ("Mouth_Smile_L", 85.0),
            ("Mouth_Smile_R", 85.0),
            ("Cheek_Raise_L", 60.0),
            ("Cheek_Raise_R", 60.0),
            ("Eye_Squint_L", 30.0),
            ("Eye_Squint_R", 30.0),
            ("Eyebrow_Raise_L", 20.0),
            ("Eyebrow_Raise_R", 20.0),
        ],
        "animations": [
            "jaw_open" # The trigger for the jaw bone animation
        ]
    }
}

def set_expression(emotion: str):
    """
    Sets the avatar's facial expression based on a predefined recipe
    that can include both blend shapes and animation triggers.
    """
    if emotion not in EXPRESSION_RECIPES:
        logger.warning(f"Expression recipe for '{emotion}' not found.")
        return

    logger.info(f"Setting expression to '{emotion}'.")
    recipe = EXPRESSION_RECIPES[emotion]

    # Process blend shapes
    if "blend_shapes" in recipe:
        for blend_shape_name, weight in recipe["blend_shapes"]:
            command = {
                "type": "expression",
                "name": blend_shape_name,
                "value": weight
            }
            send_command_to_avatar(command)

    # Process animation triggers
    if "animations" in recipe:
        for animation_trigger in recipe["animations"]:
            command = {
                "type": "animation",
                "name": animation_trigger
            }
            send_command_to_avatar(command)

def update_recipe(emotion: str, blend_shape_name: str, new_weight: float):
    """
    Updates a specific blend shape's weight in an expression recipe.
    This is part of the 'NeRD' learning loop.
    """
    if emotion not in EXPRESSION_RECIPES:
        logger.warning(f"Cannot update recipe: Emotion '{emotion}' not found.")
        return

    # This function would need to be updated if we want to modify animations too
    recipe_bs = EXPRESSION_RECIPES[emotion].get("blend_shapes", [])
    found = False
    for i, (bs_name, _) in enumerate(recipe_bs):
        if bs_name == blend_shape_name:
            recipe_bs[i] = (bs_name, new_weight)
            found = True
            break
    
    if not found:
        recipe_bs.append((blend_shape_name, new_weight))

    logger.info(f"Updated recipe for '{emotion}': set '{blend_shape_name}' to {new_weight}%.")
