import streamlit as st

from database.init_db import inicializar_base_datos
from modules.cotizaciones import obtener_cotizaciones
from modules.resumen_comercial import (
    calcular_resumen,
    guardar_resumen,
    obtener_costos_adicionales,
    obtener_parametros_comerciales,
)
from modules.seleccion_componentes import obtener_detalle_cotizacion


inicializar_base_datos()
st.set_page_config(page_title="Resumen comercial", page_icon="💰", layout="wide")
st.title("💰 Resumen comercial")
st.write("Complete los costos adicionales y calcule el precio final de la cotización.")

cotizaciones = obtener_cotizaciones()
if cotizaciones.empty:
    st.info("Primero registre una cotización.")
    st.stop()

opciones = {
    f"{fila.numero} | {fila.cliente} | {fila.proyecto}": int(fila.id)
    for fila in cotizaciones.itertuples()
}
etiqueta = st.selectbox("Seleccione la cotización", opciones.keys())
cotizacion_id = opciones[etiqueta]
detalle = obtener_detalle_cotizacion(cotizacion_id)
parametros = obtener_parametros_comerciales(cotizacion_id)

if detalle.empty:
    st.warning("La cotización no tiene componentes confirmados. Complete primero la selección.")
    st.stop()

with st.form("resumen_comercial"):
    c1, c2, c3 = st.columns(3)
    tipo_cambio = c1.number_input(
        "Tipo de cambio USD → PEN", min_value=0.01,
        value=float(parametros["tipo_cambio"]), step=0.01,
    )
    descuento = c2.number_input(
        "Descuento comercial (%)", min_value=0.0, max_value=100.0,
        value=float(parametros["descuento_porcentaje"]), step=0.5,
    )
    igv = c3.number_input(
        "IGV (%)", min_value=0.0, max_value=100.0,
        value=float(parametros["igv_porcentaje"]), step=1.0,
    )

    st.subheader("Costos adicionales en soles")
    adicionales_base = obtener_costos_adicionales(cotizacion_id)
    adicionales = st.data_editor(
        adicionales_base,
        use_container_width=True,
        hide_index=True,
        num_rows="dynamic",
        column_config={
            "descripcion": st.column_config.TextColumn("Descripción", required=True, width="large"),
            "cantidad": st.column_config.NumberColumn("Cantidad", min_value=0.01, step=1.0),
            "costo_unitario": st.column_config.NumberColumn(
                "Costo unitario (S/)", min_value=0.0, step=10.0, format="S/ %.2f"
            ),
            "recargo_porcentaje": st.column_config.NumberColumn(
                "Recargo (%)", min_value=0.0, step=1.0, format="%.1f %%"
            ),
        },
    )
    c1, c2 = st.columns(2)
    calcular = c1.form_submit_button("Calcular y guardar borrador", type="primary")
    emitir = c2.form_submit_button("Calcular y marcar como emitida")

if calcular or emitir:
    try:
        resumen = calcular_resumen(
            cotizacion_id, tipo_cambio, adicionales, descuento, igv
        )
        resultado = guardar_resumen(
            cotizacion_id, tipo_cambio, descuento, igv, resumen, emitir=emitir
        )
        if resultado["correcto"]:
            st.session_state["ultimo_resumen"] = resumen
            st.session_state["ultima_cotizacion_resumen"] = cotizacion_id
            st.success(f"Resumen guardado. Estado: {resultado['estado']}.")
        else:
            st.error(f"No se pudo guardar: {resultado['error']}")
    except Exception as error:
        st.error(str(error))

resumen = None
if st.session_state.get("ultima_cotizacion_resumen") == cotizacion_id:
    resumen = st.session_state.get("ultimo_resumen")
elif parametros["subtotal_venta"] > 0:
    try:
        resumen = calcular_resumen(
            cotizacion_id,
            float(parametros["tipo_cambio"]),
            obtener_costos_adicionales(cotizacion_id),
            float(parametros["descuento_porcentaje"]),
            float(parametros["igv_porcentaje"]),
        )
    except Exception:
        resumen = None

if resumen:
    st.subheader("Materiales valorizados en soles")
    st.dataframe(resumen["materiales"], use_container_width=True, hide_index=True)
    st.subheader("Totales")
    c1, c2, c3 = st.columns(3)
    c1.metric("Materiales", f"S/ {resumen['subtotal_materiales']:,.2f}")
    c2.metric("Costos adicionales", f"S/ {resumen['subtotal_adicionales']:,.2f}")
    c3.metric("Descuento", f"S/ {resumen['descuento_monto']:,.2f}")
    c1, c2, c3 = st.columns(3)
    c1.metric("Subtotal de venta", f"S/ {resumen['subtotal_venta']:,.2f}")
    c2.metric("IGV", f"S/ {resumen['igv_monto']:,.2f}")
    c3.metric("TOTAL", f"S/ {resumen['total_venta']:,.2f}")
