import streamlit as st

from database.init_db import inicializar_base_datos
from modules.cotizaciones import obtener_cotizaciones
from modules.seleccion_componentes import (
    buscar_candidatos,
    calcular_corriente_corregida,
    calcular_factor_derrateo,
    extraer_rango_corriente,
    generar_requerimientos,
    guardar_seleccion,
    obtener_cotizacion,
    obtener_detalle_cotizacion,
)


inicializar_base_datos()
st.set_page_config(page_title="Selección de componentes", page_icon="🧩", layout="wide")
st.title("🧩 Selección asistida de componentes")
st.warning(
    "Las sugerencias son una ayuda de búsqueda. El responsable técnico debe validar "
    "corriente, tensión, poder de corte, coordinación, IP y condiciones de instalación."
)

cotizaciones = obtener_cotizaciones()
if cotizaciones.empty:
    st.info("Primero registre una cotización en el módulo Nueva cotización.")
    st.stop()

opciones = {
    f"{fila.numero} | {fila.cliente} | {fila.proyecto}": int(fila.id)
    for fila in cotizaciones.itertuples()
}
etiqueta = st.selectbox("Seleccione la cotización", opciones.keys())
cotizacion_id = opciones[etiqueta]
cotizacion = obtener_cotizacion(cotizacion_id)

c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("Bombas", cotizacion["cantidad_bombas"])
c2.metric("Potencia por bomba", f"{cotizacion['potencia_hp']:g} HP")
c3.metric("Corriente nominal", f"{cotizacion['corriente_motor']:g} A")
c4.metric("Altitud", f"{cotizacion['altitud_msnm']:g} msnm")
c5.metric("Tensión", f"{cotizacion['tension']} V")
factor_derrateo = calcular_factor_derrateo(cotizacion["altitud_msnm"])
corriente_corregida = calcular_corriente_corregida(
    cotizacion["corriente_motor"], cotizacion["altitud_msnm"]
)
st.info(
    f"Factor de derrateo: {factor_derrateo:.3f} · "
    f"Corriente corregida por bomba: {corriente_corregida:.2f} A"
)
st.caption(f"Control: {cotizacion['tipo_control']} · Sensor: {cotizacion['senal_sensor']}")

requerimientos = generar_requerimientos(cotizacion)
selecciones = []

with st.form("seleccion_componentes"):
    margen_general = st.number_input(
        "Recargo general sobre costo (%)", min_value=0.0, value=25.0, step=1.0
    )
    st.divider()
    for indice, requerimiento in enumerate(requerimientos):
        st.subheader(f"{indice + 1}. {requerimiento['grupo']}")
        st.caption(requerimiento["nota"])
        candidatos = buscar_candidatos(requerimiento, cotizacion)
        if candidatos.empty:
            st.error("No se encontraron candidatos en el inventario para este requerimiento.")
            continue

        etiquetas = {"No seleccionar": None}
        filas = {}
        for fila in candidatos.itertuples():
            estado_stock = "Disponible" if fila.stock >= requerimiento["cantidad"] else "Stock insuficiente"
            rango = extraer_rango_corriente(
                f"{fila.descripcion} {fila.modelo or ''}"
            )
            capacidad = ""
            if rango:
                capacidad = (
                    f" | Capacidad: {rango[0]:g}-{rango[1]:g} A"
                    if rango[0] != rango[1]
                    else f" | Capacidad: {rango[1]:g} A"
                )
            texto = (
                f"{fila.codigo} | {fila.descripcion} | Stock: {fila.stock} | "
                f"{fila.moneda} {fila.costo_unitario:,.2f}{capacidad} | {estado_stock}"
            )
            etiquetas[texto] = int(fila.id)
            filas[int(fila.id)] = fila

        c1, c2 = st.columns([4, 1])
        elegido = c1.selectbox(
            "Componente sugerido",
            etiquetas.keys(),
            key=f"componente_{indice}",
        )
        cantidad = c2.number_input(
            "Cantidad", min_value=1.0, value=float(requerimiento["cantidad"]),
            step=1.0, key=f"cantidad_{indice}",
        )
        componente_id = etiquetas[elegido]
        if componente_id is not None:
            fila = filas[componente_id]
            selecciones.append({
                "componente_id": componente_id,
                "cantidad": cantidad,
                "costo_unitario": float(fila.costo_unitario),
                "margen": margen_general,
                "observaciones": requerimiento["grupo"],
            })
            if fila.stock < cantidad:
                st.warning(f"Stock insuficiente: requerido {cantidad:g}, disponible {fila.stock:g}.")
        st.divider()

    confirmar = st.checkbox("Confirmo que revisé técnicamente los componentes seleccionados.")
    guardar = st.form_submit_button("Guardar selección", type="primary")

if guardar:
    if not confirmar:
        st.error("Confirme la revisión técnica antes de guardar la selección.")
    elif not selecciones:
        st.error("Seleccione por lo menos un componente.")
    else:
        resultado = guardar_seleccion(cotizacion_id, selecciones)
        if resultado["correcto"]:
            st.success(f"Se guardaron {resultado['items']} componentes en la cotización.")
            st.rerun()
        else:
            st.error(f"No se pudo guardar la selección: {resultado['error']}")

detalle = obtener_detalle_cotizacion(cotizacion_id)
if not detalle.empty:
    st.subheader("Componentes confirmados")
    st.dataframe(detalle, use_container_width=True, hide_index=True)
    st.metric("Total de componentes", f"{detalle['subtotal'].sum():,.2f}")
