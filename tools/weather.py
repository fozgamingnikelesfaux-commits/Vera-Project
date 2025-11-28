"""
This module handles weather-related functionalities.
"""
from typing import Dict, Any
import requests
import json
import os
from tools.logger import VeraLogger

logger = VeraLogger("weather")

def get_weather(city: str) -> Dict[str, Any]:
    """
    Gets the weather for a given city.
    """
    try:
        with open(os.path.join("data", "config.json"), "r", encoding="utf-8") as f:
            config = json.load(f)
        api_key = config.get("weather_api_key")

        if not api_key:
            logger.warning("Weather API key is not set in data/config.json.")
            return {"status": "error", "message": "Weather API key not configured."}

        # OpenWeatherMap API call
        url = f"http://api.openweathermap.org/data/2.5/weather?q={city}&appid={api_key}&units=metric&lang=fr"
        response = requests.get(url)
        response.raise_for_status()  # Raise an exception for HTTP errors (4xx or 5xx)
        weather_data = response.json()

        if weather_data.get("cod") == 200: # Check if the API call was successful
            temperature = weather_data["main"]["temp"]
            description = weather_data["weather"][0]["description"]
            return {
                "status": "success",
                "city": city,
                "temperature": temperature,
                "description": description
            }
        else:
            logger.error(f"OpenWeatherMap API error for {city}: {weather_data.get('message', 'Unknown error')}")
            return {"status": "error", "message": f"Could not get weather for {city}: {weather_data.get('message', 'Unknown error')}"}

    except requests.exceptions.RequestException as e:
        logger.error(f"Network or API request error for {city}: {e}", exc_info=True)
        return {"status": "error", "message": f"Network or API request error: {e}"}
    except Exception as e:
        logger.error(f"Error getting weather for {city}: {e}", exc_info=True)
        return {"status": "error", "message": str(e)}
