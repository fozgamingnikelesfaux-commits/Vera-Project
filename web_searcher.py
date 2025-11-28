import sys
from typing import Optional, Dict
from datetime import datetime, timedelta
import threading

from tools.logger import VeraLogger
from error_handler import log_error
# Removed JSONManager

logger = VeraLogger("web_search")
print("WebSearcher.py version: 2025-11-10_DDGS_fix")

# Optional requests
try:
    import requests
    REQUESTS_AVAILABLE = True
except Exception:
    requests = None
    REQUESTS_AVAILABLE = False

# Optional beautifulsoup4
try:
    from bs4 import BeautifulSoup
    BEAUTIFULSOUP_AVAILABLE = True
except Exception:
    BeautifulSoup = None
    BEAUTIFULSOUP_AVAILABLE = False

# Optional wikipedia
try:
    import wikipedia
    WIKIPEDIA_AVAILABLE = True
except ImportError:
    wikipedia = None
    WIKIPEDIA_AVAILABLE = False

# Optional ddgs
try:
    from ddgs import DDGS
    DDGS_AVAILABLE = True
except ImportError as e:
    logger.error(f"ddgs module import failed: {e}")
    DDGS = None
    DDGS_AVAILABLE = False
except Exception as e:
    logger.error(f"Unexpected error during ddgs module import: {e}")
    DDGS = None
    DDGS_AVAILABLE = False

from db_manager import db_manager # NEW: Import DbManager
from db_config import TABLE_NAMES # NEW: Import TABLE_NAMES

logger = VeraLogger("web_search")
print("WebSearcher.py version: 2025-11-10_DDGS_fix")

