import re

import pandas as pd

from modules.db import obtener_conexion


def calcular_factor_derrateo(altitud_msnm):
    altitud = max(0.0, float(altitud_msnm or 0))
    exceso = max(0.0, altitud - 1000.0)
    return 1.0 + (exceso / 100.0) * 0.01


def calcular_corriente_corregida(corriente_motor, altitud_msnm):
    return float(corriente_motor) * calcular_factor_derrateo(altitud_msnm)


def extraer_rango_corriente(texto):
    texto = _normalizar(texto).replace(",", ".")
    rango = re.search(
        r"(\d+(?:\.\d+)?)\s*(?:-|a|hasta)\s*(\d+(?:\.\d+)?)\s*a\b",
        texto,
    )
    if rango:
        minimo, maximo = float(rango.group(1)), float(rango.group(2))
        return (min(minimo, maximo), max(minimo, maximo))
    valores = re.findall(
        r"(\d+(?:\.\d+)?)\s*(?:amp|amperios?)\b",
        texto,
    )
    valores.extend(re.findall(
        r"(\d+(?:\.\d+)?)\s*a\b"
        r"(?!\s+\d+(?:\.\d+)?\s*v(?:ac)?\b)",
        texto,
    ))
    if valores:
        capacidad = max(float(valor) for valor in valores)
        return (capacidad, capacidad)
    return None


def extraer_rangos_tension(texto):
    texto = _normalizar(texto).replace(",", ".")
    rangos = []
    for minimo, maximo in re.findall(
        r"(\d+(?:\.\d+)?)(?:\s*-\s*|\s+(?:a|hasta)\s+)"
        r"(\d+(?:\.\d+)?)\s*v(?:ac)?\b",
        texto,
    ):
        valores = sorted((float(minimo), float(maximo)))
        rangos.append((valores[0], valores[1]))
    for valor in re.findall(r"(\d+(?:\.\d+)?)\s*v(?:ac)?\b", texto):
        tension = float(valor)
        rangos.append((tension, tension))
    return rangos


def admite_tension(texto, tension_requerida):
    return any(
        minimo <= float(tension_requerida) <= maximo
        for minimo, maximo in extraer_rangos_tension(texto)
    )


def es_variador_frecuencia(fila):
    descripcion = _normalizar(fila["descripcion"])
    categoria = _normalizar(fila["categoria"])
    texto = f"{descripcion} {categoria}"
    excluidos = [
        "contactor", "arrancador suave", "soft starter",
        "guardamotor", "guarda motor", "rele termico",
    ]
    return (
        ("variador" in descripcion or "variador" in categoria)
        and not any(excluido in texto for excluido in excluidos)
    )


def clasificar_proteccion_circuito_derivado(fila):
    texto = _normalizar(
        f"{fila['descripcion']} {fila['categoria']} {fila['modelo']}"
    )
    tipos_excluidos = [
        "contactor",
        "arrancador suave",
        "soft starter",
        "variador",
        "rele termico",
    ]
    if any(tipo in texto for tipo in tipos_excluidos):
        return None
    if "guardamotor" in texto or "guarda motor" in texto:
        return "Guardamotor"
    tipos_interruptor = [
        "interruptor termomagnetico",
        "interruptor magnetotermico",
        "interruptor automatico",
        "interruptor caja moldeada",
        "disyuntor",
        "breaker",
        "mcb",
        "mccb",
    ]
    if any(tipo in texto for tipo in tipos_interruptor):
        return "Interruptor termomagnético"
    return None


def es_proteccion_circuito_derivado(fila):
    return clasificar_proteccion_circuito_derivado(fila) is not None


def extraer_numero_polos(texto):
    texto = _normalizar(texto)
    coincidencia = re.search(r"\b([1-4])\s*p\b", texto)
    if coincidencia:
        return int(coincidencia.group(1))
    nombres = {
        "monopolar": 1,
        "un polo": 1,
        "bipolar": 2,
        "dos polos": 2,
        "tripolar": 3,
        "tres polos": 3,
        "tetrapolar": 4,
        "cuatro polos": 4,
    }
    for nombre, polos in nombres.items():
        if nombre in texto:
            return polos
    return None


