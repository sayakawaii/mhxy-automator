# filepath: f:\Documents\Project\Python\mhxy\src\config\settings.py

BOT_SETTINGS = {
    "window_title": "梦幻西游",
    "max_retries": 5,
    "retry_delay": 2,  # seconds
    "action_timeout": 10,  # seconds
    "log_level": "INFO",
    "image_capture_path": "captures/",
    "text_recognition_enabled": True,
    "navigation_speed": "normal",  # options: slow, normal, fast
}

DATABASE_SETTINGS = {
    "db_path": "database/mhxy_bot.db",
    "backup_interval": 3600,  # seconds
}

PLUGIN_SETTINGS = {
    "enabled_plugins": [],
    "plugin_directory": "plugins/",
}