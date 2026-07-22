from modules.db import obtener_conexion


def crear_tabla_componentes():
    conexion = obtener_conexion()
    try:
        conexion.execute(
            """
            CREATE TABLE IF NOT EXISTS componentes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                codigo TEXT NOT NULL UNIQUE,
                descripcion TEXT NOT NULL,
                categoria TEXT NOT NULL,
                marca TEXT NOT NULL,
                modelo TEXT,
                unidad TEXT NOT NULL DEFAULT 'und',
                stock INTEGER NOT NULL DEFAULT 0 CHECK (stock >= 0),
                stock_minimo INTEGER NOT NULL DEFAULT 0 CHECK (stock_minimo >= 0),
                costo_unitario REAL NOT NULL DEFAULT 0 CHECK (costo_unitario >= 0),
                moneda TEXT NOT NULL DEFAULT 'PEN' CHECK (moneda IN ('PEN', 'USD')),
                proveedor TEXT,
                ubicacion TEXT,
                estado TEXT NOT NULL DEFAULT 'Activo'
                    CHECK (estado IN ('Activo', 'Inactivo', 'Descontinuado')),
                observaciones TEXT,
                fecha_creacion TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                fecha_actualizacion TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        conexion.commit()
    finally:
        conexion.close()


def inicializar_base_datos():
    crear_tabla_componentes()


if __name__ == "__main__":
    inicializar_base_datos()
    print("Base de datos inicializada correctamente.")

