import os
import tempfile
import unittest

import pandas as pd


class SeleccionComponentesTest(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        os.environ["COTIZADOR_DB_PATH"] = os.path.join(self.tempdir.name, "test.db")
        from database.init_db import inicializar_base_datos
        inicializar_base_datos()

    def tearDown(self):
        os.environ.pop("COTIZADOR_DB_PATH", None)
        self.tempdir.cleanup()

    def _crear_cotizacion(self):
        from modules.cotizaciones import registrar_cliente, registrar_cotizacion
        cliente = registrar_cliente({
            "tipo_documento": "RUC", "numero_documento": "20111111111",
            "razon_social": "Cliente", "contacto": "", "telefono": "",
            "correo": "", "direccion": "",
        })
        return registrar_cotizacion(cliente, {
            "proyecto": "Presión constante", "cantidad_bombas": 2,
            "bombas_operacion": 1, "bombas_reserva": 1, "potencia_hp": 5.0,
            "corriente_motor": 14.0, "tension": 220, "fases": 3,
            "tipo_control": "Un variador por bomba", "presion_trabajo": 4.0,
            "unidad_presion": "bar", "senal_sensor": "4-20 mA", "observaciones": "",
        })

    def test_genera_requerimientos_segun_control(self):
        from modules.seleccion_componentes import generar_requerimientos
        cotizacion = {
            "cantidad_bombas": 2, "tipo_control": "Un variador por bomba",
            "potencia_hp": 5.0, "tension": 220, "senal_sensor": "4-20 mA",
        }
        requerimientos = generar_requerimientos(cotizacion)
        self.assertEqual(requerimientos[0]["cantidad"], 2)
        self.assertIn("Variadores", requerimientos[0]["grupo"])

    def test_busca_y_guarda_componente(self):
        from modules.inventario import guardar_componentes
        from modules.seleccion_componentes import (
            buscar_candidatos, generar_requerimientos, guardar_seleccion,
            obtener_cotizacion, obtener_detalle_cotizacion,
        )
        guardar_componentes(pd.DataFrame([{
            "codigo": "VDF-5HP", "descripcion": "Variador de frecuencia 5 HP 220V",
            "categoria": "Variadores", "marca": "WEG", "modelo": "CFW500",
            "unidad": "und", "stock": 2, "stock_minimo": 1,
            "costo_unitario": 850.0, "moneda": "PEN", "proveedor": "",
            "ubicacion": "", "estado": "Activo", "observaciones": "",
        }]))
        creada = self._crear_cotizacion()
        cotizacion = obtener_cotizacion(creada["id"])
        requerimiento = generar_requerimientos(cotizacion)[0]
        candidatos = buscar_candidatos(requerimiento, cotizacion)
        self.assertEqual(candidatos.iloc[0]["codigo"], "VDF-5HP")
        resultado = guardar_seleccion(creada["id"], [{
            "componente_id": int(candidatos.iloc[0]["id"]), "cantidad": 2,
            "costo_unitario": 850.0, "margen": 25.0,
            "observaciones": "Variadores",
        }])
        self.assertTrue(resultado["correcto"])
        detalle = obtener_detalle_cotizacion(creada["id"])
        self.assertEqual(detalle.iloc[0]["precio_unitario"], 1062.5)


if __name__ == "__main__":
    unittest.main()
