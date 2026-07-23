from io import BytesIO

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    Paragraph,
    KeepTogether,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from modules.db import obtener_conexion
from modules.seleccion_componentes import (
    calcular_corriente_corregida,
    calcular_factor_derrateo,
)


AZUL = colors.HexColor("#17365D")
AZUL_CLARO = colors.HexColor("#DCE6F1")
GRIS = colors.HexColor("#F2F2F2")


def obtener_configuracion_empresa():
    conexion = obtener_conexion()
    try:
        fila = conexion.execute(
            "SELECT * FROM configuracion_empresa WHERE id = 1"
        ).fetchone()
        return dict(fila) if fila else {}
    finally:
        conexion.close()


def guardar_configuracion_empresa(datos):
    conexion = obtener_conexion()
    try:
        conexion.execute(
            """UPDATE configuracion_empresa SET razon_social=?, ruc=?, direccion=?,
            telefono=?, correo=?, sitio_web=? WHERE id=1""",
            (
                datos.get("razon_social", "").strip() or "MI EMPRESA",
                datos.get("ruc", "").strip(),
                datos.get("direccion", "").strip(),
                datos.get("telefono", "").strip(),
                datos.get("correo", "").strip(),
                datos.get("sitio_web", "").strip(),
            ),
        )
        conexion.commit()
    finally:
        conexion.close()


def guardar_condiciones(cotizacion_id, datos):
    conexion = obtener_conexion()
    try:
        conexion.execute(
            """UPDATE cotizaciones SET vigencia_dias=?, plazo_entrega=?, garantia=?,
            forma_pago=?, condiciones_adicionales=?, fecha_actualizacion=CURRENT_TIMESTAMP
            WHERE id=?""",
            (
                int(datos["vigencia_dias"]),
                datos["plazo_entrega"].strip(),
                datos["garantia"].strip(),
                datos["forma_pago"].strip(),
                datos.get("condiciones_adicionales", "").strip(),
                cotizacion_id,
            ),
        )
        conexion.commit()
    finally:
        conexion.close()


def obtener_datos_documento(cotizacion_id):
    conexion = obtener_conexion()
    try:
        cabecera = conexion.execute(
            """SELECT c.*, cl.tipo_documento, cl.numero_documento,
            cl.razon_social AS cliente, cl.contacto, cl.telefono AS cliente_telefono,
            cl.correo AS cliente_correo, cl.direccion AS cliente_direccion
            FROM cotizaciones c JOIN clientes cl ON cl.id=c.cliente_id
            WHERE c.id=?""",
            (cotizacion_id,),
        ).fetchone()
        materiales = conexion.execute(
            """SELECT co.codigo, co.descripcion, co.marca, co.modelo, co.moneda,
            d.cantidad, d.precio_unitario,
            d.cantidad*d.precio_unitario*
            CASE WHEN co.moneda='USD' THEN c.tipo_cambio ELSE 1 END AS subtotal_pen
            FROM detalle_cotizacion d
            JOIN componentes co ON co.id=d.componente_id
            JOIN cotizaciones c ON c.id=d.cotizacion_id
            WHERE d.cotizacion_id=? ORDER BY co.categoria, co.descripcion""",
            (cotizacion_id,),
        ).fetchall()
        adicionales = conexion.execute(
            """SELECT descripcion, cantidad, precio_unitario, subtotal
            FROM costos_adicionales WHERE cotizacion_id=? ORDER BY id""",
            (cotizacion_id,),
        ).fetchall()
        return {
            "cotizacion": dict(cabecera) if cabecera else None,
            "materiales": [dict(fila) for fila in materiales],
            "adicionales": [dict(fila) for fila in adicionales],
            "empresa": obtener_configuracion_empresa(),
        }
    finally:
        conexion.close()


def _dinero(valor):
    return f"S/ {float(valor):,.2f}"


def _texto(valor, estilo):
    return Paragraph(str(valor or "-"), estilo)