def cumple_polos_circuito_derivado(fila, polos_requeridos):
    tipo = clasificar_proteccion_circuito_derivado(fila)
    if tipo == "Guardamotor":
        return True
    if tipo != "Interruptor termomagnético":
        return False
    polos = extraer_numero_polos(
        f"{fila['descripcion']} {fila['categoria']} {fila['modelo']}"
    )
    return polos == int(polos_requeridos)


def es_accesorio_puerta(fila, subtipo, color=None):
    texto = _normalizar(
        f"{fila['descripcion']} {fila['categoria']} {fila['modelo']}"
    )
    if subtipo == "conmutador":
        return (
            "conmutador" in texto or "selector" in texto
        ) and not any(
            excluido in texto
            for excluido in ["accesorio", "contacto auxiliar", "bloque de contacto"]
        )
    if subtipo != "piloto":
        return False
    es_piloto_completo = (
        "piloto de senalizacion" in texto
        or "piloto senalizacion" in texto
        or "luz piloto" in texto
    )
    if not es_piloto_completo:
        return False
    colores = {
        "verde": ["verde"],
        "rojo": ["rojo", "roja"],
        "ambar": ["ambar", "amarillo", "amarilla"],
    }
    return any(nombre in texto for nombre in colores.get(color, []))


def es_componente_circuito_control(fila, subtipo):
    texto = _normalizar(
        f"{fila['descripcion']} {fila['categoria']} {fila['modelo']}"
    )
    if subtipo == "fusible":
        return (
            "fusible" in texto
            and not any(
                nombre in texto
                for nombre in [
                    "portafusible", "porta fusible", "base para fusible"
                ]
            )
        )
    if subtipo == "portafusible":
        return any(
            nombre in texto
            for nombre in [
                "portafusible", "porta fusible", "base para fusible"
            ]
        )
    if subtipo == "rele_auxiliar_24vdc":
        es_rele_auxiliar = any(
            nombre in texto
            for nombre in [
                "rele auxiliar", "rele enchufable", "rele interfaz"
            ]
        )
        es_24vdc = bool(re.search(r"\b24\s*v\s*dc\b", texto))
        return (
            es_rele_auxiliar
            and es_24vdc
            and "rele programable" not in texto
            and "base de rele" not in texto
        )
    if subtipo == "distribucion":
        return any(
            nombre in texto
            for nombre in [
                "cuadro de distribucion",
                "bloque de distribucion",
                "bloque repartidor",
                "repartidor de potencia",
                "distribuidor de potencia",
            ]
        )
    return False


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
    cantidad_variadores = (
        total if tipo_control == "Un variador por bomba"
        else 1 if tipo_control == "Un variador compartido"
        else 0
    )
    corriente_bomba = calcular_corriente_corregida(
        cotizacion["corriente_motor"], cotizacion.get("altitud_msnm", 0)
    )
    corriente_general = corriente_bomba * total
    requerimientos = [
        {
            "grupo": "Protección general",
            "cantidad": 1,
            "palabras": ["interruptor termomagnetico", "interruptor caja moldeada"],
            "corriente_requerida": corriente_bomba * total,
            "criterio_corriente": "minima",
            "nota": (
                f"Protección principal: mínimo {corriente_bomba * total:.2f} A, "
                f"calculado con {total} bomba(s) y corriente derrateada."
            ),
        },
        {
            "grupo": "Circuitos derivados",
            "cantidad": total,
            "palabras": [
                "interruptor termomagnetico", "interruptor automatico",
                "interruptor magnetotermico", "interruptor caja moldeada",
                "guarda motor", "guardamotor", "disyuntor", "breaker",
                "mcb", "mccb",
            ],
            "corriente_requerida": corriente_bomba,
            "criterio_corriente": "minima",
            "tipo_componente": "proteccion_circuito_derivado",
            "polos_requeridos": int(cotizacion["fases"]),
            "nota": (
                f"Un interruptor termomagnético o guardamotor por variador. "
                f"Solo se muestran equipos con capacidad mínima de "
                f"{corriente_bomba:.2f} A después del derrateo; los "
                f"interruptores deben ser de {cotizacion['fases']} polos."
            ),
        },
        {
            "grupo": "Accesorios de puerta - Conmutadores",
            "cantidad": total,
            "palabras": ["conmutador", "selector"],
            "criterio_corriente": None,
            "tipo_componente": "accesorio_puerta",
            "subtipo_accesorio": "conmutador",
            "nota": (
                f"Un conmutador o selector por bomba: {total} unidad(es)."
            ),
        },
        {
            "grupo": "Accesorios de puerta - Pilotos verdes",
            "cantidad": total,
            "palabras": [
                "piloto de senalizacion verde", "piloto senalizacion verde"
            ],
            "criterio_corriente": None,
            "tipo_componente": "accesorio_puerta",
            "subtipo_accesorio": "piloto",
            "color_requerido": "verde",
            "nota": f"Un piloto verde por bomba: {total} unidad(es).",
        },
        {
            "grupo": "Accesorios de puerta - Pilotos rojos",
            "cantidad": total + 2,
            "palabras": [
                "piloto de senalizacion rojo", "piloto senalizacion rojo"
            ],
            "criterio_corriente": None,
            "tipo_componente": "accesorio_puerta",
            "subtipo_accesorio": "piloto",
            "color_requerido": "rojo",
            "nota": (
                f"{total} piloto(s) rojo(s) para las bombas y 2 adicionales "
                f"para bajo nivel de cisterna y sobrepresión: "
                f"{total + 2} unidad(es)."
            ),
        },
        {
            "grupo": "Accesorios de puerta - Piloto ámbar",
            "cantidad": 1,
            "palabras": [
                "piloto de senalizacion ambar",
                "piloto de senalizacion amarillo",
                "piloto senalizacion amarillo",
            ],
            "criterio_corriente": None,
            "tipo_componente": "accesorio_puerta",
            "subtipo_accesorio": "piloto",
            "color_requerido": "ambar",
            "nota": (
                "Un piloto ámbar; también se reconocen las denominaciones "
                "amarillo o amarilla del inventario."
            ),
        },
        {
            "grupo": "Circuito de control - Fusibles",
            "cantidad": 4,
            "palabras": ["fusible"],
            "criterio_corriente": None,
            "tipo_componente": "circuito_control",
            "subtipo_control": "fusible",
            "nota": "Cuatro fusibles para protección del circuito de control.",
        },
        {
            "grupo": "Circuito de control - Portafusibles",
            "cantidad": 4,
            "palabras": [
                "portafusible", "porta fusible", "base para fusible"
            ],
            "criterio_corriente": None,
            "tipo_componente": "circuito_control",
            "subtipo_control": "portafusible",
            "nota": "Un portafusible por cada fusible: 4 unidades.",
        },
        {
            "grupo": "Control automático",
            "cantidad": 1,
            "palabras": ["plc", "rele programable", "controlador"],
            "criterio_corriente": None,
            "nota": "Control de alternancia, presión, alarmas y secuencia de bombas.",
        },
        {
            "grupo": "Transmisor de presión",
            "cantidad": 1,
            "palabras": ["transmisor de presion", "sensor de presion", "presostato"],
            "criterio_corriente": None,
            "nota": f"Señal requerida: {cotizacion['senal_sensor']}.",
        },
        {
            "grupo": "Fuente o transformador de control",
            "cantidad": 1,
            "palabras": ["fuente de alimentacion", "transformador"],
            "criterio_corriente": None,
            "nota": "Alimentación para PLC, sensores y elementos de mando.",
        },
        {
            "grupo": "Gabinete",
            "cantidad": 1,
            "palabras": ["gabinete", "tablero"],
            "criterio_corriente": None,
            "nota": "Dimensionar después de confirmar equipos, ventilación y reserva física.",
        },
    ]

    if cantidad_variadores > 0:
        indice_control = next(
            indice for indice, item in enumerate(requerimientos)
            if item["grupo"] == "Control automático"
        )
        requerimientos.insert(indice_control, {
            "grupo": "Circuito de control - Relés auxiliares 24 VDC",
            "cantidad": cantidad_variadores,
            "palabras": [
                "rele auxiliar", "rele enchufable", "rele interfaz"
            ],
            "criterio_corriente": None,
            "tipo_componente": "circuito_control",
            "subtipo_control": "rele_auxiliar_24vdc",
            "nota": (
                f"Un relé auxiliar de bobina 24 VDC por variador: "
                f"{cantidad_variadores} unidad(es)."
            ),
        })

    if total > 2:
        indice_control = next(
            indice for indice, item in enumerate(requerimientos)
            if item["grupo"] == "Control automático"
        )
        requerimientos.insert(indice_control, {
            "grupo": "Circuito de potencia - Cuadros de distribución",
            "cantidad": 3,
            "palabras": [
                "cuadro de distribucion", "bloque de distribucion",
                "bloque repartidor", "repartidor de potencia",
                "distribuidor de potencia",
            ],
            "corriente_requerida": corriente_general,
            "criterio_corriente": "minima",
            "tipo_componente": "circuito_control",
            "subtipo_control": "distribucion",
            "nota": (
                f"Tres cuadros o bloques de distribución, cada uno con "
                f"capacidad mínima de {corriente_general:.2f} A, equivalente "
                f"a la corriente general derrateada."
            ),
        })

    if tipo_control == "Un variador por bomba":
        requerimientos.insert(0, {
            "grupo": "Variadores de frecuencia",
            "cantidad": total,
            "palabras": ["variador"],
            "corriente_requerida": corriente_bomba,
            "criterio_corriente": "minima",
            "tipo_componente": "variador",
            "tension_requerida": int(cotizacion["tension"]),
            "nota": (
                f"Un variador por bomba, mínimo {corriente_bomba:.2f} A después "
                f"del derrateo, {cotizacion['tension']} V."
            ),
        })
    elif tipo_control == "Un variador compartido":
        requerimientos.insert(0, {
            "grupo": "Variador de frecuencia",
            "cantidad": 1,
            "palabras": ["variador"],
            "corriente_requerida": corriente_bomba,
            "criterio_corriente": "minima",
            "tipo_componente": "variador",
            "tension_requerida": int(cotizacion["tension"]),
            "nota": (
                f"Variador compartido, mínimo {corriente_bomba:.2f} A después "
                f"del derrateo, {cotizacion['tension']} V."
            ),
        })
        requerimientos.insert(2, {
            "grupo": "Contactores de transferencia",
            "cantidad": total,
            "palabras": ["contactor"],
            "corriente_requerida": corriente_bomba,
            "criterio_corriente": "minima",
            "nota": "Transferencia entre motores con enclavamiento eléctrico y mecánico.",
        })
    elif tipo_control == "Arranque directo":
        requerimientos.insert(0, {
            "grupo": "Contactores de potencia",
            "cantidad": total,
            "palabras": ["contactor"],
            "corriente_requerida": corriente_bomba,
            "criterio_corriente": "minima",
            "nota": "Un contactor por bomba; seleccionar categoría AC-3.",
        })
    elif tipo_control == "Estrella-triángulo":
        requerimientos.insert(0, {
            "grupo": "Contactores estrella-triángulo",
            "cantidad": total * 3,
            "palabras": ["contactor"],
            "corriente_requerida": corriente_bomba,
            "criterio_corriente": "minima",
            "nota": "Tres contactores por motor; validar calibres de línea, estrella y triángulo.",
        })
        requerimientos.insert(1, {
            "grupo": "Temporizadores estrella-triángulo",
            "cantidad": total,
            "palabras": ["temporizador estrella", "temporizador"],
            "criterio_corriente": None,
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
            stock, stock_minimo, costo_unitario, corriente_nominal, moneda, estado
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

    if requerimiento.get("tipo_componente") == "variador":
        componentes = componentes[
            componentes.apply(es_variador_frecuencia, axis=1)
        ].copy()
        if componentes.empty:
            return componentes.reset_index(drop=True)
        componentes = componentes[
            componentes.apply(
                lambda fila: admite_tension(
                    f"{fila['descripcion']} {fila['modelo']}",
                    requerimiento["tension_requerida"],
                ),
                axis=1,
            )
        ].copy()
        if componentes.empty:
            return componentes.reset_index(drop=True)

    if requerimiento.get("tipo_componente") == "proteccion_circuito_derivado":
        componentes = componentes[
            componentes.apply(
                lambda fila: cumple_polos_circuito_derivado(
                    fila, requerimiento["polos_requeridos"]
                ),
                axis=1,
            )
        ].copy()
        if componentes.empty:
            return componentes.reset_index(drop=True)

    if requerimiento.get("tipo_componente") == "accesorio_puerta":
        componentes = componentes[
            componentes.apply(
                lambda fila: es_accesorio_puerta(
                    fila,
                    requerimiento["subtipo_accesorio"],
                    requerimiento.get("color_requerido"),
                ),
                axis=1,
            )
        ].copy()
        if componentes.empty:
            return componentes.reset_index(drop=True)

    if requerimiento.get("tipo_componente") == "circuito_control":
        componentes = componentes[
            componentes.apply(
                lambda fila: es_componente_circuito_control(
                    fila, requerimiento["subtipo_control"]
                ),
                axis=1,
            )
        ].copy()
        if componentes.empty:
            return componentes.reset_index(drop=True)

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
    if candidatos.empty:
        return candidatos.reset_index(drop=True)
    criterio = requerimiento.get("criterio_corriente")
    corriente_requerida = requerimiento.get("corriente_requerida")
    if criterio and corriente_requerida is not None:
        candidatos["corriente_seleccion"] = candidatos.apply(
            lambda fila: (
                float(fila["corriente_nominal"])
                if float(fila["corriente_nominal"] or 0) > 0
                else (
                    extraer_rango_corriente(
                        f"{fila['descripcion']} {fila['modelo']}"
                    ) or (0, 0)
                )[1]
            ),
            axis=1,
        )
        candidatos = candidatos[
            candidatos["corriente_seleccion"] >= corriente_requerida
        ].copy()
        if candidatos.empty:
            return candidatos.reset_index(drop=True)
        candidatos = candidatos.sort_values(
            ["corriente_seleccion", "puntaje", "stock", "descripcion"],
            ascending=[True, False, False, True],
        )
        if (
            requerimiento.get("tipo_componente")
            == "proteccion_circuito_derivado"
        ):
            candidatos["tipo_proteccion"] = candidatos.apply(
                clasificar_proteccion_circuito_derivado, axis=1
            )
            candidatos = pd.concat(
                [
                    candidatos[
                        candidatos["tipo_proteccion"] == tipo
                    ].head(limite)
                    for tipo in [
                        "Guardamotor",
                        "Interruptor termomagnético",
                    ]
                ],
                ignore_index=True,
            )
            return candidatos.sort_values(
                [
                    "tipo_proteccion",
                    "corriente_seleccion",
                    "puntaje",
                    "stock",
                    "descripcion",
                ],
                ascending=[True, True, False, False, True],
            ).reset_index(drop=True)
        return candidatos.head(limite).reset_index(drop=True)
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
