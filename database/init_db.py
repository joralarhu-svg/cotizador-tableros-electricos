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


def crear_tablas_cotizaciones():
    conexion = obtener_conexion()
    try:
        conexion.executescript(
            """
            CREATE TABLE IF NOT EXISTS clientes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                tipo_documento TEXT NOT NULL DEFAULT 'RUC'
                    CHECK (tipo_documento IN ('RUC', 'DNI', 'CE', 'Otro')),
                numero_documento TEXT UNIQUE,
                razon_social TEXT NOT NULL,
                contacto TEXT,
                telefono TEXT,
                correo TEXT,
                direccion TEXT,
                fecha_creacion TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS cotizaciones (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                numero TEXT NOT NULL UNIQUE,
                cliente_id INTEGER NOT NULL,
                proyecto TEXT NOT NULL,
                cantidad_bombas INTEGER NOT NULL CHECK (cantidad_bombas >= 1),
                bombas_operacion INTEGER NOT NULL CHECK (bombas_operacion >= 1),
                bombas_reserva INTEGER NOT NULL DEFAULT 0 CHECK (bombas_reserva >= 0),
                potencia_hp REAL NOT NULL CHECK (potencia_hp > 0),
                corriente_motor REAL NOT NULL CHECK (corriente_motor > 0),
                tension INTEGER NOT NULL CHECK (tension IN (220, 380, 440)),
                fases INTEGER NOT NULL DEFAULT 3 CHECK (fases IN (1, 3)),
                tipo_control TEXT NOT NULL,
                presion_trabajo REAL NOT NULL CHECK (presion_trabajo > 0),
                unidad_presion TEXT NOT NULL DEFAULT 'bar'
                    CHECK (unidad_presion IN ('bar', 'psi', 'mca')),
                senal_sensor TEXT NOT NULL DEFAULT '4-20 mA',
                observaciones TEXT,
                estado TEXT NOT NULL DEFAULT 'Borrador'
                    CHECK (estado IN ('Borrador', 'Emitida', 'Aprobada', 'Rechazada')),
                fecha_creacion TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                fecha_actualizacion TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (cliente_id) REFERENCES clientes(id)
            );

            CREATE TABLE IF NOT EXISTS detalle_cotizacion (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                cotizacion_id INTEGER NOT NULL,
                componente_id INTEGER NOT NULL,
                cantidad REAL NOT NULL CHECK (cantidad > 0),
                costo_unitario REAL NOT NULL CHECK (costo_unitario >= 0),
                margen REAL NOT NULL DEFAULT 0 CHECK (margen >= 0),
                precio_unitario REAL NOT NULL CHECK (precio_unitario >= 0),
                observaciones TEXT,
                FOREIGN KEY (cotizacion_id) REFERENCES cotizaciones(id) ON DELETE CASCADE,
                FOREIGN KEY (componente_id) REFERENCES componentes(id),
                UNIQUE (cotizacion_id, componente_id)
            );
            """
        )
        conexion.commit()
    finally:
        conexion.close()


def crear_estructura_comercial():
    conexion = obtener_conexion()
    try:
        columnas = {
            fila["name"] for fila in conexion.execute("PRAGMA table_info(cotizaciones)")
        }
        nuevas_columnas = {
            "altitud_msnm": "REAL NOT NULL DEFAULT 0",
            "tipo_cambio": "REAL NOT NULL DEFAULT 3.50",
            "descuento_porcentaje": "REAL NOT NULL DEFAULT 0",
            "igv_porcentaje": "REAL NOT NULL DEFAULT 18",
            "subtotal_materiales": "REAL NOT NULL DEFAULT 0",
            "subtotal_adicionales": "REAL NOT NULL DEFAULT 0",
            "subtotal_venta": "REAL NOT NULL DEFAULT 0",
            "igv_monto": "REAL NOT NULL DEFAULT 0",
            "total_venta": "REAL NOT NULL DEFAULT 0",
            "vigencia_dias": "INTEGER NOT NULL DEFAULT 15",
            "plazo_entrega": "TEXT NOT NULL DEFAULT 'Por coordinar'",
            "garantia": "TEXT NOT NULL DEFAULT '12 meses'",
            "forma_pago": "TEXT NOT NULL DEFAULT '50% de adelanto y 50% contra entrega'",
            "condiciones_adicionales": "TEXT",
        }
        for nombre, definicion in nuevas_columnas.items():
            if nombre not in columnas:
                conexion.execute(
                    f"ALTER TABLE cotizaciones ADD COLUMN {nombre} {definicion}"
                )

        # Las cotizaciones nuevas y existentes consideran todas las bombas
        # disponibles para operación, con alternancia definida por el control.
        conexion.execute(
            """UPDATE cotizaciones SET bombas_operacion = cantidad_bombas,
            bombas_reserva = 0
            WHERE bombas_operacion <> cantidad_bombas OR bombas_reserva <> 0"""
        )

        conexion.execute(
            """
            CREATE TABLE IF NOT EXISTS costos_adicionales (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                cotizacion_id INTEGER NOT NULL,
                descripcion TEXT NOT NULL,
                cantidad REAL NOT NULL DEFAULT 1 CHECK (cantidad > 0),
                costo_unitario REAL NOT NULL DEFAULT 0 CHECK (costo_unitario >= 0),
                recargo_porcentaje REAL NOT NULL DEFAULT 0 CHECK (recargo_porcentaje >= 0),
                precio_unitario REAL NOT NULL DEFAULT 0 CHECK (precio_unitario >= 0),
                subtotal REAL NOT NULL DEFAULT 0 CHECK (subtotal >= 0),
                FOREIGN KEY (cotizacion_id) REFERENCES cotizaciones(id) ON DELETE CASCADE
            )
            """
        )
        conexion.execute(
            """
            CREATE TABLE IF NOT EXISTS configuracion_empresa (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                razon_social TEXT NOT NULL DEFAULT 'MI EMPRESA',
                ruc TEXT,
                direccion TEXT,
                telefono TEXT,
                correo TEXT,
                sitio_web TEXT
            )
            """
        )
        conexion.execute(
            """INSERT OR IGNORE INTO configuracion_empresa
            (id, razon_social, ruc, direccion, telefono, correo, sitio_web)
            VALUES (1, 'MI EMPRESA', '', '', '', '', '')"""
        )
        conexion.commit()
    finally:
        conexion.close()


def inicializar_base_datos():
    crear_tabla_componentes()
    crear_tablas_cotizaciones()
    crear_estructura_comercial()


if __name__ == "__main__":
    inicializar_base_datos()
    print("Base de datos inicializada correctamente.")
