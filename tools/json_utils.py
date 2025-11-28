import json
from datetime import datetime

def datetime_converter(o):
    """
    JSON serializer for objects not serializable by default json code.
    Converts datetime objects to ISO 8601 strings.
    """
    if isinstance(o, datetime):
        return o.isoformat()
    raise TypeError(repr(o) + " is not JSON serializable")

def to_json_serializable(obj):
    """
    Recursively converts datetime objects within a dictionary or list to ISO 8601 strings.
    """
    if isinstance(obj, datetime):
        return obj.isoformat()
    elif isinstance(obj, dict):
        return {k: to_json_serializable(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [to_json_serializable(elem) for elem in obj]
    else:
        return obj
