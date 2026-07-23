import streamlit as st

from database.init_db import inicializar_base_datos
from modules.cotizaciones import obtener_cotizaciones
from modules.generador_pdf import (
    generar_pdf_cotizacion,
    guardar_condiciones,
    guardar_configuracion_empresa,
    obtener_configuracion_empresa,
    obtener_datos_documento,
)


inicializar_base_datos()
st.set_page_config(page_title="Generar PDF", page_icon="📄", layout="wide")
st.title("📄 Generar cotización en PDF")
st.write("Configure los datos de emisión y descargue la propuesta comercial.")

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
datos = obtener_datos_documento(cotizacion_id)
cot = datos["cotizacion"]

with st.expander("Datos de la empresa emisora", expanded=cot["total_venta"] <= 0):
    empresa = obtener_configuracion_empresa()
    with st.form("datos_empresa"):
        c1, c2 = st.columns(2)
        razon_social = c1.text_input("Razón social", value=empresa.get("razon_social", ""))
        ruc = c2.text_input("RUC", value=empresa.get("ruc", ""))
        direccion = st.text_input("Dirección", value=empresa.get("direccion", ""))
        c1, c2, c3 = st.columns(3)
        telefono = c1.text_input("Teléfono", value=empresa.get("telefono", ""))
        correo = c2.text_input("Correo", value=empresa.get("correo", ""))
        sitio_web = c3.text_input("Sitio web", value=empresa.get("sitio_web", ""))
        guardar_empresa = st.form_submit_button("Guardar datos de la empresa")
    if guardar_empresa:
        guardar_configuracion_empresa({
            "razon_social": razon_social, "ruc": ruc, "direccion": direccion,
            "telefono": telefono, "correo": correo, "sitio_web": sitio_web,
        })
        st.success("Datos de la empresa guardados.")

st.subheader("Condiciones de la cotización")
with st.form("condiciones_pdf"):
    c1, c2 = st.columns(2)
    vigencia = c1.number_input(
        "Vigencia de la oferta (días)", min_value=1,
        value=int(cot["vigencia_dias"]), step=1,
    )
    plazo = c2.text_input("Plazo de entrega", value=cot["plazo_entrega"])
    garantia = c1.text_input("Garantía", value=cot["garantia"])
    forma_pago = c2.text_input("Forma de pago", value=cot["forma_pago"])
    adicionales = st.text_area(
        "Condiciones u observaciones adicionales",
        value=cot["condiciones_adicionales"] or "",
    )
    preparar = st.form_submit_button("Guardar condiciones y preparar PDF", type="primary")

if preparar:
    if not plazo.strip() or not garantia.strip() or not forma_pago.strip():
        st.error("Complete el plazo de entrega, la garantía y la forma de pago.")
    else:
        guardar_condiciones(cotizacion_id, {
            "vigencia_dias": vigencia, "plazo_entrega": plazo,
            "garantia": garantia, "forma_pago": forma_pago,
            "condiciones_adicionales": adicionales,
        })
        try:
            pdf = generar_pdf_cotizacion(cotizacion_id)
            st.session_state["pdf_cotizacion"] = pdf
            st.session_state["pdf_cotizacion_id"] = cotizacion_id
            st.success("Documento preparado correctamente.")
        except ValueError as error:
            st.error(str(error))

if st.session_state.get("pdf_cotizacion_id") == cotizacion_id:
    st.download_button(
        "Descargar cotización PDF",
        data=st.session_state["pdf_cotizacion"],
        file_name=f"{cot['numero']}.pdf",
        mime="application/pdf",
        type="primary",
        use_container_width=True,
    )
elif float(cot["total_venta"] or 0) <= 0:
    st.warning("Primero calcule y guarde el resumen comercial de esta cotización.")
