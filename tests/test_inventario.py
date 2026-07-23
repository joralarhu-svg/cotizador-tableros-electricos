import io
import os
import tempfile
import unittest

import pandas as pd


class InventarioTest(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        os.environ["COTIZADOR_DB_PATH"] = os.path.join(self.tempdir.name, "test.db")
        from database.init_db import inicializar_base_datos
        inicializar_base_datos()

    def tearDown(self):
        os.environ.pop("COTIZADOR_DB_PATH", None)
        self.tempdir.cleanup()

    def test_importacion_y_actualizacion(self):
        from modules.inventario import guardar_componentes, obtener_componentes
        datos = pd.DataFrame([{
            "codigo": "VDF-001", "descripcion": "Variador 5 HP",
            "categoria": "Variadores", "marca": "WEG", "modelo": "CFW500",
            "unidad": "und", "stock": 2, "stock_minimo": 1,
            "costo_unitario": 850.0, "corriente_nominal": 18.0,
            "moneda": "PEN", "proveedor": "",
            "ubicacion": "A-01", "estado": "Activo", "observaciones": "",
        }])
        resultado = guardar_componentes(datos)
        self.assertTrue(resultado["correcto"])
        self.assertEqual(resultado["nuevos"], 1)
        self.assertEqual(len(obtener_componentes()), 1)

    def test_detecta_encabezados_en_fila_cuatro(self):
        from modules.inventario import procesar_archivo_excel
        columnas = [
            "codigo", "descripcion", "categoria", "marca", "modelo", "unidad",
            "stock", "stock_minimo", "costo_unitario", "corriente_nominal",
            "moneda", "proveedor",
            "ubicacion", "estado", "observaciones",
        ]
        fila = ["VDF-001", "Variador", "Variadores", "WEG", "CFW500", "und",
                1, 0, 850, 18, "PEN", "", "", "Activo", ""]
        archivo = io.BytesIO()
        with pd.ExcelWriter(archivo, engine="openpyxl") as writer:
            pd.DataFrame([fila], columns=columnas).to_excel(
                writer, sheet_name="Componentes", index=False, startrow=3
            )
        archivo.seek(0)
        dataframe, errores = procesar_archivo_excel(archivo)
        self.assertEqual(errores, [])
        self.assertEqual(len(dataframe), 1)
        self.assertEqual(dataframe.iloc[0]["corriente_nominal"], 18)


if __name__ == "__main__":
    unittest.main()
