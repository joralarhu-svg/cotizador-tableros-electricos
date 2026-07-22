import streamlit as st

from database.init_db import inicializar_base_datos


inicializar_base_datos()

st.set_page_config(
    page_title="Cotizador de tableros eléctricos",
    page_icon="⚡",
    layout="wide",
)

st.title("⚡ Cotizador de tableros eléctricos")
st.subheader("Sistemas de presión constante")
st.write(
    "Aplicativo para administrar componentes de almacén y generar "
    "cotizaciones de tableros eléctricos para sistemas de bombeo."
)
st.info("Utilice el menú lateral para acceder al módulo de Inventario.")

