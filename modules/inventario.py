import pandas as pd

from modules.db import obtener_conexion


COLUMNAS_REQUERIDAS = [
    "codigo", "descripcion", "categoria", "marca", "modelo", "unidad",
    "stock", "stock_minimo", "costo_unitario", "moneda", "proveedor",
    "ubicacion", "estado", "observaciones",
]
MONEDAS_PERMITIDAS = {"PEN", "USD"}
ESTADOS_PERMITIDOS = {"Activo", "Inactivo", "Descontinuado"}


def limpiar_texto(valor):
    return "" if pd.isna(valor) else str(valor).strip()


def leer_archivo_excel(archivo):
    try:
        archivo.seek(0)
        vista_previa = pd.read_excel(
            archivo, sheet_name="Componentes", header=None,
            engine="openpyxl", nrows=20,
        )
        fila_encabezados = None
        for indice, fila in vista_previa.iterrows():
            valores = {limpiar_texto(valor).lower() for valor in fila.tolist()}
            if {"codigo", "descripcion", "categoria"}.issubset(valores):
                fila_encabezados = indice
                break
        if fila_encabezados is None:
            return None, [
                "No se encontró la fila de encabezados con codigo, "
                "descripcion y categoria."
            ]
        archivo.seek(0)
        dataframe = pd.read_excel(
            archivo, sheet_name="Componentes", header=fila_encabezados,
            engine="openpyxl",
        )
        dataframe.columns = [limpiar_texto(c).lower() for c in dataframe.columns]
        return dataframe, []
    except ValueError:
        return None, ["El archivo no contiene una hoja llamada 'Componentes'."]
    except Exception as error:
        return None, [f"No se pudo leer el archivo Excel: {error}"]


def validar_columnas(dataframe):
    faltantes = [c for c in COLUMNAS_REQUERIDAS if c not in dataframe.columns]
    return ["Faltan las siguientes columnas: " + ", ".join(faltantes)] if faltantes else []


def preparar_dataframe(dataframe):
    dataframe = dataframe[COLUMNAS_REQUERIDAS].copy()
    columnas_texto = [
        "codigo", "descripcion", "categoria", "marca", "modelo", "unidad",
        "moneda", "proveedor", "ubicacion", "estado", "observaciones",
    ]
    for columna in columnas_texto:
        dataframe[columna] = dataframe[columna].apply(limpiar_texto)
    dataframe["codigo"] = dataframe["codigo"].str.upper()
    dataframe["moneda"] = dataframe["moneda"].str.upper()
    mapa_estados = {
        "activo": "Activo", "inactivo": "Inactivo",
        "descontinuado": "Descontinuado",
    }
    dataframe["estado"] = (
        dataframe["estado"].str.lower().map(mapa_estados).fillna(dataframe["estado"])
    )
    for columna in ["stock", "stock_minimo", "costo_unitario"]:
        dataframe[columna] = pd.to_numeric(dataframe[columna], errors="coerce")
    dataframe = dataframe[
        dataframe["codigo"].ne("") | dataframe["descripcion"].ne("")
    ].copy()
    return dataframe.reset_index(drop=True)


def validar_datos(dataframe):
    errores = []
    duplicados = dataframe[
        dataframe["codigo"].duplicated(keep=False) & dataframe["codigo"].ne("")
    ]["codigo"].unique()
    errores.extend(f"El código '{codigo}' está duplicado en el archivo." for codigo in duplicados)
    for indice, fila in dataframe.iterrows():
        numero_fila = indice + 5
        for columna, etiqueta in [
            ("codigo", "código"), ("descripcion", "descripción"),
            ("categoria", "categoría"), ("marca", "marca"), ("unidad", "unidad"),
        ]:
            if not fila[columna]:
                errores.append(f"Fila {numero_fila}: {etiqueta} es obligatorio.")
        for columna, etiqueta in [("stock", "stock"), ("stock_minimo", "stock mínimo")]:
            valor = fila[columna]
            if pd.isna(valor):
                errores.append(f"Fila {numero_fila}: {etiqueta} debe ser numérico.")
            elif valor < 0 or not float(valor).is_integer():
                errores.append(f"Fila {numero_fila}: {etiqueta} debe ser un entero no negativo.")
        costo = fila["costo_unitario"]
        if pd.isna(costo) or costo < 0:
            errores.append(f"Fila {numero_fila}: el costo debe ser un número no negativo.")
        if fila["moneda"] not in MONEDAS_PERMITIDAS:
            errores.append(f"Fila {numero_fila}: la moneda debe ser PEN o USD.")
        if fila["estado"] not in ESTADOS_PERMITIDOS:
            errores.append(f"Fila {numero_fila}: el estado no es válido.")
    return errores


