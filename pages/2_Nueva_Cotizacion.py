import streamlit as st

from database.init_db import inicializar_base_datos
from modules.cotizaciones import obtener_clientes, registrar_cliente, registrar_cotizacion


inicializar_base_datos()
st.set_page_config(page_title="Nueva cotización", page_icon="🧾", layout="wide")
st.title("🧾 Nueva cotización")
st.write("Registre el cliente y los datos técnicos del sistema de presión constante.")

clientes = obtener_clientes()

with st.form("formulario_cotizacion", clear_on_submit=False):
    st.subheader("1. Datos del cliente")
    modo_cliente = st.radio(
        "Cliente", ["Registrar nuevo cliente", "Seleccionar cliente existente"],
        horizontal=True,
    )
    cliente_id = None
    datos_cliente = None
    if modo_cliente == "Seleccionar cliente existente" and not clientes.empty:
        opciones = dict(zip(clientes["razon_social"], clientes["id"]))
        cliente_seleccionado = st.selectbox("Cliente registrado", opciones.keys())
        cliente_id = int(opciones[cliente_seleccionado])
    else:
        if modo_cliente == "Seleccionar cliente existente" and clientes.empty:
            st.info("Todavía no existen clientes registrados. Complete un nuevo cliente.")
        c1, c2, c3 = st.columns([1, 1, 2])
        tipo_documento = c1.selectbox("Tipo de documento", ["RUC", "DNI", "CE", "Otro"])
        numero_documento = c2.text_input("Número de documento")
        razon_social = c3.text_input("Razón social o nombre *")
        c1, c2, c3 = st.columns(3)
        contacto = c1.text_input("Persona de contacto")
        telefono = c2.text_input("Teléfono")
        correo = c3.text_input("Correo")
        direccion = st.text_input("Dirección")
        datos_cliente = {
            "tipo_documento": tipo_documento, "numero_documento": numero_documento,
            "razon_social": razon_social, "contacto": contacto, "telefono": telefono,
            "correo": correo, "direccion": direccion,
        }

    st.divider()
    st.subheader("2. Datos técnicos del sistema")
    proyecto = st.text_input("Proyecto o referencia *")
    c1, c2, c3 = st.columns(3)
    cantidad_bombas = c1.number_input("Cantidad total de bombas", min_value=1, value=2, step=1)
    bombas_operacion = c2.number_input("Bombas en operación", min_value=1, value=1, step=1)
    bombas_reserva = c3.number_input("Bombas de reserva", min_value=0, value=1, step=1)
    c1, c2, c3, c4 = st.columns(4)
    potencia_hp = c1.number_input("Potencia por bomba (HP)", min_value=0.1, value=5.0, step=0.5)
    corriente_motor = c2.number_input("Corriente por motor (A)", min_value=0.1, value=14.0, step=0.1)
    tension = c3.selectbox("Tensión (V)", [220, 380, 440])
    fases = c4.selectbox("Fases", [3, 1])
    c1, c2, c3 = st.columns(3)
    tipo_control = c1.selectbox(
        "Estrategia de control",
        ["Un variador por bomba", "Un variador compartido", "Arranque directo", "Estrella-triángulo"],
    )
    presion_trabajo = c2.number_input("Presión de trabajo", min_value=0.1, value=4.0, step=0.1)
    unidad_presion = c3.selectbox("Unidad de presión", ["bar", "psi", "mca"])
    senal_sensor = st.selectbox("Señal del transmisor de presión", ["4-20 mA", "0-10 V"])
    observaciones = st.text_area("Observaciones técnicas")
    guardar = st.form_submit_button("Guardar borrador de cotización", type="primary")

if guardar:
    if not proyecto.strip():
        st.error("Ingrese el nombre o referencia del proyecto.")
    elif cliente_id is None and not datos_cliente["razon_social"].strip():
        st.error("Ingrese la razón social o nombre del cliente.")
    else:
        try:
            if cliente_id is None:
                cliente_id = registrar_cliente(datos_cliente)
            resultado = registrar_cotizacion(cliente_id, {
                "proyecto": proyecto, "cantidad_bombas": int(cantidad_bombas),
                "bombas_operacion": int(bombas_operacion), "bombas_reserva": int(bombas_reserva),
                "potencia_hp": float(potencia_hp), "corriente_motor": float(corriente_motor),
                "tension": int(tension), "fases": int(fases), "tipo_control": tipo_control,
                "presion_trabajo": float(presion_trabajo), "unidad_presion": unidad_presion,
                "senal_sensor": senal_sensor, "observaciones": observaciones,
            })
            if resultado["correcto"]:
                st.success(f"Cotización {resultado['numero']} creada como borrador.")
                st.info("El siguiente paso será seleccionar los componentes del tablero.")
            else:
                for error in resultado["errores"]:
                    st.error(error)
        except Exception as error:
            st.error(f"No se pudo guardar la cotización: {error}")
