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
            "potencia_hp": 5.0,
            "corriente_motor": 14.0, "tension": 220, "fases": 3,
            "altitud_msnm": 2000,
            "tipo_control": "Un variador por bomba", "presion_trabajo": 4.0,
            "unidad_presion": "bar", "senal_sensor": "4-20 mA", "observaciones": "",
        })

    def test_genera_requerimientos_segun_control(self):
        from modules.seleccion_componentes import generar_requerimientos
        cotizacion = {
            "cantidad_bombas": 2, "tipo_control": "Un variador por bomba",
            "potencia_hp": 5.0, "corriente_motor": 14.0,
            "altitud_msnm": 2000, "tension": 220, "senal_sensor": "4-20 mA",
        }
        requerimientos = generar_requerimientos(cotizacion)
        self.assertEqual(requerimientos[0]["cantidad"], 2)
        self.assertIn("Variadores", requerimientos[0]["grupo"])
        self.assertAlmostEqual(requerimientos[0]["corriente_requerida"], 15.4)
        proteccion_general = requerimientos[1]
        self.assertEqual(proteccion_general["grupo"], "Protección general")
        self.assertAlmostEqual(proteccion_general["corriente_requerida"], 30.8)
        self.assertEqual(requerimientos[2]["grupo"], "Circuitos derivados")

    def test_calcula_derrateo_y_extrae_corriente(self):
        from modules.seleccion_componentes import (
            calcular_corriente_corregida,
            calcular_factor_derrateo,
            extraer_rango_corriente,
            extraer_rangos_tension,
            admite_tension,
        )
        self.assertEqual(calcular_factor_derrateo(1000), 1.0)
        self.assertAlmostEqual(calcular_factor_derrateo(2500), 1.15)
        self.assertAlmostEqual(calcular_corriente_corregida(20, 2500), 23.0)
        self.assertEqual(extraer_rango_corriente("Guardamotor 18-25 A"), (18.0, 25.0))
        self.assertEqual(extraer_rango_corriente("Contactor AC-3 32A"), (32.0, 32.0))
        self.assertEqual(
            extraer_rango_corriente("Soft Starter 208 a 600VAC 45AMP"),
            (45.0, 45.0),
        )
        self.assertTrue(admite_tension("Variador entrada 200-240VAC", 220))
        self.assertFalse(admite_tension("Variador trifásico 380V", 220))
        self.assertIn((380.0, 380.0), extraer_rangos_tension("Equipo 380VAC"))

    def test_busca_y_guarda_componente(self):
        from modules.inventario import guardar_componentes
        from modules.seleccion_componentes import (
            buscar_candidatos, generar_requerimientos, guardar_seleccion,
            obtener_cotizacion, obtener_detalle_cotizacion,
        )
        guardar_componentes(pd.DataFrame([{
            "codigo": "VDF-5HP", "descripcion": "Variador de frecuencia 5 HP 18A 220V",
            "categoria": "Variadores", "marca": "WEG", "modelo": "CFW500",
            "unidad": "und", "stock": 2, "stock_minimo": 1,
            "costo_unitario": 850.0, "corriente_nominal": 18.0,
            "moneda": "PEN", "proveedor": "",
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

    def test_descarta_componente_con_corriente_insuficiente(self):
        from modules.inventario import guardar_componentes
        from modules.seleccion_componentes import (
            buscar_candidatos, generar_requerimientos, obtener_cotizacion,
        )
        guardar_componentes(pd.DataFrame([
            {
                "codigo": "VDF-12A", "descripcion": "Variador 5 HP 12A 220V",
                "categoria": "Variadores", "marca": "A", "modelo": "",
                "unidad": "und", "stock": 5, "stock_minimo": 0,
                "costo_unitario": 500, "corriente_nominal": 12,
                "moneda": "PEN", "proveedor": "",
                "ubicacion": "", "estado": "Activo", "observaciones": "",
            },
            {
                "codigo": "VDF-18A", "descripcion": "Variador 5 HP 18A 220V",
                "categoria": "Variadores", "marca": "B", "modelo": "",
                "unidad": "und", "stock": 5, "stock_minimo": 0,
                "costo_unitario": 600, "corriente_nominal": 18,
                "moneda": "PEN", "proveedor": "",
                "ubicacion": "", "estado": "Activo", "observaciones": "",
            },
            {
                "codigo": "VDF-25A", "descripcion": "Variador 5 HP 25A 220V",
                "categoria": "Variadores", "marca": "C", "modelo": "",
                "unidad": "und", "stock": 5, "stock_minimo": 0,
                "costo_unitario": 700, "corriente_nominal": 25,
                "moneda": "PEN", "proveedor": "", "ubicacion": "",
                "estado": "Activo", "observaciones": "",
            },
        ]))
        creada = self._crear_cotizacion()
        cotizacion = obtener_cotizacion(creada["id"])
        candidatos = buscar_candidatos(
            generar_requerimientos(cotizacion)[0], cotizacion
        )
        self.assertEqual(candidatos["codigo"].tolist(), ["VDF-18A", "VDF-25A"])
        self.assertEqual(candidatos.iloc[0]["corriente_seleccion"], 18)

    def test_sin_capacidad_suficiente_devuelve_lista_vacia(self):
        from modules.inventario import guardar_componentes
        from modules.seleccion_componentes import (
            buscar_candidatos, generar_requerimientos, obtener_cotizacion,
        )
        guardar_componentes(pd.DataFrame([{
            "codigo": "VDF-12A", "descripcion": "Variador 5 HP 12A 220V",
            "categoria": "Variadores", "marca": "A", "modelo": "",
            "unidad": "und", "stock": 5, "stock_minimo": 0,
            "costo_unitario": 500, "corriente_nominal": 12,
            "moneda": "PEN", "proveedor": "",
            "ubicacion": "", "estado": "Activo", "observaciones": "",
        }]))
        creada = self._crear_cotizacion()
        cotizacion = obtener_cotizacion(creada["id"])
        candidatos = buscar_candidatos(
            generar_requerimientos(cotizacion)[0], cotizacion
        )
        self.assertTrue(candidatos.empty)
        self.assertIn("puntaje", candidatos.columns)

    def test_variadores_filtra_tipo_y_tension(self):
        from modules.inventario import guardar_componentes
        from modules.seleccion_componentes import (
            buscar_candidatos, generar_requerimientos, obtener_cotizacion,
        )
        base = {
            "unidad": "und", "stock": 5, "stock_minimo": 0,
            "costo_unitario": 500, "corriente_nominal": 18,
            "moneda": "PEN", "proveedor": "", "ubicacion": "",
            "estado": "Activo", "observaciones": "",
        }
        guardar_componentes(pd.DataFrame([
            {
                **base, "codigo": "VDF-220",
                "descripcion": "Variador de frecuencia 5 HP 18A 220V",
                "categoria": "Variadores", "marca": "A", "modelo": "V220",
            },
            {
                **base, "codigo": "VDF-380",
                "descripcion": "Variador de frecuencia 5 HP 18A 380V",
                "categoria": "Variadores", "marca": "B", "modelo": "V380",
            },
            {
                **base, "codigo": "CONT-220",
                "descripcion": "Contactor para variador 18A 220V",
                "categoria": "Contactores", "marca": "C", "modelo": "C18",
            },
            {
                **base, "codigo": "SS-220",
                "descripcion": "Arrancador suave 5 HP 18A 220V",
                "categoria": "Arrancadores suaves", "marca": "D", "modelo": "SS18",
            },
        ]))
        creada = self._crear_cotizacion()
        cotizacion = obtener_cotizacion(creada["id"])
        candidatos = buscar_candidatos(
            generar_requerimientos(cotizacion)[0], cotizacion
        )
        self.assertEqual(candidatos["codigo"].tolist(), ["VDF-220"])


if __name__ == "__main__":
    unittest.main()
