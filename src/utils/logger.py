import logging
import sys

_FORMATTER = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')

# Track which file paths already have a handler attached so add_file_handler is idempotent.
_FILE_HANDLER_PATHS = set()


def add_file_handler(path, level=logging.INFO):
    """Attach a single UTF-8 FileHandler to the root logger (idempotent).

    All module loggers propagate to root, so this captures every log line into a
    clean UTF-8 file regardless of the console/PowerShell encoding. Returns the
    handler (existing or newly created).
    """
    try:
        norm = path
        if norm in _FILE_HANDLER_PATHS:
            for h in logging.getLogger().handlers:
                if isinstance(h, logging.FileHandler) and getattr(h, "_mhxy_path", None) == norm:
                    return h
        handler = logging.FileHandler(path, encoding="utf-8")
        handler.setLevel(level)
        handler.setFormatter(_FORMATTER)
        handler._mhxy_path = norm
        logging.getLogger().addHandler(handler)
        logging.getLogger().setLevel(min(logging.getLogger().level or level, level))
        _FILE_HANDLER_PATHS.add(norm)
        return handler
    except Exception:
        # Never let logging setup crash the application.
        return None


class Logger:
    """
    Thin wrapper around logging to provide a simple per-module logger.
    Ensures multiple imports don't add duplicate handlers.

    Console output goes to stdout (NOT stderr) so that shells like PowerShell do
    not misinterpret normal log lines as command errors (NativeCommandError).
    """
    def __init__(self, name, level=logging.INFO):
        self.logger = logging.getLogger(name)
        self.logger.setLevel(level)
        # avoid adding multiple handlers when re-instantiating Logger for same name
        if not self.logger.handlers:
            handler = logging.StreamHandler(stream=sys.stdout)
            handler.setFormatter(_FORMATTER)
            self.logger.addHandler(handler)

    def debug(self, message):
        self.logger.debug(message)

    def info(self, message):
        self.logger.info(message)

    def warning(self, message):
        self.logger.warning(message)

    def error(self, message):
        self.logger.error(message)

    def critical(self, message):
        self.logger.critical(message)

# Example usage:
# logger = Logger(__name__)
# logger.info("This is an info message.")