def procesar_archivo_excel(archivo):
    dataframe, errores = leer_archivo_excel(archivo)
    if errores:
        return None, errores
    errores = validar_columnas(dataframe)
    if errores:
        return None, errores
    dataframe = preparar_dataframe(dataframe)
    return dataframe, validar_datos(dataframe)


def guardar_componentes(dataframe):
    conexion = obtener_conexion()
    nuevos = actualizados = 0
    try:
        for _, fila in dataframe.iterrows():
            existente = conexion.execute(
                "SELECT id FROM componentes WHERE codigo = ?", (fila["codigo"],)
            ).fetchone()
            datos = (
                fila["descripcion"], fila["categoria"], fila["marca"],
                fila["modelo"], fila["unidad"], int(fila["stock"]),
                int(fila["stock_minimo"]), float(fila["costo_unitario"]),
                fila["moneda"], fila["proveedor"], fila["ubicacion"],
                fila["estado"], fila["observaciones"],
            )
            if existente:
                conexion.execute(
                    """UPDATE componentes SET descripcion=?, categoria=?, marca=?,
                    modelo=?, unidad=?, stock=?, stock_minimo=?, costo_unitario=?,
                    moneda=?, proveedor=?, ubicacion=?, estado=?, observaciones=?,
                    fecha_actualizacion=CURRENT_TIMESTAMP WHERE codigo=?""",
                    datos + (fila["codigo"],),
                )
                actualizados += 1
            else:
                conexion.execute(
                    """INSERT INTO componentes (descripcion, categoria, marca, modelo,
                    unidad, stock, stock_minimo, costo_unitario, moneda, proveedor,
                    ubicacion, estado, observaciones, codigo)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    datos + (fila["codigo"],),
                )
                nuevos += 1
        conexion.commit()
        return {"correcto": True, "nuevos": nuevos, "actualizados": actualizados,
                "total": nuevos + actualizados, "mensaje": "Importación completada correctamente."}
    except Exception as error:
        conexion.rollback()
        return {"correcto": False, "nuevos": 0, "actualizados": 0, "total": 0,
                "mensaje": f"No se pudieron guardar los componentes: {error}"}
    finally:
        conexion.close()


def obtener_componentes():
    conexion = obtener_conexion()
    try:
        return pd.read_sql_query(
            """SELECT id, codigo, descripcion, categoria, marca, modelo, unidad,
            stock, stock_minimo, costo_unitario, moneda, proveedor, ubicacion,
            estado, observaciones FROM componentes ORDER BY categoria, descripcion""",
            conexion,
        )
    finally:
        conexion.close()


def actualizar_inventario(dataframe):
    conexion = obtener_conexion()
    try:
        for _, fila in dataframe.iterrows():
            stock = int(fila["stock"])
            stock_minimo = int(fila["stock_minimo"])
            costo = float(fila["costo_unitario"])
            if stock < 0 or stock_minimo < 0 or costo < 0:
                raise ValueError(f"Los valores de {fila['codigo']} no pueden ser negativos.")
            conexion.execute(
                """UPDATE componentes SET stock=?, stock_minimo=?, costo_unitario=?,
                proveedor=?, ubicacion=?, estado=?, observaciones=?,
                fecha_actualizacion=CURRENT_TIMESTAMP WHERE id=?""",
                (stock, stock_minimo, costo, limpiar_texto(fila["proveedor"]),
                 limpiar_texto(fila["ubicacion"]), fila["estado"],
                 limpiar_texto(fila["observaciones"]), int(fila["id"])),
            )
        conexion.commit()
        return {"correcto": True, "mensaje": f"Se actualizaron {len(dataframe)} componentes."}
    except Exception as error:
        conexion.rollback()
        return {"correcto": False, "mensaje": f"No se pudo actualizar el inventario: {error}"}
    finally:
        conexion.close()

