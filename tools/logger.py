import logging
from pathlib import Path
import json
from datetime import datetime
from typing import Optional, Dict, Any
import sys
import threading

# --- Global Lock for Logging Setup ---
_logging_setup_lock = threading.Lock()
_logging_setup_done = False
_file_handlers = {} # New: To keep track of named file handlers

class CustomFormatter(logging.Formatter):
    """Formateur personnalisé avec couleurs pour la console"""
    
    COLORS = {
        'DEBUG': '\033[0;36m',    # Cyan
        'INFO': '\033[0;32m',     # Vert
        'WARNING': '\033[0;33m',  # Jaune
        'ERROR': '\033[0;31m',    # Rouge
        'CRITICAL': '\033[0;35m', # Magenta
        'RESET': '\033[0m'        # Reset
    }
    
    def format(self, record):
        if record.levelname in self.COLORS:
            record.levelname_colored = f"{self.COLORS[record.levelname]}{record.levelname}{self.COLORS['RESET']}"
        else:
            record.levelname_colored = record.levelname
        return super().format(record)

class JsonFileHandler(logging.Handler):
    """Handler pour sauvegarder les logs au format JSON Lines (.jsonl)"""
    
    def __init__(self, filename: Path):
        super().__init__()
        self.filename = filename.with_suffix('.jsonl')
        self.lock = threading.RLock() # Use a Re-entrant Lock
        
    def emit(self, record):
        try:
            log_entry = self._format_record(record)
            with self.lock:
                with open(self.filename, 'a', encoding='utf-8') as f:
                    f.write(json.dumps(log_entry, ensure_ascii=False) + '\n')
        except Exception:
            self.handleError(record)

    def _format_record(self, record) -> Dict:
        log_entry = {
            'timestamp': datetime.now().isoformat(),
            'level': record.levelname,
            'message': record.getMessage(),
            'module': record.module,
            'function': record.funcName,
            'line': record.lineno
        }
        if hasattr(record, 'extra_data'):
            log_entry.update(record.extra_data)
        return log_entry

    def flush(self):
        pass

class VeraLogger:
    """Gestionnaire de logging centralisé pour Vera"""
    
    def __init__(self, name: str = "vera"):
        setup_logging() # Ensure root logger is set up
        self.logger = logging.getLogger(name)
        self.logger.setLevel(logging.DEBUG) # Set level for this specific logger

        # Add file handlers for this named logger if they don't already exist
        with _logging_setup_lock:
            if name not in _file_handlers:
                log_dir = Path(__file__).parent.parent / "logs"
                log_dir.mkdir(exist_ok=True)

                # Specific .log file for this module
                module_log_file = log_dir / f"{name}_{datetime.now().strftime('%Y%m%d')}.log"
                file_handler = logging.FileHandler(module_log_file, encoding='utf-8')
                file_handler.setLevel(logging.DEBUG)
                file_formatter = logging.Formatter(
                    '%(asctime)s [%(levelname)s] %(name)s:%(lineno)d: %(message)s',
                    datefmt='%Y-%m-%d %H:%M:%S'
                )
                file_handler.setFormatter(file_formatter)
                self.logger.addHandler(file_handler)
                _file_handlers[name] = [file_handler] # Store handler

                # Specific .jsonl file for this module
                module_json_file = log_dir / f"{name}_{datetime.now().strftime('%Y%m%d')}.jsonl"
                json_handler = JsonFileHandler(module_json_file)
                json_handler.setLevel(logging.DEBUG)
                self.logger.addHandler(json_handler)
                _file_handlers[name].append(json_handler) # Add to stored handlers
            else:
                # If handlers already exist for this name, ensure they are attached
                # This handles cases where getLogger(name) is called multiple times
                for handler in _file_handlers[name]:
                    if handler not in self.logger.handlers:
                        self.logger.addHandler(handler)
        
    def debug(self, msg: str, **kwargs):
        exc_info = kwargs.pop('exc_info', False)
        self.logger.debug(msg, exc_info=exc_info, extra=self._prepare_extra(kwargs))
        
    def info(self, msg: str, **kwargs):
        exc_info = kwargs.pop('exc_info', False)
        self.logger.info(msg, exc_info=exc_info, extra=self._prepare_extra(kwargs))
        
    def warning(self, msg: str, **kwargs):
        exc_info = kwargs.pop('exc_info', False)
        self.logger.warning(msg, exc_info=exc_info, extra=self._prepare_extra(kwargs))
        
    def error(self, msg: str, **kwargs):
        exc_info = kwargs.pop('exc_info', True)
        self.logger.error(msg, exc_info=exc_info, extra=self._prepare_extra(kwargs))
        
    def critical(self, msg: str, **kwargs):
        exc_info = kwargs.pop('exc_info', True)
        self.logger.critical(msg, exc_info=exc_info, extra=self._prepare_extra(kwargs))
        
    def _prepare_extra(self, kwargs: Dict[str, Any]) -> Dict[str, Any]:
        extra = {
            'timestamp': datetime.now().isoformat(),
            'data': kwargs
        }
        return {'extra_data': extra}

def setup_logging():
    """Configure les handlers sur le root logger (uniquement console), une seule fois."""
    global _logging_setup_done
    with _logging_setup_lock:
        if _logging_setup_done:
            return

        root_logger = logging.getLogger()
        # Remove all existing handlers to prevent duplicates
        if root_logger.hasHandlers():
            root_logger.handlers.clear()

        root_logger.setLevel(logging.DEBUG)
        
        # Handler console (reste sur le root logger)
        console = logging.StreamHandler(sys.stdout)
        console.setLevel(logging.DEBUG)
        try:
            sys.stdout.reconfigure(encoding='utf-8')
        except TypeError:
            pass
        color_formatter = CustomFormatter(
            '%(asctime)s [%(levelname_colored)s] %(name)s: %(message)s',
            datefmt='%H:%M:%S'
        )
        console.setFormatter(color_formatter)
        root_logger.addHandler(console)
        
        _logging_setup_done = True

# Exemple d'utilisation
if __name__ == "__main__":
    setup_logging() # Setup once
    logger1 = VeraLogger("test1")
    logger2 = VeraLogger("test2")
    
    logger1.info("Test info from logger1", user="test_user")
    logger2.error("Test error from logger2", error_code=500)
