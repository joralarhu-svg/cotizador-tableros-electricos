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
    if datos["cantidad_bombas"] < 1:
        errores.append("La cantidad de bombas debe ser mayor que cero.")
    if datos["potencia_hp"] <= 0 or datos["corriente_motor"] <= 0:
        errores.append("La potencia y la corriente del motor deben ser mayores que cero.")
    if datos.get("altitud_msnm", 0) < 0:
        errores.append("La altitud de operación no puede ser negativa.")
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
            tipo_control, presion_trabajo, unidad_presion, con_alarma,
            observaciones, altitud_msnm, estado)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'Borrador')""",
            (numero, cliente_id, datos["proyecto"].strip(), datos["cantidad_bombas"],
             datos["cantidad_bombas"], 0, datos["potencia_hp"],
             datos["corriente_motor"], datos["tension"], datos["fases"],
             datos["tipo_control"], datos["presion_trabajo"], datos["unidad_presion"],
             int(bool(datos.get("con_alarma", False))),
             datos.get("observaciones", "").strip(),
             datos.get("altitud_msnm", 0)),
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
            c.cantidad_bombas, c.potencia_hp, c.corriente_motor,
            c.altitud_msnm, c.tension, c.tipo_control,
            c.presion_trabajo, c.unidad_presion, c.con_alarma,
            c.estado, c.fecha_creacion
            FROM cotizaciones c JOIN clientes cl ON cl.id = c.cliente_id
            ORDER BY c.id DESC""",
            conexion,
        )
    finally:
        conexion.close()