def generar_pdf_cotizacion(cotizacion_id):
    datos = obtener_datos_documento(cotizacion_id)
    cot = datos["cotizacion"]
    if not cot:
        raise ValueError("No se encontró la cotización seleccionada.")
    if not datos["materiales"]:
        raise ValueError("La cotización no tiene componentes confirmados.")
    if float(cot["total_venta"] or 0) <= 0:
        raise ValueError("Primero calcule y guarde el resumen comercial.")

    salida = BytesIO()
    documento = SimpleDocTemplate(
        salida,
        pagesize=A4,
        rightMargin=16 * mm,
        leftMargin=16 * mm,
        topMargin=15 * mm,
        bottomMargin=16 * mm,
        title=f"Cotización {cot['numero']}",
        author=datos["empresa"].get("razon_social", ""),
    )
    estilos = getSampleStyleSheet()
    normal = ParagraphStyle("NormalCot", parent=estilos["Normal"], fontSize=8.5, leading=11)
    pequeno = ParagraphStyle("Pequeno", parent=normal, fontSize=7.5, leading=9)
    titulo = ParagraphStyle(
        "TituloCot", parent=estilos["Title"], fontSize=17, textColor=AZUL,
        alignment=TA_RIGHT, spaceAfter=2,
    )
    subtitulo = ParagraphStyle(
        "Subtitulo", parent=estilos["Heading2"], fontSize=10, textColor=AZUL,
        spaceBefore=7, spaceAfter=4,
    )
    derecha = ParagraphStyle("Derecha", parent=normal, alignment=TA_RIGHT)
    centro = ParagraphStyle("Centro", parent=normal, alignment=TA_CENTER)
    historia = []

    empresa = datos["empresa"]
    emisor = [f"<b>{empresa.get('razon_social') or 'MI EMPRESA'}</b>"]
    if empresa.get("ruc"):
        emisor.append(f"RUC: {empresa['ruc']}")
    for campo in ("direccion", "telefono", "correo", "sitio_web"):
        if empresa.get(campo):
            emisor.append(str(empresa[campo]))
    encabezado = Table(
        [[Paragraph("<br/>".join(emisor), normal), Paragraph("COTIZACIÓN", titulo)],
         ["", Paragraph(f"<b>{cot['numero']}</b><br/>{str(cot['fecha_creacion'])[:10]}", derecha)]],
        colWidths=[112 * mm, 50 * mm],
    )
    encabezado.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LINEBELOW", (0, -1), (-1, -1), 1.5, AZUL),
        ("BOTTOMPADDING", (0, -1), (-1, -1), 7),
    ]))
    historia.extend([encabezado, Spacer(1, 5 * mm)])

    cliente = [
        [Paragraph("<b>CLIENTE</b>", normal), _texto(cot["cliente"], normal),
         Paragraph("<b>DOCUMENTO</b>", normal), _texto(cot["numero_documento"], normal)],
        [Paragraph("<b>CONTACTO</b>", normal), _texto(cot["contacto"], normal),
         Paragraph("<b>TELÉFONO</b>", normal), _texto(cot["cliente_telefono"], normal)],
        [Paragraph("<b>CORREO</b>", normal), _texto(cot["cliente_correo"], normal),
         Paragraph("<b>PROYECTO</b>", normal), _texto(cot["proyecto"], normal)],
    ]
    tabla_cliente = Table(cliente, colWidths=[23 * mm, 63 * mm, 24 * mm, 52 * mm])
    tabla_cliente.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (0, -1), AZUL_CLARO),
        ("BACKGROUND", (2, 0), (2, -1), AZUL_CLARO),
        ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#A6A6A6")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    historia.extend([tabla_cliente, Paragraph("ESPECIFICACIÓN DEL SISTEMA", subtitulo)])

    factor_derrateo = calcular_factor_derrateo(cot["altitud_msnm"])
    corriente_corregida = calcular_corriente_corregida(
        cot["corriente_motor"], cot["altitud_msnm"]
    )
    especificacion = (
        f"Tablero para sistema de presión constante con {cot['cantidad_bombas']} bomba(s) "
        f"disponibles para operación alternada. Motores de {cot['potencia_hp']:g} HP, "
        f"{cot['corriente_motor']:g} A, {cot['tension']} V, {cot['fases']} fase(s). "
        f"Altitud: {cot['altitud_msnm']:g} msnm; factor de derrateo {factor_derrateo:.3f}; "
        f"corriente corregida por bomba {corriente_corregida:.2f} A. "
        f"Control: {cot['tipo_control']}. Presión de trabajo: "
        f"{cot['presion_trabajo']:g} {cot['unidad_presion']}; sensor {cot['senal_sensor']}."
    )
    historia.extend([Paragraph(especificacion, normal), Paragraph("DETALLE ECONÓMICO", subtitulo)])

    filas = [[_texto("Ítem", pequeno), _texto("Código", pequeno), _texto("Descripción", pequeno),
              _texto("Cant.", pequeno), _texto("P. unitario", pequeno), _texto("Subtotal", pequeno)]]
    indice = 1
    for fila in datos["materiales"]:
        descripcion = fila["descripcion"]
        referencia = " ".join(filter(None, [fila.get("marca"), fila.get("modelo")]))
        if referencia:
            descripcion += f" - {referencia}"
        factor = float(cot["tipo_cambio"]) if fila["moneda"] == "USD" else 1
        precio_pen = float(fila["precio_unitario"]) * factor
        filas.append([
            _texto(indice, centro), _texto(fila["codigo"], pequeno), _texto(descripcion, pequeno),
            _texto(f"{float(fila['cantidad']):g}", centro),
            _texto(_dinero(precio_pen), derecha), _texto(_dinero(fila["subtotal_pen"]), derecha),
        ])
        indice += 1
    total_integracion = sum(
        float(fila["subtotal"]) for fila in datos["adicionales"]
        if float(fila["subtotal"]) > 0
    )
    if total_integracion > 0:
        filas.append([
            _texto(indice, centro), _texto("INT", pequeno),
            _texto("Integración del tablero eléctrico", pequeno),
            _texto("1", centro),
            _texto(_dinero(total_integracion), derecha),
            _texto(_dinero(total_integracion), derecha),
        ])
        indice += 1
    tabla_detalle = Table(filas, colWidths=[10*mm, 23*mm, 72*mm, 13*mm, 22*mm, 22*mm], repeatRows=1)
    tabla_detalle.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), AZUL),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("GRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#BFBFBF")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, GRIS]),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    historia.extend([tabla_detalle, Spacer(1, 3 * mm)])

    subtotal_bruto = float(cot["subtotal_materiales"]) + float(cot["subtotal_adicionales"])
    descuento_monto = subtotal_bruto - float(cot["subtotal_venta"])
    totales = [
        ["Subtotal", _dinero(subtotal_bruto)],
        [f"Descuento ({cot['descuento_porcentaje']:g}%)", _dinero(descuento_monto)],
        ["Valor de venta", _dinero(cot["subtotal_venta"])],
        [f"IGV ({cot['igv_porcentaje']:g}%)", _dinero(cot["igv_monto"])],
        [Paragraph("<b>TOTAL</b>", normal), Paragraph(f"<b>{_dinero(cot['total_venta'])}</b>", derecha)],
    ]
    tabla_totales = Table(totales, colWidths=[42 * mm, 32 * mm], hAlign="RIGHT")
    tabla_totales.setStyle(TableStyle([
        ("ALIGN", (1, 0), (1, -1), "RIGHT"),
        ("LINEABOVE", (0, -1), (-1, -1), 1.2, AZUL),
        ("BACKGROUND", (0, -1), (-1, -1), AZUL_CLARO),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    historia.append(tabla_totales)

    condiciones = [
        ["Vigencia de la oferta", f"{cot['vigencia_dias']} días calendario"],
        ["Plazo de entrega", cot["plazo_entrega"]],
        ["Garantía", cot["garantia"]],
        ["Forma de pago", cot["forma_pago"]],
    ]
    if cot.get("condiciones_adicionales"):
        condiciones.append(["Observaciones", cot["condiciones_adicionales"]])
    tabla_condiciones = Table(
        [[_texto(a, normal), _texto(b, normal)] for a, b in condiciones],
        colWidths=[42 * mm, 120 * mm],
    )
    tabla_condiciones.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (0, -1), AZUL_CLARO),
        ("GRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#BFBFBF")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    historia.append(KeepTogether([
        Paragraph("CONDICIONES COMERCIALES", subtitulo),
        tabla_condiciones,
        Spacer(1, 7 * mm),
        Paragraph("Agradecemos la oportunidad de presentar nuestra propuesta.", centro),
    ]))

    def pie_pagina(canvas, doc):
        canvas.saveState()
        canvas.setStrokeColor(AZUL)
        canvas.line(16 * mm, 11 * mm, 194 * mm, 11 * mm)
        canvas.setFont("Helvetica", 7)
        canvas.setFillColor(colors.HexColor("#666666"))
        canvas.drawString(16 * mm, 7 * mm, f"Cotización {cot['numero']}")
        canvas.drawRightString(194 * mm, 7 * mm, f"Página {doc.page}")
        canvas.restoreState()

    documento.build(historia, onFirstPage=pie_pagina, onLaterPages=pie_pagina)
    salida.seek(0)
    return salida.getvalue()
