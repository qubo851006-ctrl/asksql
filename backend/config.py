# -*- coding: utf-8 -*-
import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(override=True)


# MariaDB read-only connection. Keep this user limited to SELECT privileges.
MARIADB_HOST = os.getenv("MARIADB_HOST", "127.0.0.1")
MARIADB_PORT = int(os.getenv("MARIADB_PORT", "3306"))
MARIADB_USER = os.getenv("MARIADB_USER", "ask_readonly")
MARIADB_PASSWORD = os.getenv("MARIADB_PASSWORD", "")
MARIADB_DATABASE = os.getenv("MARIADB_DATABASE", "data_analysis_ibds")


# Dashboard dictionary exported from the restored test database.
DICTIONARY_DIR = Path(
    os.getenv(
        "DICTIONARY_DIR",
        r"C:\Users\shinh\Desktop\db_export_utf8_processed",
    )
)


# Query guardrails.
QUERY_LIMIT = int(os.getenv("QUERY_LIMIT", "100"))
