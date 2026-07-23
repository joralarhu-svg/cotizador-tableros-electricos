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
            "proyecto": "Sistema de presión constante",
            "tipo_tablero": "Alternador", "cantidad_bombas": 2,
            "potencia_hp": 5.0,
            "corriente_motor": 14.0, "tension": 220, "fases": 3,
            "altitud_msnm": 2500,
            "tipo_control": "Un variador por bomba", "presion_trabajo": 4.0,
            "unidad_presion": "bar", "con_alarma": True,
            "observaciones": "",
        })
        self.assertTrue(resultado["correcto"])
        self.assertTrue(resultado["numero"].startswith("COT-"))
        cotizaciones = obtener_cotizaciones()
        self.assertEqual(len(cotizaciones), 1)
        self.assertEqual(int(cotizaciones.iloc[0]["con_alarma"]), 1)
        self.assertEqual(cotizaciones.iloc[0]["tipo_tablero"], "Alternador")

    def test_rechaza_altitud_negativa(self):
        from modules.cotizaciones import validar_datos_tecnicos
        errores = validar_datos_tecnicos({
            "cantidad_bombas": 3, "altitud_msnm": -1,
            "potencia_hp": 5.0, "corriente_motor": 14.0, "presion_trabajo": 4.0,
        })
        self.assertTrue(errores)

    def test_rechaza_tipo_de_tablero_invalido(self):
        from modules.cotizaciones import validar_datos_tecnicos

        errores = validar_datos_tecnicos({
            "tipo_tablero": "Otro",
            "cantidad_bombas": 2,
            "potencia_hp": 5,
            "corriente_motor": 14,
            "altitud_msnm": 0,
            "presion_trabajo": 4,
        })
        self.assertIn("El tipo de tablero seleccionado no es válido.", errores)

    def test_contraincendio_guarda_bomba_principal_y_jockey(self):
        from modules.cotizaciones import (
            obtener_cotizaciones,
            registrar_cliente,
            registrar_cotizacion,
        )

        cliente_id = registrar_cliente({
            "tipo_documento": "RUC",
            "numero_documento": "20987654321",
            "razon_social": "Cliente contraincendio",
        })
        resultado = registrar_cotizacion(cliente_id, {
            "proyecto": "Sala de bombas",
            "tipo_tablero": "Contraincendio",
            "cantidad_bombas": 2,
            "potencia_hp": 40,
            "corriente_motor": 105,
            "potencia_jockey_hp": 3,
            "corriente_jockey": 8,
            "tension": 220,
            "fases": 3,
            "altitud_msnm": 500,
            "tipo_control": "Estrella-triángulo",
            "presion_trabajo": 1,
            "unidad_presion": "bar",
        })
        self.assertTrue(resultado["correcto"])
        cotizacion = obtener_cotizaciones().iloc[0]
        self.assertEqual(cotizacion["potencia_hp"], 40)
        self.assertEqual(cotizacion["corriente_motor"], 105)
        self.assertEqual(cotizacion["potencia_jockey_hp"], 3)
        self.assertEqual(cotizacion["corriente_jockey"], 8)

    def test_contraincendio_rechaza_variador_y_datos_jockey_vacios(self):
        from modules.cotizaciones import validar_datos_tecnicos

        errores = validar_datos_tecnicos({
            "tipo_tablero": "Contraincendio",
            "cantidad_bombas": 2,
            "potencia_hp": 40,
            "corriente_motor": 105,
            "potencia_jockey_hp": 0,
            "corriente_jockey": 0,
            "altitud_msnm": 0,
            "tipo_control": "Un variador por bomba",
            "presion_trabajo": 1,
        })
        self.assertIn(
            "La potencia y la corriente de la bomba jockey deben ser mayores que cero.",
            errores,
        )
        self.assertTrue(any("solo admite control" in error for error in errores))

    def test_eliminar_cotizacion_borra_relaciones_y_conserva_cliente(self):
        from modules.cotizaciones import (
            eliminar_cotizaciones,
            registrar_cliente,
            registrar_cotizacion,
        )
        from modules.db import obtener_conexion

        cliente_id = registrar_cliente({
            "tipo_documento": "RUC",
            "numero_documento": "20123456789",
            "razon_social": "Cliente de prueba",
        })
        creada = registrar_cotizacion(cliente_id, {
            "proyecto": "Sistema con eliminación",
            "cantidad_bombas": 2,
            "potencia_hp": 5,
            "corriente_motor": 14,
            "altitud_msnm": 1000,
            "tension": 220,
            "fases": 3,
            "tipo_control": "Un variador por bomba",
            "presion_trabajo": 4,
            "unidad_presion": "bar",
        })
        cotizacion_id = creada["id"]

        conexion = obtener_conexion()
        try:
            conexion.execute(
                """INSERT INTO componentes
                (codigo, descripcion, categoria, marca, unidad, stock,
                 stock_minimo, costo_unitario, moneda, estado)
                VALUES ('COMP-DELETE', 'Componente de prueba', 'Prueba',
                        'Prueba', 'und', 1, 0, 10, 'PEN', 'Activo')"""
            )
            componente_id = conexion.execute(
                "SELECT id FROM componentes WHERE codigo='COMP-DELETE'"
            ).fetchone()["id"]
            conexion.execute(
                """INSERT INTO detalle_cotizacion
                (cotizacion_id, componente_id, cantidad, costo_unitario,
                 margen, precio_unitario)
                VALUES (?, ?, 1, 10, 0, 10)""",
                (cotizacion_id, componente_id),
            )
            conexion.execute(
                """INSERT INTO costos_adicionales
                (cotizacion_id, descripcion, cantidad, costo_unitario,
                 recargo_porcentaje, precio_unitario, subtotal)
                VALUES (?, 'Integración', 1, 100, 0, 100, 100)""",
                (cotizacion_id,),
            )
            conexion.commit()
        finally:
            conexion.close()

        resultado = eliminar_cotizaciones([cotizacion_id])
        self.assertTrue(resultado["correcto"])
        self.assertEqual(resultado["eliminadas"], 1)

        conexion = obtener_conexion()
        try:
            for tabla in ("cotizaciones", "detalle_cotizacion", "costos_adicionales"):
                total = conexion.execute(
                    f"SELECT COUNT(*) AS total FROM {tabla} WHERE "
                    f"{'id' if tabla == 'cotizaciones' else 'cotizacion_id'}=?",
                    (cotizacion_id,),
                ).fetchone()["total"]
                self.assertEqual(total, 0)
            clientes = conexion.execute(
                "SELECT COUNT(*) AS total FROM clientes WHERE id=?",
                (cliente_id,),
            ).fetchone()["total"]
            self.assertEqual(clientes, 1)
        finally:
            conexion.close()

    def test_eliminar_cotizaciones_requiere_seleccion(self):
        from modules.cotizaciones import eliminar_cotizaciones

        resultado = eliminar_cotizaciones([])
        self.assertFalse(resultado["correcto"])
        self.assertEqual(resultado["eliminadas"], 0)


if __name__ == "__main__":
    unittest.main()
