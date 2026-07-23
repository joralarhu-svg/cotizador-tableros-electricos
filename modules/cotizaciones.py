from datetime import datetime

import pandas as pd

from modules.db import obtener_conexion


TIPOS_TABLERO = ("Presión constante", "Alternador", "Contraincendio")


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
    tipo_tablero = datos.get("tipo_tablero", "Presión constante")
    if tipo_tablero not in TIPOS_TABLERO:
        errores.append("El tipo de tablero seleccionado no es válido.")
    if datos["cantidad_bombas"] < 1:
        errores.append("La cantidad de bombas debe ser mayor que cero.")
    if datos["potencia_hp"] <= 0 or datos["corriente_motor"] <= 0:
        errores.append("La potencia y la corriente del motor deben ser mayores que cero.")
    if tipo_tablero == "Contraincendio":
        if (
            datos.get("potencia_jockey_hp", 0) <= 0
            or datos.get("corriente_jockey", 0) <= 0
        ):
            errores.append(
                "La potencia y la corriente de la bomba jockey deben ser mayores que cero."
            )
        if datos.get("tipo_control") not in ("Estrella-triángulo", "Softstarter"):
            errores.append(
                "El tablero contraincendio solo admite control "
                "Estrella-triángulo o Softstarter."
            )
        if (
            datos.get("tension") in (380, 440)
            and datos.get("tipo_control") != "Softstarter"
        ):
            errores.append(
                "Los tableros contraincendio de 380 V o 440 V "
                "deben utilizar Softstarter."
            )
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
            numero, cliente_id, proyecto, tipo_tablero, cantidad_bombas, bombas_operacion,
            bombas_reserva, potencia_hp, corriente_motor, potencia_jockey_hp,
            corriente_jockey, tension, fases,
            tipo_control, presion_trabajo, unidad_presion, con_alarma,
            observaciones, altitud_msnm, estado)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                    'Borrador')""",
            (numero, cliente_id, datos["proyecto"].strip(),
             datos.get("tipo_tablero", "Presión constante"), datos["cantidad_bombas"],
             datos["cantidad_bombas"], 0, datos["potencia_hp"],
             datos["corriente_motor"], datos.get("potencia_jockey_hp", 0),
             datos.get("corriente_jockey", 0), datos["tension"], datos["fases"],
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
            c.tipo_tablero,
            c.cantidad_bombas, c.potencia_hp, c.corriente_motor,
            c.potencia_jockey_hp, c.corriente_jockey,
            c.altitud_msnm, c.tension, c.tipo_control,
            c.presion_trabajo, c.unidad_presion, c.con_alarma,
            c.estado, c.fecha_creacion
            FROM cotizaciones c JOIN clientes cl ON cl.id = c.cliente_id
            ORDER BY c.id DESC""",
            conexion,
        )
    finally:
        conexion.close()


def eliminar_cotizaciones(cotizacion_ids):
    ids = sorted({int(cotizacion_id) for cotizacion_id in cotizacion_ids})
    if not ids:
        return {
            "correcto": False,
            "eliminadas": 0,
            "errores": ["Seleccione al menos una cotización para eliminar."],
        }

    conexion = obtener_conexion()
    try:
        marcadores = ",".join("?" for _ in ids)
        existentes = conexion.execute(
            f"SELECT COUNT(*) AS total FROM cotizaciones WHERE id IN ({marcadores})",
            ids,
        ).fetchone()["total"]
        if existentes != len(ids):
            conexion.rollback()
            return {
                "correcto": False,
                "eliminadas": 0,
                "errores": [
                    "Una o más cotizaciones seleccionadas ya no existen. "
                    "Actualice la página e inténtelo nuevamente."
                ],
            }

        conexion.execute(
            f"DELETE FROM cotizaciones WHERE id IN ({marcadores})",
            ids,
        )
        conexion.commit()
        return {"correcto": True, "eliminadas": len(ids), "errores": []}
    except Exception as error:
        conexion.rollback()
        return {"correcto": False, "eliminadas": 0, "errores": [str(error)]}
    finally:
        conexion.close()
