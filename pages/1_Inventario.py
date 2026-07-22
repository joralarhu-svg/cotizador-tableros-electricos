import streamlit as st

from database.init_db import inicializar_base_datos
from modules.inventario import (
    actualizar_inventario,
    guardar_componentes,
    obtener_componentes,
    procesar_archivo_excel,
)


inicializar_base_datos()
st.set_page_config(page_title="Inventario", page_icon="📦", layout="wide")
st.title("📦 Inventario de componentes")
st.write("Cargue, actualice y consulte los componentes disponibles en almacén.")

tab_importar, tab_actualizar, tab_consultar = st.tabs([
    "Importar desde Excel", "Actualizar inventario", "Consultar inventario"
])

with tab_importar:
    st.subheader("Carga del archivo de componentes")
    st.info("El archivo debe contener una hoja llamada **Componentes** y conservar los encabezados.")
    archivo = st.file_uploader("Seleccione el archivo Excel", type=["xlsx"])
    if archivo is not None:
        with st.spinner("Leyendo y validando el archivo..."):
            dataframe, errores = procesar_archivo_excel(archivo)
        if dataframe is not None:
            c1, c2, c3 = st.columns(3)
            c1.metric("Productos encontrados", len(dataframe))
            c2.metric("Categorías", dataframe["categoria"].nunique())
            c3.metric("Marcas", dataframe["marca"].nunique())
        if errores:
            st.error(f"Se encontraron {len(errores)} errores.")
            with st.expander("Ver errores encontrados", expanded=True):
                for error in errores:
                    st.write(f"❌ {error}")
            st.warning("Corrija el archivo y vuelva a cargarlo. No se guardó ningún componente.")
        elif dataframe is not None:
            st.success("El archivo pasó todas las validaciones.")
            st.dataframe(dataframe, use_container_width=True, hide_index=True)
            confirmar = st.checkbox("Confirmo que revisé los datos del archivo.")
            if st.button("Guardar componentes", type="primary", disabled=not confirmar):
                resultado = guardar_componentes(dataframe)
                if resultado["correcto"]:
                    st.success(resultado["mensaje"])
                    c1, c2, c3 = st.columns(3)
                    c1.metric("Nuevos", resultado["nuevos"])
                    c2.metric("Actualizados", resultado["actualizados"])
                    c3.metric("Procesados", resultado["total"])
                else:
                    st.error(resultado["mensaje"])
    else:
        st.warning("Seleccione un archivo Excel para iniciar la validación.")

with tab_actualizar:
    st.subheader("Actualizar existencias y costos")
    inventario = obtener_componentes()
    if inventario.empty:
        st.warning("La base de datos todavía no contiene componentes.")
    else:
        categorias = sorted(inventario["categoria"].dropna().unique().tolist())
        c1, c2 = st.columns([2, 1])
        busqueda = c1.text_input("Buscar componente", key="buscar_editar")
        categoria = c2.selectbox("Categoría", ["Todas"] + categorias, key="categoria_editar")
        filtrado = inventario.copy()
        if busqueda:
            mascara = (
                filtrado["codigo"].fillna("").str.contains(busqueda, case=False, regex=False)
                | filtrado["descripcion"].fillna("").str.contains(busqueda, case=False, regex=False)
            )
            filtrado = filtrado[mascara]
        if categoria != "Todas":
            filtrado = filtrado[filtrado["categoria"] == categoria]
        columnas = ["id", "codigo", "descripcion", "stock", "stock_minimo",
                    "costo_unitario", "proveedor", "ubicacion", "estado", "observaciones"]
        editado = st.data_editor(
            filtrado[columnas], use_container_width=True, hide_index=True,
            disabled=["id", "codigo", "descripcion"],
            column_config={
                "id": None,
                "stock": st.column_config.NumberColumn("Stock", min_value=0, step=1, format="%d"),
                "stock_minimo": st.column_config.NumberColumn("Stock mínimo", min_value=0, step=1, format="%d"),
                "costo_unitario": st.column_config.NumberColumn("Costo", min_value=0.0, step=0.01, format="%.2f"),
                "estado": st.column_config.SelectboxColumn(
                    "Estado", options=["Activo", "Inactivo", "Descontinuado"], required=True
                ),
            }, key="editor_inventario",
        )
        if st.button("Guardar cambios del inventario", type="primary"):
            resultado = actualizar_inventario(editado)
            st.success(resultado["mensaje"]) if resultado["correcto"] else st.error(resultado["mensaje"])

with tab_consultar:
    st.subheader("Componentes registrados")
    inventario = obtener_componentes()
    if inventario.empty:
        st.warning("La base de datos todavía no contiene componentes.")
    else:
        c1, c2, c3 = st.columns(3)
        c1.metric("Total", len(inventario))
        c2.metric("Activos", len(inventario[inventario["estado"] == "Activo"]))
        c3.metric("Stock bajo", len(inventario[inventario["stock"] <= inventario["stock_minimo"]]))
        f1, f2, f3 = st.columns([2, 1, 1])
        buscar = f1.text_input("Buscar", key="buscar_consulta")
        categorias = sorted(inventario["categoria"].dropna().unique().tolist())
        categoria = f2.selectbox("Categoría", ["Todas"] + categorias, key="categoria_consulta")
        estado = f3.selectbox("Estado", ["Todos", "Activo", "Inactivo", "Descontinuado"])
        filtrado = inventario.copy()
        if buscar:
            mascara = False
            for columna in ["codigo", "descripcion", "marca", "modelo"]:
                mascara = mascara | filtrado[columna].fillna("").str.contains(buscar, case=False, regex=False)
            filtrado = filtrado[mascara]
        if categoria != "Todas":
            filtrado = filtrado[filtrado["categoria"] == categoria]
        if estado != "Todos":
            filtrado = filtrado[filtrado["estado"] == estado]
        st.write(f"Resultados: **{len(filtrado)}**")
        st.dataframe(filtrado.drop(columns=["id"]), use_container_width=True, hide_index=True)

