import os
import tempfile
import unittest


class CotizacionesTest(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        os.environ["COTIZADOR_DB_PATH"] = os.path.join(self.tempdir.name, "test.db")
        from database.init_db import inicializar_base_datos
        inicializar_base_datos()

    def tearDown(self):
        os.environ.pop("COTIZADOR_DB_PATH", None)
        self.tempdir.cleanup()

    def test_registra_cliente_y_cotizacion(self):
        from modules.cotizaciones import (
            obtener_cotizaciones,
            registrar_cliente,
            registrar_cotizacion,
        )
        cliente_id = registrar_cliente({
            "tipo_documento": "RUC", "numero_documento": "20123456789",
            "razon_social": "Cliente de prueba", "contacto": "Jorge",
            "telefono": "", "correo": "", "direccion": "",
        })
        resultado = registrar_cotizacion(cliente_id, {
            "proyecto": "Sistema de presión constante", "cantidad_bombas": 2,
            "potencia_hp": 5.0,
            "corriente_motor": 14.0, "tension": 220, "fases": 3,
            "altitud_msnm": 2500,
            "tipo_control": "Un variador por bomba", "presion_trabajo": 4.0,
            "unidad_presion": "bar", "senal_sensor": "4-20 mA",
            "observaciones": "",
        })
        self.assertTrue(resultado["correcto"])
        self.assertTrue(resultado["numero"].startswith("COT-"))
        self.assertEqual(len(obtener_cotizaciones()), 1)

    def test_rechaza_altitud_negativa(self):
        from modules.cotizaciones import validar_datos_tecnicos
        errores = validar_datos_tecnicos({
            "cantidad_bombas": 3, "altitud_msnm": -1,
            "potencia_hp": 5.0, "corriente_motor": 14.0, "presion_trabajo": 4.0,
        })
        self.assertTrue(errores)


if __name__ == "__main__":
    unittest.main()
