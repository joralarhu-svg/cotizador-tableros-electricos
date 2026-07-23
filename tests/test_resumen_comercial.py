import os
import tempfile
import unittest

import pandas as pd


class ResumenComercialTest(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        os.environ["COTIZADOR_DB_PATH"] = os.path.join(self.tempdir.name, "test.db")
        from database.init_db import inicializar_base_datos
        inicializar_base_datos()

    def tearDown(self):
        os.environ.pop("COTIZADOR_DB_PATH", None)
        self.tempdir.cleanup()

    def test_calculo_comercial_con_igv(self):
        from modules.cotizaciones import registrar_cliente, registrar_cotizacion
        from modules.inventario import guardar_componentes
        from modules.resumen_comercial import calcular_resumen
        from modules.seleccion_componentes import guardar_seleccion

        guardar_componentes(pd.DataFrame([{
            "codigo": "VDF", "descripcion": "Variador", "categoria": "Variadores",
            "marca": "WEG", "modelo": "CFW500", "unidad": "und", "stock": 2,
            "stock_minimo": 0, "costo_unitario": 100.0,
            "corriente_nominal": 18.0, "moneda": "USD",
            "proveedor": "", "ubicacion": "", "estado": "Activo", "observaciones": "",
        }]))
        cliente = registrar_cliente({
            "tipo_documento": "RUC", "numero_documento": "20999999999",
            "razon_social": "Cliente", "contacto": "", "telefono": "",
            "correo": "", "direccion": "",
        })
        cotizacion = registrar_cotizacion(cliente, {
            "proyecto": "Proyecto", "cantidad_bombas": 1, "bombas_operacion": 1,
            "bombas_reserva": 0, "potencia_hp": 5, "corriente_motor": 14,
            "altitud_msnm": 0,
            "tension": 220, "fases": 3, "tipo_control": "Un variador por bomba",
            "presion_trabajo": 4, "unidad_presion": "bar",
            "senal_sensor": "4-20 mA", "observaciones": "",
        })
        from modules.db import obtener_conexion
        conexion = obtener_conexion()
        componente_id = conexion.execute("SELECT id FROM componentes").fetchone()["id"]
        conexion.close()
        guardar_seleccion(cotizacion["id"], [{
            "componente_id": componente_id, "cantidad": 1,
            "costo_unitario": 100, "margen": 25, "observaciones": "Variador",
        }])
        adicionales = pd.DataFrame([{
            "descripcion": "Mano de obra", "cantidad": 1,
            "costo_unitario": 100, "recargo_porcentaje": 0,
        }])
        resumen = calcular_resumen(cotizacion["id"], 3.5, adicionales, 0, 18)
        self.assertEqual(resumen["subtotal_materiales"], 437.5)
        self.assertEqual(resumen["subtotal_venta"], 537.5)
        self.assertAlmostEqual(resumen["total_venta"], 634.25)


if __name__ == "__main__":
    unittest.main()
