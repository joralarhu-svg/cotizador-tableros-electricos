# Cotizador de tableros eléctricos

Aplicación desarrollada con Python, Streamlit y SQLite para administrar el
inventario de componentes utilizados en tableros eléctricos para sistemas de
presión constante.

## Funciones disponibles

- Importación de inventario desde Excel.
- Detección automática de la fila de encabezados.
- Validación de campos obligatorios, códigos duplicados, stock y costos.
- Registro de productos nuevos y actualización por código.
- Edición de existencias, stock mínimo, costos y ubicación.
- Consulta con filtros por texto, categoría y estado.
- Alertas de stock bajo.

## Ejecución local

```bash
python -m venv .venv
```

En Windows:

```powershell
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
streamlit run app.py
```

## Archivo de inventario

El Excel debe contener una hoja `Componentes` con estas columnas:

`codigo`, `descripcion`, `categoria`, `marca`, `modelo`, `unidad`, `stock`,
`stock_minimo`, `costo_unitario`, `moneda`, `proveedor`, `ubicacion`, `estado`
y `observaciones`.

## Persistencia

SQLite es adecuado para desarrollo local. Antes de utilizar la aplicación en
producción con múltiples usuarios se migrará la base de datos a PostgreSQL.

