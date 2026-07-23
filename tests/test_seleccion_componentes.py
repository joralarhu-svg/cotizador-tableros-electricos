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

    def _crear_cotizacion(self, con_alarma=False):
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
            "unidad_presion": "bar", "con_alarma": con_alarma,
            "observaciones": "",
        })

    def test_genera_requerimientos_segun_control(self):
        from modules.seleccion_componentes import generar_requerimientos
        cotizacion = {
            "cantidad_bombas": 2, "tipo_control": "Un variador por bomba",
            "potencia_hp": 5.0, "corriente_motor": 14.0,
            "altitud_msnm": 2000, "tension": 220, "fases": 3,
            "con_alarma": False,
        }
        requerimientos = generar_requerimientos(cotizacion)
        self.assertEqual(requerimientos[0]["cantidad"], 2)
        self.assertIn("Variadores", requerimientos[0]["grupo"])
        self.assertAlmostEqual(requerimientos[0]["corriente_requerida"], 15.4)
        proteccion_general = requerimientos[1]
        self.assertEqual(proteccion_general["grupo"], "Protección general")
        self.assertAlmostEqual(proteccion_general["corriente_requerida"], 30.8)
        self.assertEqual(requerimientos[2]["grupo"], "Circuitos derivados")
        self.assertEqual(
            requerimientos[2]["tipo_componente"],
            "proteccion_circuito_derivado",
        )
        self.assertEqual(requerimientos[2]["polos_requeridos"], 3)
        accesorios = {
            item["grupo"]: item["cantidad"]
            for item in requerimientos
            if item["grupo"].startswith("Accesorios de puerta")
        }
        self.assertEqual(
            accesorios,
            {
                "Accesorios de puerta - Conmutadores": 2,
                "Accesorios de puerta - Pilotos verdes": 2,
                "Accesorios de puerta - Pilotos rojos": 4,
                "Accesorios de puerta - Piloto ámbar": 1,
            },
        )
        circuito_control = {
            item["grupo"]: item["cantidad"]
            for item in requerimientos
            if item["grupo"].startswith("Circuito de control")
        }
        self.assertEqual(
            circuito_control,
            {
                "Circuito de control - Fusibles": 4,
                "Circuito de control - Portafusibles": 4,
                "Circuito de control - Relés auxiliares 24 VDC": 2,
            },
        )
        self.assertNotIn(
            "Circuito de potencia - Cuadros de distribución",
            [item["grupo"] for item in requerimientos],
        )
        self.assertFalse(any(
            item["grupo"].startswith("Sistema de alarma")
            for item in requerimientos
        ))

    def test_calcula_derrateo_y_extrae_corriente(self):
        from modules.seleccion_componentes import (
            calcular_corriente_corregida,
            calcular_factor_derrateo,
            extraer_rango_corriente,
            extraer_rangos_tension,
            extraer_numero_polos,
            admite_tension,
        )
        self.assertEqual(calcular_factor_derrateo(1000), 1.0)
        self.assertAlmostEqual(calcular_factor_derrateo(2500), 1.15)
        self.assertAlmostEqual(calcular_corriente_corregida(20, 2500), 23.0)
        self.assertEqual(extraer_rango_corriente("Guardamotor 18-25 A"), (18.0, 25.0))
        self.assertEqual(extraer_rango_corriente("Contactor AC-3 32A"), (32.0, 32.0))
        self.assertEqual(
            extraer_rango_corriente(
                "Interruptor Termomagnético 3P C 20AMP 10KA"
            ),
            (20.0, 20.0),
        )
        self.assertEqual(
            extraer_rango_corriente("Soft Starter 208 a 600VAC 45AMP"),
            (45.0, 45.0),
        )
        self.assertTrue(admite_tension("Variador entrada 200-240VAC", 220))
        self.assertFalse(admite_tension("Variador trifásico 380V", 220))
        self.assertIn((380.0, 380.0), extraer_rangos_tension("Equipo 380VAC"))
        self.assertEqual(extraer_numero_polos("Interruptor 3P C20"), 3)
        self.assertEqual(extraer_numero_polos("Interruptor tetrapolar"), 4)

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
            {
                "codigo": "VDF-32A", "descripcion": "Variador 5 HP 32A 220V",
                "categoria": "Variadores", "marca": "D", "modelo": "",
                "unidad": "und", "stock": 5, "stock_minimo": 0,
                "costo_unitario": 800, "corriente_nominal": 32,
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
        self.assertEqual(
            candidatos["corriente_seleccion"].nunique(), 2
        )

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

    def test_circuitos_derivados_admite_interruptores_y_guardamotores_suficientes(self):
        from modules.inventario import guardar_componentes
        from modules.seleccion_componentes import (
            buscar_candidatos, generar_requerimientos, obtener_cotizacion,
        )
        base = {
            "unidad": "und", "stock": 5, "stock_minimo": 0,
            "costo_unitario": 100, "moneda": "PEN", "proveedor": "",
            "ubicacion": "", "estado": "Activo", "observaciones": "",
            "marca": "Prueba",
        }
        guardar_componentes(pd.DataFrame([
            {
                **base, "codigo": "TM-10A",
                "descripcion": "Interruptor termomagnético 3P 10A",
                "categoria": "Interruptores termomagnéticos", "modelo": "C10",
                "corriente_nominal": 10,
            },
            {
                **base, "codigo": "TM-16A",
                "descripcion": "Interruptor termomagnético 3P 16A",
                "categoria": "Interruptores termomagnéticos", "modelo": "C16",
                "corriente_nominal": 16,
            },
            {
                **base, "codigo": "GM-12-18A",
                "descripcion": "Guardamotor regulable 12-18 A",
                "categoria": "Guardamotores", "modelo": "GM18",
                "corriente_nominal": 0,
            },
            {
                **base, "codigo": "CONT-25A",
                "descripcion": "Contactor de potencia 25A",
                "categoria": "Contactores", "modelo": "C25",
                "corriente_nominal": 25,
            },
        ]))
        creada = self._crear_cotizacion()
        cotizacion = obtener_cotizacion(creada["id"])
        requerimiento = next(
            item for item in generar_requerimientos(cotizacion)
            if item["grupo"] == "Circuitos derivados"
        )
        candidatos = buscar_candidatos(requerimiento, cotizacion)
        self.assertEqual(
            candidatos["codigo"].tolist(),
            ["GM-12-18A", "TM-16A"],
        )
        self.assertTrue(
            (candidatos["corriente_seleccion"] >= 15.4).all()
        )

    def test_circuitos_derivados_reserva_resultados_para_ambos_tipos(self):
        from modules.inventario import guardar_componentes
        from modules.seleccion_componentes import (
            buscar_candidatos, generar_requerimientos, obtener_cotizacion,
        )
        base = {
            "unidad": "und", "stock": 5, "stock_minimo": 0,
            "costo_unitario": 100, "moneda": "PEN", "proveedor": "",
            "ubicacion": "", "estado": "Activo", "observaciones": "",
            "marca": "Prueba",
        }
        protecciones = [
            {
                **base, "codigo": f"GM-{corriente}A",
                "descripcion": f"Guardamotor regulable 10-{corriente} A",
                "categoria": "Guardamotores", "modelo": f"GM{corriente}",
                "corriente_nominal": corriente,
            }
            for corriente in range(16, 25)
        ]
        protecciones.extend([
            {
                **base, "codigo": "TM-20A",
                "descripcion": "Interruptor termomagnético 3P C 20AMP 10KA",
                "categoria": "Protecciones y maniobra", "modelo": "P1MB3PC20",
                "corriente_nominal": 0,
            },
            {
                **base, "codigo": "TM-25A",
                "descripcion": "Interruptor magnetotérmico 3P C 25AMP 10KA",
                "categoria": "Protecciones y maniobra", "modelo": "P1MB3PC25",
                "corriente_nominal": 0,
            },
        ])
        guardar_componentes(pd.DataFrame(protecciones))
        creada = self._crear_cotizacion()
        cotizacion = obtener_cotizacion(creada["id"])
        requerimiento = next(
            item for item in generar_requerimientos(cotizacion)
            if item["grupo"] == "Circuitos derivados"
        )
        candidatos = buscar_candidatos(requerimiento, cotizacion)
        codigos = candidatos["codigo"].tolist()
        self.assertIn("TM-20A", codigos)
        self.assertIn("TM-25A", codigos)
        self.assertEqual(
            set(candidatos["tipo_proteccion"]),
            {"Guardamotor", "Interruptor termomagnético"},
        )
        self.assertTrue(
            (candidatos["corriente_seleccion"] >= 15.4).all()
        )

    def test_circuitos_derivados_descarta_interruptores_con_polos_incorrectos(self):
        from modules.inventario import guardar_componentes
        from modules.seleccion_componentes import (
            buscar_candidatos, generar_requerimientos, obtener_cotizacion,
        )
        base = {
            "unidad": "und", "stock": 5, "stock_minimo": 0,
            "costo_unitario": 100, "corriente_nominal": 20,
            "moneda": "PEN", "proveedor": "", "ubicacion": "",
            "estado": "Activo", "observaciones": "", "marca": "Prueba",
            "categoria": "Interruptores termomagnéticos",
        }
        guardar_componentes(pd.DataFrame([
            {
                **base, "codigo": "TM-1P",
                "descripcion": "Interruptor termomagnético 1P C 20AMP",
                "modelo": "M1P",
            },
            {
                **base, "codigo": "TM-2P",
                "descripcion": "Interruptor termomagnético 2P C 20AMP",
                "modelo": "M2P",
            },
            {
                **base, "codigo": "TM-3P",
                "descripcion": "Interruptor termomagnético 3P C 20AMP",
                "modelo": "M3P",
            },
            {
                **base, "codigo": "TM-4P",
                "descripcion": "Interruptor termomagnético 4P C 20AMP",
                "modelo": "M4P",
            },
        ]))
        creada = self._crear_cotizacion()
        cotizacion = obtener_cotizacion(creada["id"])
        requerimiento = next(
            item for item in generar_requerimientos(cotizacion)
            if item["grupo"] == "Circuitos derivados"
        )
        candidatos = buscar_candidatos(requerimiento, cotizacion)
        self.assertEqual(candidatos["codigo"].tolist(), ["TM-3P"])

    def test_accesorios_puerta_filtra_tipo_y_color(self):
        from modules.inventario import guardar_componentes
        from modules.seleccion_componentes import (
            buscar_candidatos, generar_requerimientos, obtener_cotizacion,
        )
        base = {
            "unidad": "und", "stock": 10, "stock_minimo": 0,
            "costo_unitario": 20, "corriente_nominal": 0,
            "moneda": "PEN", "proveedor": "", "ubicacion": "",
            "estado": "Activo", "observaciones": "", "marca": "Prueba",
            "categoria": "Mando y señalización",
        }
        guardar_componentes(pd.DataFrame([
            {
                **base, "codigo": "SEL-MOA",
                "descripcion": "Selector Man-0-Aut, 1 Polo, 16A",
                "modelo": "SEL1",
            },
            {
                **base, "codigo": "PIL-VERDE",
                "descripcion": "Piloto de señalizacion PVC verde 22mm 220VAC",
                "modelo": "PV",
            },
            {
                **base, "codigo": "PIL-ROJO",
                "descripcion": "Piloto de señalizacion PVC rojo 22mm 220VAC",
                "modelo": "PR",
            },
            {
                **base, "codigo": "PIL-AMARILLO",
                "descripcion": "Piloto de señalizacion PVC amarilla 22mm 220VAC",
                "modelo": "PA",
            },
            {
                **base, "codigo": "PUL-ROJO",
                "descripcion": "Pulsador rasante metal rojo 22mm",
                "modelo": "BR",
            },
            {
                **base, "codigo": "CAB-ROJO",
                "descripcion": "Cabezal piloto rojo",
                "modelo": "CR",
            },
        ]))
        creada = self._crear_cotizacion()
        cotizacion = obtener_cotizacion(creada["id"])
        requerimientos = {
            item["grupo"]: item
            for item in generar_requerimientos(cotizacion)
        }
        esperados = {
            "Accesorios de puerta - Conmutadores": ["SEL-MOA"],
            "Accesorios de puerta - Pilotos verdes": ["PIL-VERDE"],
            "Accesorios de puerta - Pilotos rojos": ["PIL-ROJO"],
            "Accesorios de puerta - Piloto ámbar": ["PIL-AMARILLO"],
        }
        for grupo, codigos in esperados.items():
            candidatos = buscar_candidatos(
                requerimientos[grupo], cotizacion
            )
            self.assertEqual(candidatos["codigo"].tolist(), codigos)

    def test_circuito_control_filtra_componentes_y_calcula_distribucion(self):
        from modules.inventario import guardar_componentes
        from modules.cotizaciones import registrar_cliente, registrar_cotizacion
        from modules.seleccion_componentes import (
            buscar_candidatos, generar_requerimientos, obtener_cotizacion,
        )
        base = {
            "unidad": "und", "stock": 10, "stock_minimo": 0,
            "costo_unitario": 20, "moneda": "PEN", "proveedor": "",
            "ubicacion": "", "estado": "Activo", "observaciones": "",
            "marca": "Prueba",
        }
        guardar_componentes(pd.DataFrame([
            {
                **base, "codigo": "FUS-10A",
                "descripcion": "Fusible cilindro 10X38 10AMP",
                "categoria": "Fusibles", "modelo": "F10",
                "corriente_nominal": 10,
            },
            {
                **base, "codigo": "PF-10X38",
                "descripcion": "Base para fusible 1P 10X38",
                "categoria": "Portafusibles", "modelo": "PF1",
                "corriente_nominal": 0,
            },
            {
                **base, "codigo": "REL-24DC",
                "descripcion": "Relé auxiliar enchufable bobina 24VDC",
                "categoria": "Relés auxiliares", "modelo": "R24",
                "corriente_nominal": 0,
            },
            {
                **base, "codigo": "REL-220AC",
                "descripcion": "Relé auxiliar enchufable bobina 220VAC",
                "categoria": "Relés auxiliares", "modelo": "R220",
                "corriente_nominal": 0,
            },
            {
                **base, "codigo": "DIST-40A",
                "descripcion": "Bloque de distribución 4 polos 40A",
                "categoria": "Distribución", "modelo": "D40",
                "corriente_nominal": 40,
            },
            {
                **base, "codigo": "DIST-63A",
                "descripcion": "Bloque repartidor de potencia 4 polos 63A",
                "categoria": "Distribución", "modelo": "D63",
                "corriente_nominal": 63,
            },
            {
                **base, "codigo": "DIST-80A",
                "descripcion": "Bloque repartidor de potencia 4 polos 80A",
                "categoria": "Distribución", "modelo": "D80",
                "corriente_nominal": 80,
            },
            {
                **base, "codigo": "DIST-100A",
                "descripcion": "Bloque de distribución 4 polos 100A",
                "categoria": "Distribución", "modelo": "D100",
                "corriente_nominal": 100,
            },
        ]))
        cliente = registrar_cliente({
            "tipo_documento": "RUC", "numero_documento": "20999999999",
            "razon_social": "Cliente 3 bombas", "contacto": "",
            "telefono": "", "correo": "", "direccion": "",
        })
        creada = registrar_cotizacion(cliente, {
            "proyecto": "Presión constante", "cantidad_bombas": 3,
            "potencia_hp": 5.0, "corriente_motor": 14.0,
            "tension": 220, "fases": 3, "altitud_msnm": 2000,
            "tipo_control": "Un variador por bomba",
            "presion_trabajo": 4.0, "unidad_presion": "bar",
            "senal_sensor": "4-20 mA", "observaciones": "",
        })
        cotizacion = obtener_cotizacion(creada["id"])
        requerimientos = {
            item["grupo"]: item
            for item in generar_requerimientos(cotizacion)
        }
        self.assertEqual(
            requerimientos["Circuito de control - Fusibles"]["cantidad"], 4
        )
        self.assertEqual(
            requerimientos["Circuito de control - Portafusibles"]["cantidad"],
            4,
        )
        self.assertEqual(
            requerimientos[
                "Circuito de control - Relés auxiliares 24 VDC"
            ]["cantidad"],
            3,
        )
        distribucion = requerimientos[
            "Circuito de potencia - Cuadros de distribución"
        ]
        self.assertEqual(distribucion["cantidad"], 3)
        self.assertAlmostEqual(distribucion["corriente_requerida"], 46.2)
        esperados = {
            "Circuito de control - Fusibles": ["FUS-10A"],
            "Circuito de control - Portafusibles": ["PF-10X38"],
            "Circuito de control - Relés auxiliares 24 VDC": ["REL-24DC"],
            "Circuito de potencia - Cuadros de distribución": [
                "DIST-63A", "DIST-80A"
            ],
        }
        for grupo, codigos in esperados.items():
            candidatos = buscar_candidatos(
                requerimientos[grupo], cotizacion
            )
            self.assertEqual(candidatos["codigo"].tolist(), codigos)

    def test_sistema_alarma_agrega_y_filtra_componentes_220v_na(self):
        from modules.inventario import guardar_componentes
        from modules.seleccion_componentes import (
            buscar_candidatos, generar_requerimientos, obtener_cotizacion,
        )
        base = {
            "unidad": "und", "stock": 5, "stock_minimo": 0,
            "costo_unitario": 30, "corriente_nominal": 0,
            "moneda": "PEN", "proveedor": "", "ubicacion": "",
            "estado": "Activo", "observaciones": "", "marca": "Prueba",
            "categoria": "Mando y señalización",
        }
        guardar_componentes(pd.DataFrame([
            {
                **base, "codigo": "SIR-220",
                "descripcion": "Motor sirena roja 220V", "modelo": "S220",
            },
            {
                **base, "codigo": "SIR-24",
                "descripcion": "Sirena industrial 24VDC", "modelo": "S24",
            },
            {
                **base, "codigo": "REL-220",
                "descripcion": "Relé auxiliar enchufable bobina 220VAC",
                "modelo": "R220",
            },
            {
                **base, "codigo": "REL-24",
                "descripcion": "Relé auxiliar enchufable bobina 24VDC",
                "modelo": "R24",
            },
            {
                **base, "codigo": "PUL-NA",
                "descripcion": "Pulsador rasante verde 22mm 1NA",
                "modelo": "PNA",
            },
            {
                **base, "codigo": "PUL-NC",
                "descripcion": "Pulsador rasante rojo 22mm 1NC",
                "modelo": "PNC",
            },
            {
                **base, "codigo": "CAB-NA",
                "descripcion": "Cabezal pulsador verde 1NA",
                "modelo": "CNA",
            },
        ]))
        creada = self._crear_cotizacion(con_alarma=True)
        cotizacion = obtener_cotizacion(creada["id"])
        requerimientos = {
            item["grupo"]: item
            for item in generar_requerimientos(cotizacion)
        }
        esperados = {
            "Sistema de alarma - Sirena 220 V": ["SIR-220"],
            "Sistema de alarma - Relé auxiliar 220 V": ["REL-220"],
            "Sistema de alarma - Pulsador NA": ["PUL-NA"],
        }
        for grupo, codigos in esperados.items():
            self.assertEqual(requerimientos[grupo]["cantidad"], 1)
            candidatos = buscar_candidatos(
                requerimientos[grupo], cotizacion
            )
            self.assertEqual(candidatos["codigo"].tolist(), codigos)

    def test_contraincendio_softstarter_filtra_protecciones_y_mando(self):
        from modules.inventario import guardar_componentes
        from modules.seleccion_componentes import (
            buscar_candidatos,
            generar_requerimientos,
        )

        base = {
            "unidad": "und", "stock": 10, "stock_minimo": 0,
            "costo_unitario": 30, "moneda": "PEN", "proveedor": "",
            "ubicacion": "", "estado": "Activo", "observaciones": "",
            "marca": "Prueba", "modelo": "",
        }
        componentes = []
        for codigo, amperios in [
            ("INT-3P-10", 10), ("INT-3P-16", 16), ("INT-3P-50", 50),
            ("INT-3P-63", 63), ("INT-3P-80", 80),
        ]:
            componentes.append({
                **base, "codigo": codigo,
                "descripcion": f"Interruptor termomagnético trifásico 3P {amperios}A",
                "categoria": "Interruptores",
                "corriente_nominal": amperios,
            })
        componentes.extend([
            {
                **base, "codigo": "INT-1P-10",
                "descripcion": "Interruptor termomagnético monopolar 1P 10A",
                "categoria": "Interruptores", "corriente_nominal": 10,
            },
            {
                **base, "codigo": "INT-4P-50",
                "descripcion": "Interruptor termomagnético tetrapolar 4P 50A",
                "categoria": "Interruptores", "corriente_nominal": 50,
            },
            {
                **base, "codigo": "CON-9",
                "descripcion": "Contactor de potencia AC-3 9A",
                "categoria": "Contactores", "corriente_nominal": 9,
            },
            {
                **base, "codigo": "CON-12",
                "descripcion": "Contactor de potencia AC-3 12A",
                "categoria": "Contactores", "corriente_nominal": 12,
            },
            {
                **base, "codigo": "REL-7-10",
                "descripcion": "Relé térmico regulable 7-10A",
                "categoria": "Relés térmicos", "corriente_nominal": 0,
            },
            {
                **base, "codigo": "REL-9-13",
                "descripcion": "Relé térmico regulable 9-13A",
                "categoria": "Relés térmicos", "corriente_nominal": 0,
            },
            {
                **base, "codigo": "FUS-CONTROL",
                "descripcion": "Fusible cilíndrico de control 10x38",
                "categoria": "Fusibles", "corriente_nominal": 0,
            },
            {
                **base, "codigo": "PF-CONTROL",
                "descripcion": "Portafusible modular 10x38",
                "categoria": "Portafusibles", "corriente_nominal": 0,
            },
            {
                **base, "codigo": "RA-220",
                "descripcion": "Relé auxiliar enchufable bobina 220VAC",
                "categoria": "Relés auxiliares", "corriente_nominal": 0,
            },
            {
                **base, "codigo": "RA-24",
                "descripcion": "Relé auxiliar enchufable bobina 24VDC",
                "categoria": "Relés auxiliares", "corriente_nominal": 0,
            },
            {
                **base, "codigo": "BASE-RA-220",
                "descripcion": "Base de relé auxiliar enchufable 220VAC",
                "categoria": "Accesorios", "corriente_nominal": 0,
            },
            {
                **base, "codigo": "TIM-1",
                "descripcion": "Temporizador electrónico multifunción",
                "categoria": "Temporizadores", "corriente_nominal": 0,
            },
            {
                **base, "codigo": "BASE-TIM",
                "descripcion": "Base para timer electrónico",
                "categoria": "Accesorios", "corriente_nominal": 0,
            },
        ])
        accesorios = [
            ("PIL-AM", "Piloto de señalización amarillo 22mm"),
            ("PIL-VE", "Piloto de señalización verde 22mm"),
            ("PIL-RO", "Piloto de señalización rojo 22mm"),
            ("CONM", "Conmutador selector de puerta 2 posiciones"),
            ("PUL-NA", "Pulsador rasante verde 1NA"),
            ("PUL-NC", "Pulsador rasante rojo 1NC"),
        ]
        for codigo, descripcion in accesorios:
            componentes.append({
                **base, "codigo": codigo, "descripcion": descripcion,
                "categoria": "Mando y señalización", "corriente_nominal": 0,
            })
        guardar_componentes(pd.DataFrame(componentes))

        cotizacion = {
            "tipo_tablero": "Contraincendio",
            "tipo_control": "Softstarter",
            "potencia_hp": 15,
            "corriente_motor": 30,
            "potencia_jockey_hp": 3,
            "corriente_jockey": 8,
            "altitud_msnm": 2000,
            "tension": 380,
            "fases": 3,
            "cantidad_bombas": 2,
        }
        requerimientos = {
            item["grupo"]: item
            for item in generar_requerimientos(cotizacion)
        }
        self.assertAlmostEqual(
            requerimientos["Protección general contraincendio"][
                "corriente_requerida"
            ],
            41.8,
        )
        self.assertAlmostEqual(
            requerimientos["Protección trifásica de bomba jockey"][
                "corriente_requerida"
            ],
            8.8,
        )
        esperados = {
            "Protección general contraincendio": ["INT-3P-50", "INT-3P-63"],
            "Protección trifásica de bomba jockey": ["INT-3P-10", "INT-3P-16"],
            "Contactor de bomba jockey": ["CON-9", "CON-12"],
            "Relé térmico de bomba jockey": ["REL-7-10"],
            "Accesorios de control - Fusibles": ["FUS-CONTROL"],
            "Accesorios de control - Portafusibles": ["PF-CONTROL"],
            "Accesorios de control - Relés auxiliares 220 V": ["RA-220"],
            "Accesorios de control - Temporizadores": ["TIM-1"],
            "Accesorios de puerta - Piloto amarillo": ["PIL-AM"],
            "Accesorios de puerta - Pilotos verdes": ["PIL-VE"],
            "Accesorios de puerta - Pilotos rojos": ["PIL-RO"],
            "Accesorios de puerta - Conmutador": ["CONM"],
            "Accesorios de puerta - Pulsador NA": ["PUL-NA"],
            "Accesorios de puerta - Pulsador NC": ["PUL-NC"],
        }
        cantidades = {
            "Accesorios de puerta - Piloto amarillo": 1,
            "Accesorios de puerta - Pilotos verdes": 2,
            "Accesorios de puerta - Pilotos rojos": 3,
            "Accesorios de puerta - Conmutador": 1,
            "Accesorios de puerta - Pulsador NA": 1,
            "Accesorios de puerta - Pulsador NC": 1,
            "Accesorios de control - Fusibles": 2,
            "Accesorios de control - Portafusibles": 2,
            "Accesorios de control - Relés auxiliares 220 V": 3,
            "Accesorios de control - Temporizadores": 2,
        }
        for grupo, codigos in esperados.items():
            candidatos = buscar_candidatos(requerimientos[grupo], cotizacion)
            self.assertEqual(candidatos["codigo"].tolist(), codigos)
        for grupo, cantidad in cantidades.items():
            self.assertEqual(requerimientos[grupo]["cantidad"], cantidad)

        cotizacion["corriente_jockey"] = 14
        requerimientos_aproximados = {
            item["grupo"]: item
            for item in generar_requerimientos(cotizacion)
        }
        rele_aproximado = buscar_candidatos(
            requerimientos_aproximados["Relé térmico de bomba jockey"],
            cotizacion,
        )
        self.assertEqual(rele_aproximado["codigo"].tolist(), ["REL-9-13"])
        self.assertGreater(rele_aproximado.iloc[0]["distancia_corriente"], 0)

    def test_contraincendio_estrella_triangulo_espera_reglas_especificas(self):
        from modules.seleccion_componentes import generar_requerimientos

        cotizacion = {
            "tipo_tablero": "Contraincendio",
            "tipo_control": "Estrella-triángulo",
            "potencia_hp": 15,
            "corriente_motor": 30,
            "potencia_jockey_hp": 3,
            "corriente_jockey": 8,
            "altitud_msnm": 0,
            "tension": 220,
            "fases": 3,
            "cantidad_bombas": 2,
        }
        self.assertEqual(generar_requerimientos(cotizacion), [])


if __name__ == "__main__":
    unittest.main()
