import pandas as pd

from modules.db import obtener_conexion


DESCRIPCIONES_INICIALES = [
    "Ingeniería y programación",
    "Fabricación y montaje",
    "Pruebas y puesta en marcha",
    "Transporte",
]


def obtener_costos_adicionales(cotizacion_id):
    conexion = obtener_conexion()
    try:
        dataframe = pd.read_sql_query(
            """SELECT descripcion, cantidad, costo_unitario, recargo_porcentaje,
            precio_unitario, subtotal FROM costos_adicionales
            WHERE cotizacion_id = ? ORDER BY id""",
            conexion,
            params=(cotizacion_id,),
        )
    finally:
        conexion.close()
    if dataframe.empty:
        return pd.DataFrame({
            "descripcion": DESCRIPCIONES_INICIALES,
            "cantidad": [1.0] * len(DESCRIPCIONES_INICIALES),
            "costo_unitario": [0.0] * len(DESCRIPCIONES_INICIALES),
            "recargo_porcentaje": [0.0] * len(DESCRIPCIONES_INICIALES),
        })
    return dataframe[["descripcion", "cantidad", "costo_unitario", "recargo_porcentaje"]]


def calcular_materiales(cotizacion_id, tipo_cambio):
    conexion = obtener_conexion()
    try:
        detalle = pd.read_sql_query(
            """SELECT c.codigo, c.descripcion, c.moneda, d.cantidad,
            d.precio_unitario, d.cantidad * d.precio_unitario AS subtotal_origen
            FROM detalle_cotizacion d
            JOIN componentes c ON c.id = d.componente_id
            WHERE d.cotizacion_id = ? ORDER BY c.categoria, c.descripcion""",
            conexion,
            params=(cotizacion_id,),
        )
    finally:
        conexion.close()
    if detalle.empty:
        detalle["subtotal_pen"] = pd.Series(dtype=float)
        return detalle
    detalle["tipo_cambio_aplicado"] = detalle["moneda"].map(
        lambda moneda: tipo_cambio if moneda == "USD" else 1.0
    )
    detalle["subtotal_pen"] = (
        detalle["subtotal_origen"] * detalle["tipo_cambio_aplicado"]
    )
    return detalle


def preparar_costos_adicionales(dataframe):
    dataframe = dataframe.copy()
    dataframe["descripcion"] = dataframe["descripcion"].fillna("").astype(str).str.strip()
    for columna in ["cantidad", "costo_unitario", "recargo_porcentaje"]:
        dataframe[columna] = pd.to_numeric(dataframe[columna], errors="coerce").fillna(0)
    dataframe = dataframe[dataframe["descripcion"].ne("")].copy()
    if (dataframe["cantidad"] <= 0).any():
        raise ValueError("La cantidad de los costos adicionales debe ser mayor que cero.")
    if (dataframe[["costo_unitario", "recargo_porcentaje"]] < 0).any().any():
        raise ValueError("Los costos y recargos no pueden ser negativos.")
    dataframe["precio_unitario"] = dataframe["costo_unitario"] * (
        1 + dataframe["recargo_porcentaje"] / 100
    )
    dataframe["subtotal"] = dataframe["cantidad"] * dataframe["precio_unitario"]
    return dataframe


def calcular_resumen(cotizacion_id, tipo_cambio, adicionales, descuento, igv):
    if tipo_cambio <= 0:
        raise ValueError("El tipo de cambio debe ser mayor que cero.")
    if not 0 <= descuento <= 100:
        raise ValueError("El descuento debe encontrarse entre 0 % y 100 %.")
    if not 0 <= igv <= 100:
        raise ValueError("El IGV debe encontrarse entre 0 % y 100 %.")

    materiales = calcular_materiales(cotizacion_id, tipo_cambio)
    adicionales = preparar_costos_adicionales(adicionales)
    subtotal_materiales = float(materiales["subtotal_pen"].sum())
    subtotal_adicionales = float(adicionales["subtotal"].sum())
    subtotal_bruto = subtotal_materiales + subtotal_adicionales
    descuento_monto = subtotal_bruto * descuento / 100
    subtotal_venta = subtotal_bruto - descuento_monto
    igv_monto = subtotal_venta * igv / 100
    total_venta = subtotal_venta + igv_monto
    return {
        "materiales": materiales,
        "adicionales": adicionales,
        "subtotal_materiales": subtotal_materiales,
        "subtotal_adicionales": subtotal_adicionales,
        "subtotal_bruto": subtotal_bruto,
        "descuento_monto": descuento_monto,
        "subtotal_venta": subtotal_venta,
        "igv_monto": igv_monto,
        "total_venta": total_venta,
    }


def guardar_resumen(cotizacion_id, tipo_cambio, descuento, igv, resumen, emitir=False):
    conexion = obtener_conexion()
    try:
        conexion.execute(
            "DELETE FROM costos_adicionales WHERE cotizacion_id = ?", (cotizacion_id,)
        )
        for fila in resumen["adicionales"].itertuples():
            conexion.execute(
                """INSERT INTO costos_adicionales (
                cotizacion_id, descripcion, cantidad, costo_unitario,
                recargo_porcentaje, precio_unitario, subtotal)
                VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (cotizacion_id, fila.descripcion, float(fila.cantidad),
                 float(fila.costo_unitario), float(fila.recargo_porcentaje),
                 float(fila.precio_unitario), float(fila.subtotal)),
            )
        estado = "Emitida" if emitir else "Borrador"
        conexion.execute(
            """UPDATE cotizaciones SET tipo_cambio=?, descuento_porcentaje=?,
            igv_porcentaje=?, subtotal_materiales=?, subtotal_adicionales=?,
            subtotal_venta=?, igv_monto=?, total_venta=?, estado=?,
            fecha_actualizacion=CURRENT_TIMESTAMP WHERE id=?""",
            (tipo_cambio, descuento, igv, resumen["subtotal_materiales"],
             resumen["subtotal_adicionales"], resumen["subtotal_venta"],
             resumen["igv_monto"], resumen["total_venta"], estado, cotizacion_id),
        )
        conexion.commit()
        return {"correcto": True, "estado": estado}
    except Exception as error:
        conexion.rollback()
        return {"correcto": False, "error": str(error)}
    finally:
        conexion.close()


def obtener_parametros_comerciales(cotizacion_id):
    conexion = obtener_conexion()
    try:
        fila = conexion.execute(
            """SELECT tipo_cambio, descuento_porcentaje, igv_porcentaje,
            subtotal_materiales, subtotal_adicionales, subtotal_venta,
            igv_monto, total_venta, estado FROM cotizaciones WHERE id = ?""",
            (cotizacion_id,),
        ).fetchone()
        return dict(fila) if fila else None
    finally:
        conexion.close()

