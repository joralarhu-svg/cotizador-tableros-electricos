import os
import sqlite3
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent.parent
DATABASE_DIR = BASE_DIR / "database"
DEFAULT_DATABASE_PATH = DATABASE_DIR / "cotizador.db"


def obtener_ruta_base_datos():
    ruta_configurada = os.getenv("COTIZADOR_DB_PATH")
    return Path(ruta_configurada) if ruta_configurada else DEFAULT_DATABASE_PATH


def obtener_conexion():
    ruta = obtener_ruta_base_datos()
    ruta.parent.mkdir(parents=True, exist_ok=True)
    conexion = sqlite3.connect(ruta)
    conexion.row_factory = sqlite3.Row
    conexion.execute("PRAGMA foreign_keys = ON")
    return conexion

