from datetime import datetime

import pandas as pd

from modules.db import obtener_conexion


def obtener_clientes():
    conexion = obtener_conexion()
    try:
        return pd.read_sql_query(
            """SELECT id, tipo_documento, numero_documento, razon_social,
            contacto, telefono, correo, direccion
            FROM clientes ORDER BY razon_social""",
            conexion,
        )
    finally:
        conexion.close()


def registrar_cliente(datos):
    conexion = obtener_conexion()
    try:
        documento = datos.get("numero_documento", "").strip() or None
        if documento:
            existente = conexion.execute(
                "SELECT id FROM clientes WHERE numero_documento = ?", (documento,)
            ).fetchone()
            if existente:
                conexion.execute(
                    """UPDATE clientes SET tipo_documento=?, razon_social=?, contacto=?,
                    telefono=?, correo=?, direccion=? WHERE id=?""",
                    (datos["tipo_documento"], datos["razon_social"].strip(),
                     datos.get("contacto", "").strip(), datos.get("telefono", "").strip(),
                     datos.get("correo", "").strip(), datos.get("direccion", "").strip(),
                     existente["id"]),
                )
                conexion.commit()
                return existente["id"]
        cursor = conexion.execute(
            """INSERT INTO clientes (tipo_documento, numero_documento, razon_social,
            contacto, telefono, correo, direccion) VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (datos["tipo_documento"], documento, datos["razon_social"].strip(),
             datos.get("contacto", "").strip(), datos.get("telefono", "").strip(),
             datos.get("correo", "").strip(), datos.get("direccion", "").strip()),
        )
        conexion.commit()
        return cursor.lastrowid
    except Exception:
        conexion.rollback()
        raise
    finally:
        conexion.close()


def generar_numero_cotizacion(conexion):
    anio = datetime.now().year
    prefijo = f"COT-{anio}-"
    fila = conexion.execute(
        "SELECT numero FROM cotizaciones WHERE numero LIKE ? ORDER BY id DESC LIMIT 1",
        (f"{prefijo}%",),
    ).fetchone()
    correlativo = int(fila["numero"].split("-")[-1]) + 1 if fila else 1
    return f"{prefijo}{correlativo:04d}"


def validar_datos_tecnicos(datos):
    errores = []
    if datos["bombas_operacion"] + datos["bombas_reserva"] != datos["cantidad_bombas"]:
        errores.append(
            "La suma de bombas en operación y reserva debe ser igual al total de bombas."
        )
    if datos["potencia_hp"] <= 0 or datos["corriente_motor"] <= 0:
        errores.append("La potencia y la corriente del motor deben ser mayores que cero.")
    if datos["presion_trabajo"] <= 0:
        errores.append("La presión de trabajo debe ser mayor que cero.")
    return errores


def registrar_cotizacion(cliente_id, datos):
    errores = validar_datos_tecnicos(datos)
    if errores:
        return {"correcto": False, "errores": errores}
    conexion = obtener_conexion()
    try:
        numero = generar_numero_cotizacion(conexion)
        cursor = conexion.execute(
            """INSERT INTO cotizaciones (
            numero, cliente_id, proyecto, cantidad_bombas, bombas_operacion,
            bombas_reserva, potencia_hp, corriente_motor, tension, fases,
            tipo_control, presion_trabajo, unidad_presion, senal_sensor,
            observaciones, estado) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'Borrador')""",
            (numero, cliente_id, datos["proyecto"].strip(), datos["cantidad_bombas"],
             datos["bombas_operacion"], datos["bombas_reserva"], datos["potencia_hp"],
             datos["corriente_motor"], datos["tension"], datos["fases"],
             datos["tipo_control"], datos["presion_trabajo"], datos["unidad_presion"],
             datos["senal_sensor"], datos.get("observaciones", "").strip()),
        )
        conexion.commit()
        return {"correcto": True, "id": cursor.lastrowid, "numero": numero, "errores": []}
    except Exception as error:
        conexion.rollback()
        return {"correcto": False, "errores": [str(error)]}
    finally:
        conexion.close()


def obtener_cotizaciones():
    conexion = obtener_conexion()
    try:
        return pd.read_sql_query(
            """SELECT c.id, c.numero, cl.razon_social AS cliente, c.proyecto,
            c.cantidad_bombas, c.potencia_hp, c.tension, c.tipo_control,
            c.presion_trabajo, c.unidad_presion, c.estado, c.fecha_creacion
            FROM cotizaciones c JOIN clientes cl ON cl.id = c.cliente_id
            ORDER BY c.id DESC""",
            conexion,
        )
    finally:
        conexion.close()

