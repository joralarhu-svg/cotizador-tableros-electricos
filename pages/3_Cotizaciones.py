import streamlit as st

from database.init_db import inicializar_base_datos
from modules.cotizaciones import obtener_cotizaciones


inicializar_base_datos()
st.set_page_config(page_title="Cotizaciones", page_icon="📋", layout="wide")
st.title("📋 Cotizaciones registradas")

cotizaciones = obtener_cotizaciones()
if cotizaciones.empty:
    st.info("Todavía no existen cotizaciones registradas.")
else:
    st.metric("Total de cotizaciones", len(cotizaciones))
    st.dataframe(cotizaciones, use_container_width=True, hide_index=True)
