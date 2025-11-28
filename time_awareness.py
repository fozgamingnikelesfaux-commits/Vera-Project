"""
Module pour gérer la conscience temporelle de Vera.
"""
from datetime import datetime

def get_current_time_context():
    """Retourne le contexte temporel actuel"""
    now = datetime.now()
    
    # Format français pour plus de naturel
    return {
        "timestamp": now.isoformat(),
        "date": now.strftime("%d %B %Y"),
        "heure": now.strftime("%H:%M"),
        "jour_semaine": now.strftime("%A"),
        "est_matin": now.hour < 12,
        "est_apres_midi": 12 <= now.hour < 18,
        "est_soir": now.hour >= 18
    }

def format_timestamp(timestamp_str: str) -> str:
    """Formate un timestamp ISO en texte naturel"""
    try:
        dt = datetime.fromisoformat(timestamp_str)
        return dt.strftime("%d %B %Y à %H:%M")
    except:
        return "date inconnue"