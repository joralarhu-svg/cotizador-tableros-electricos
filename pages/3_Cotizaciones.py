import streamlit as st

from database.init_db import inicializar_base_datos
from modules.cotizaciones import eliminar_cotizaciones, obtener_cotizaciones


inicializar_base_datos()
st.set_page_config(page_title="Cotizaciones", page_icon="📋", layout="wide")
st.title("📋 Cotizaciones registradas")

cotizaciones = obtener_cotizaciones()
if cotizaciones.empty:
    st.info("Todavía no existen cotizaciones registradas.")
else:
    st.metric("Total de cotizaciones", len(cotizaciones))
    st.dataframe(cotizaciones, use_container_width=True, hide_index=True)

    st.divider()
    st.subheader("Eliminar cotizaciones")
    st.warning(
        "Esta acción eliminará permanentemente las cotizaciones seleccionadas, "
        "junto con su selección de componentes y resumen comercial."
    )

    etiquetas = {
        f"{fila.numero} · {fila.cliente} · {fila.proyecto}": int(fila.id)
        for fila in cotizaciones.itertuples()
    }
    seleccionadas = st.multiselect(
        "Cotizaciones que desea eliminar",
        options=list(etiquetas),
        placeholder="Seleccione una o más cotizaciones",
    )
    ids_seleccionados = [etiquetas[etiqueta] for etiqueta in seleccionadas]
    confirmar = st.checkbox(
        f"Confirmo la eliminación permanente de "
        f"{len(ids_seleccionados)} cotización(es).",
        disabled=not ids_seleccionados,
    )

    if st.button(
        "Eliminar cotizaciones seleccionadas",
        type="primary",
        disabled=not ids_seleccionados or not confirmar,
    ):
        resultado = eliminar_cotizaciones(ids_seleccionados)
        if resultado["correcto"]:
            st.success(
                f"Se eliminaron {resultado['eliminadas']} cotización(es) correctamente."
            )
            st.rerun()
        else:
            for error in resultado["errores"]:
                st.error(error)
