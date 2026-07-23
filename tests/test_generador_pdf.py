import os
import tempfile
import unittest

import pandas as pd
import pdfplumber


class GeneradorPdfTest(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        os.environ["COTIZADOR_DB_PATH"] = os.path.join(self.tempdir.name, "test.db")
        from database.init_db import inicializar_base_datos
        inicializar_base_datos()

    def tearDown(self):
        os.environ.pop("COTIZADOR_DB_PATH", None)
        self.tempdir.cleanup()

    def test_genera_pdf_con_datos_comerciales(self):
        from modules.cotizaciones import registrar_cliente, registrar_cotizacion
        from modules.generador_pdf import generar_pdf_cotizacion, guardar_condiciones
        from modules.inventario import guardar_componentes
        from modules.resumen_comercial import calcular_resumen, guardar_resumen
        from modules.seleccion_componentes import guardar_seleccion
        from modules.db import obtener_conexion

        guardar_componentes(pd.DataFrame([{
            "codigo": "VDF-5HP", "descripcion": "Variador de frecuencia",
            "categoria": "Variadores", "marca": "WEG", "modelo": "CFW500",
            "unidad": "und", "stock": 2, "stock_minimo": 0,
            "costo_unitario": 100.0, "corriente_nominal": 18.0,
            "moneda": "USD", "proveedor": "",
            "ubicacion": "", "estado": "Activo", "observaciones": "",
        }]))
        cliente_id = registrar_cliente({
            "tipo_documento": "RUC", "numero_documento": "20123456789",
            "razon_social": "Cliente Industrial SAC", "contacto": "Jefe de planta",
            "telefono": "999999999", "correo": "cliente@empresa.com", "direccion": "Lima",
        })
        cot = registrar_cotizacion(cliente_id, {
            "proyecto": "Sistema de presión constante", "cantidad_bombas": 1,
            "potencia_hp": 5,
            "corriente_motor": 14, "tension": 220, "fases": 3,
            "altitud_msnm": 2500,
            "tipo_control": "Un variador por bomba", "presion_trabajo": 50,
            "unidad_presion": "psi", "con_alarma": True,
            "observaciones": "",
        })
        conexion = obtener_conexion()
        componente_id = conexion.execute("SELECT id FROM componentes").fetchone()["id"]
        conexion.close()
        guardar_seleccion(cot["id"], [{
            "componente_id": componente_id, "cantidad": 1, "costo_unitario": 100,
            "margen": 25, "observaciones": "Equipo principal",
        }])
        adicionales = pd.DataFrame([{
            "descripcion": "Ingeniería y programación", "cantidad": 1,
            "costo_unitario": 200, "recargo_porcentaje": 0,
        }])
        resumen = calcular_resumen(cot["id"], 3.5, adicionales, 0, 18)
        guardar_resumen(cot["id"], 3.5, 0, 18, resumen, emitir=True)
        guardar_condiciones(cot["id"], {
            "vigencia_dias": 15, "plazo_entrega": "15 días",
            "garantia": "12 meses", "forma_pago": "50% de adelanto",
            "condiciones_adicionales": "Incluye pruebas en taller.",
        })

        pdf = generar_pdf_cotizacion(cot["id"])
        self.assertTrue(pdf.startswith(b"%PDF"))
        self.assertGreater(len(pdf), 3000)
        ruta_pdf = os.path.join(self.tempdir.name, "cotizacion.pdf")
        with open(ruta_pdf, "wb") as archivo:
            archivo.write(pdf)
        with pdfplumber.open(ruta_pdf) as documento:
            texto = "\n".join(pagina.extract_text() or "" for pagina in documento.pages)
        self.assertIn("Integración del tablero eléctrico", texto)
        self.assertNotIn("Ingeniería y programación", texto)
        self.assertIn("Sistema de alarma: incluido", texto)
        self.assertNotIn("4-20 mA", texto)


if __name__ == "__main__":
    unittest.main()
