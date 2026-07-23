import re

import pandas as pd

from modules.db import obtener_conexion


def obtener_cotizacion(cotizacion_id):
    conexion = obtener_conexion()
    try:
        fila = conexion.execute(
            """SELECT c.*, cl.razon_social AS cliente
            FROM cotizaciones c
            JOIN clientes cl ON cl.id = c.cliente_id
            WHERE c.id = ?""",
            (cotizacion_id,),
        ).fetchone()
        return dict(fila) if fila else None
    finally:
        conexion.close()


def generar_requerimientos(cotizacion):
    total = int(cotizacion["cantidad_bombas"])
    tipo_control = cotizacion["tipo_control"]
    requerimientos = [
        {
            "grupo": "Protección general",
            "cantidad": 1,
            "palabras": ["interruptor termomagnetico", "interruptor caja moldeada"],
            "nota": "Protección principal del tablero; verificar poder de corte y corriente total.",
        },
        {
            "grupo": "Protección de motores",
            "cantidad": total,
            "palabras": ["guarda motor", "guardamotor", "rele termico"],
            "nota": "Una protección por motor; confirmar rango con la corriente nominal.",
        },
        {
            "grupo": "Control automático",
            "cantidad": 1,
            "palabras": ["plc", "rele programable", "controlador"],
            "nota": "Control de alternancia, presión, alarmas y secuencia de bombas.",
        },
        {
            "grupo": "Transmisor de presión",
            "cantidad": 1,
            "palabras": ["transmisor de presion", "sensor de presion", "presostato"],
            "nota": f"Señal requerida: {cotizacion['senal_sensor']}.",
        },
        {
            "grupo": "Fuente o transformador de control",
            "cantidad": 1,
            "palabras": ["fuente de alimentacion", "transformador"],
            "nota": "Alimentación para PLC, sensores y elementos de mando.",
        },
        {
            "grupo": "Gabinete",
            "cantidad": 1,
            "palabras": ["gabinete", "tablero"],
            "nota": "Dimensionar después de confirmar equipos, ventilación y reserva física.",
        },
    ]

    if tipo_control == "Un variador por bomba":
        requerimientos.insert(0, {
            "grupo": "Variadores de frecuencia",
            "cantidad": total,
            "palabras": ["variador"],
            "nota": f"Un variador por bomba, {cotizacion['potencia_hp']:g} HP, {cotizacion['tension']} V.",
        })
    elif tipo_control == "Un variador compartido":
        requerimientos.insert(0, {
            "grupo": "Variador de frecuencia",
            "cantidad": 1,
            "palabras": ["variador"],
            "nota": f"Variador compartido, {cotizacion['potencia_hp']:g} HP, {cotizacion['tension']} V.",
        })
        requerimientos.insert(2, {
            "grupo": "Contactores de transferencia",
            "cantidad": total,
            "palabras": ["contactor"],
            "nota": "Transferencia entre motores con enclavamiento eléctrico y mecánico.",
        })
    elif tipo_control == "Arranque directo":
        requerimientos.insert(0, {
            "grupo": "Contactores de potencia",
            "cantidad": total,
            "palabras": ["contactor"],
            "nota": "Un contactor por bomba; seleccionar categoría AC-3.",
        })
    elif tipo_control == "Estrella-triángulo":
        requerimientos.insert(0, {
            "grupo": "Contactores estrella-triángulo",
            "cantidad": total * 3,
            "palabras": ["contactor"],
            "nota": "Tres contactores por motor; validar calibres de línea, estrella y triángulo.",
        })
        requerimientos.insert(1, {
            "grupo": "Temporizadores estrella-triángulo",
            "cantidad": total,
            "palabras": ["temporizador estrella", "temporizador"],
            "nota": "Un temporizador por arrancador estrella-triángulo.",
        })

    return requerimientos


def _normalizar(texto):
    texto = str(texto or "").lower()
    traduccion = str.maketrans("áéíóúüñ", "aeiouun")
    return re.sub(r"\s+", " ", texto.translate(traduccion)).strip()


def buscar_candidatos(requerimiento, cotizacion, limite=8):
    conexion = obtener_conexion()
    try:
        componentes = pd.read_sql_query(
            """SELECT id, codigo, descripcion, categoria, marca, modelo, unidad,
            stock, stock_minimo, costo_unitario, moneda, estado
            FROM componentes WHERE estado = 'Activo'""",
            conexion,
        )
    finally:
        conexion.close()

    if componentes.empty:
        return componentes

    potencia = float(cotizacion["potencia_hp"])
    tension = int(cotizacion["tension"])
    palabras = [_normalizar(p) for p in requerimiento["palabras"]]

    def puntuar(fila):
        texto = _normalizar(
            f"{fila['descripcion']} {fila['categoria']} {fila['marca']} {fila['modelo']}"
        )
        puntaje = 0
        for palabra in palabras:
            if palabra in texto:
                puntaje += 20
            elif all(fragmento in texto for fragmento in palabra.split()):
                puntaje += 12
        if "variador" in " ".join(palabras):
            formatos_hp = [f"{potencia:g}hp", f"{potencia:g} hp"]
            if any(formato in texto for formato in formatos_hp):
                puntaje += 10
            if str(tension) in texto:
                puntaje += 5
        if fila["stock"] >= requerimiento["cantidad"]:
            puntaje += 4
        elif fila["stock"] > 0:
            puntaje += 1
        return puntaje

    componentes["puntaje"] = componentes.apply(puntuar, axis=1)
    candidatos = componentes[componentes["puntaje"] > 0].copy()
    return candidatos.sort_values(
        ["puntaje", "stock", "descripcion"], ascending=[False, False, True]
    ).head(limite).reset_index(drop=True)


def guardar_seleccion(cotizacion_id, selecciones):
    conexion = obtener_conexion()
    try:
        conexion.execute(
            "DELETE FROM detalle_cotizacion WHERE cotizacion_id = ?", (cotizacion_id,)
        )
        consolidados = {}
        for seleccion in selecciones:
            componente_id = int(seleccion["componente_id"])
            if componente_id not in consolidados:
                consolidados[componente_id] = seleccion.copy()
            else:
                consolidados[componente_id]["cantidad"] += seleccion["cantidad"]

        for seleccion in consolidados.values():
            cantidad = float(seleccion["cantidad"])
            costo = float(seleccion["costo_unitario"])
            margen = float(seleccion["margen"])
            precio = costo * (1 + margen / 100)
            conexion.execute(
                """INSERT INTO detalle_cotizacion (
                cotizacion_id, componente_id, cantidad, costo_unitario,
                margen, precio_unitario, observaciones)
                VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (cotizacion_id, seleccion["componente_id"], cantidad, costo,
                 margen, precio, seleccion.get("observaciones", "")),
            )
        conexion.commit()
        return {"correcto": True, "items": len(consolidados)}
    except Exception as error:
        conexion.rollback()
        return {"correcto": False, "error": str(error)}
    finally:
        conexion.close()


def obtener_detalle_cotizacion(cotizacion_id):
    conexion = obtener_conexion()
    try:
        return pd.read_sql_query(
            """SELECT d.id, c.codigo, c.descripcion, c.marca, d.cantidad,
            c.stock, d.costo_unitario, d.margen, d.precio_unitario,
            d.cantidad * d.precio_unitario AS subtotal, c.moneda,
            d.observaciones
            FROM detalle_cotizacion d
            JOIN componentes c ON c.id = d.componente_id
            WHERE d.cotizacion_id = ? ORDER BY c.categoria, c.descripcion""",
            conexion,
            params=(cotizacion_id,),
        )
    finally:
        conexion.close()