class WebSearcher:
    def __init__(self):
        self.table_name = TABLE_NAMES["web_cache"]
        self.doc_id = "cache_data"
        self.cache_lock = threading.Lock()
        self.cache = self._load_cache() # Load cache from DB
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/108.0.0.0 Safari/537.36' # More generic User-Agent
        }
        
    def _load_cache(self) -> Dict:
        """Loads cache from DB and handles default if not found."""
        cache_data = db_manager.get_document(self.table_name, self.doc_id, column_name="cache_json")
        if cache_data is None:
            cache_data = {"searches": [], "last_cleanup": datetime.now().isoformat()}
            self._save_cache(cache_data) # Save default if not found
        return cache_data
        
    def _save_cache(self, cache_data: Dict):
        """Saves cache to DB."""
        with self.cache_lock:
            db_manager.insert_document(self.table_name, self.doc_id, cache_data, column_name="cache_json")
                
    def search(self, query: str, force_refresh: bool = False) -> Dict:
        """
        Recherche multi-sources avec cache
        """
        # Vérifier cache d'abord
        if not force_refresh:
            cached = self._check_cache(query)
            if cached:
                return cached
                
        results = {
            "wikipedia": self._search_wikipedia(query),
            # "news": self._search_news(query),
            "general": self._search_ddg(query),
            "timestamp": datetime.now().isoformat()
        }
        
        # Sauvegarder dans cache
        self._add_to_cache(query, results)
        
        return results
        
    def _check_cache(self, query: str) -> Optional[Dict]:
        """
        Vérifier si résultat en cache et pas trop vieux
        """
        self.cache = self._load_cache() # Ensure cache is fresh
        for entry in self.cache.get("searches", []):
            if entry["query"].lower() == query.lower():
                # Vérifier si moins de 24h
                cached_time = datetime.fromisoformat(entry["results"]["timestamp"])
                age = datetime.now() - cached_time
                if age.days < 1:
                    return entry["results"]
        return None
        
    def _add_to_cache(self, query: str, results: Dict):
        self.cache = self._load_cache() # Ensure cache is fresh before modifying
        self.cache["searches"].append({
            "query": query,
            "results": results
        })
        
        # Garder que 100 dernières recherches
        if len(self.cache["searches"]) > 100:
            self.cache["searches"] = self.cache["searches"][-100:]
        
        # Persister le cache
        self._save_cache(self.cache)
        
    def _search_wikipedia(self, query: str, lang: str = 'fr') -> Dict:
        """
        Recherche Wikipedia
        """
        if not WIKIPEDIA_AVAILABLE:
            return {"success": False, "error": "wikipedia module not installed"}

        try:
            wikipedia.set_lang(lang)
            # Chercher pages pertinentes
            search_results = wikipedia.search(query, results=3)
            articles = []
            
            for title in search_results:
                try:
                    page = wikipedia.page(title)
                    articles.append({
                        "title": page.title,
                        "summary": page.summary,
                        "url": page.url
                    })
                except wikipedia.exceptions.DisambiguationError as e:
                    # Prendre première suggestion non ambiguë
                    if e.options:
                        try:
                            page = wikipedia.page(e.options[0])
                            articles.append({
                                "title": page.title,
                                "summary": page.summary,
                                "url": page.url
                            })
                        except:
                            pass
                except Exception as e:
                    print(f"Erreur wiki pour {title}: {e}")
                    
            return {
                "success": True,
                "articles": articles
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }
            
    def _search_news(self, query: str) -> Dict:
        """
        Recherche actualités via NewsAPI
        """
        try:
            # Utiliser une API d'actualités gratuite
            url = "https://newsapi.org/v2/everything"
            params = {
                "q": query,
                "language": "fr",
                "sortBy": "relevancy",
                "pageSize": 5
            }
            if not REQUESTS_AVAILABLE:
                return {"success": False, "error": "requests module not installed"}

            response = requests.get(url, params=params, headers=self.headers)
            if response.status_code == 200:
                data = response.json()
                return {
                    "success": True,
                    "articles": data.get("articles", [])
                }
            else:
                return {
                    "success": False,
                    "error": f"Status code: {response.status_code}"
                }
                
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }
            
    def _search_ddg(self, query: str) -> Dict:
        """
        Recherche DuckDuckGo en utilisant la bibliothèque ddgs, avec filtrage de contenu explicite.
        """
        if not DDGS_AVAILABLE:
            return {"success": False, "error": "ddgs module not installed"}

        try:
            ddgs = DDGS()
            logger.info(f"Tentative de recherche DuckDuckGo pour la requête : '{query}'")
            # Passage en safesearch strict
            results = ddgs.text(query, region='fr-fr', safesearch='strict', max_results=10)
            logger.info(f"Résultats bruts de DuckDuckGo pour '{query}': {results}")
            
            formatted_results = []
            if results:
                for r in results:
                    formatted_results.append({
                        "title": r.get("title"),
                        "snippet": r.get("body"),
                        "url": r.get("href")
                    })
            
            # Filtrer le contenu explicite
            filtered_results = self._filter_explicit_content(formatted_results)
                        
            return {
                "success": True,
                "results": filtered_results
            }
                
        except Exception as e:
            logger.error(f"Erreur lors de la recherche DuckDuckGo avec ddgs pour la requête '{query}': {e}", exc_info=True)
            return {
                "success": False,
                "error": str(e)
            }

    def _filter_explicit_content(self, results: list) -> list:
        """
        Filtre les résultats de recherche qui contiennent des mots-clés ou des indicateurs
        clairement pornographiques dans leur titre, leur description ou leur URL.
        Cette fonction est conçue pour être agressive afin de garantir la sécurité.
        """
        EXPLICIT_KEYWORDS = [
            # Domaines explicites
            "pornhub", "xvideos", "xhamster", "xnxx", "redtube", "youporn", "spankbang",
            # Termes directement liés à la pornographie
            "porno", "porn", "xxx", "hentai", "milf", "gangbang", "threesome",
            "incest", "viol", "rape", "pedophile", "pédophile", "child porn",
            "teen porn", "lolita", "shota", "bestiality", "zoophil",
            # Extensions de domaine courantes pour les sites pornographiques
            ".xxx", ".porn", ".adult",
            # Termes argotiques très spécifiques à la pornographie
            "cumshot", "blowjob", "deepthroat", "fellation", "cunnilingus", "anilingus",
            "golden shower", "watersports", "scat", "bondage", "bdsm", "fetish", "fétichisme",
            "orgie", "orgy", "hardcore", "amateur porn", "gay porn", "lesbian porn",
            "nude pics", "naked pics", "nu photo", "nue photo", "sexe gratuit"
        ]
        
        filtered_results = []
        for r in results:
            is_explicit = False
            # Concaténer toutes les parties textuelles pour une seule vérification
            content_to_check = " ".join(filter(None, [
                r.get("title", "").lower(),
                r.get("snippet", "").lower(),
                r.get("url", "").lower()
            ]))
            
            for keyword in EXPLICIT_KEYWORDS:
                # Logique de détection simple et agressive
                if keyword in content_to_check:
                    is_explicit = True
                    logger.warning(f"Contenu explicite détecté et filtré. Mot-clé: '{keyword}'. URL: {r.get('url')}")
                    break
            
            if not is_explicit:
                filtered_results.append(r)
        return filtered_results

# Instance globale
web_searcher = WebSearcher()