# Clasificación y gestión comercial

Cada repuesto puede tener una unidad de medida, una marca comercial y una categoría de esa marca. Las marcas comerciales se administran en `marcas_repuestos`; las marcas de vehículos siguen en `marcas_vehiculos`. Una marca comercial puede tener muchas categorías y cada repuesto tiene como máximo una.

Los precios de compra y venta son unitarios y se registran en **dólares estadounidenses (USD)**. Las cantidades usan la unidad del repuesto y admiten decimales para metros u otras unidades fraccionables.

## Flujo de trabajo

El operador puede seleccionar cualquier estado en cualquier momento, incluso retroceder desde En SAP o Rechazado. El Código SAP es opcional. Los estados son Propuesto, En cotización, Pendiente de aprobación, Aprobado, Pedido, En SAP y Rechazado.

En la pantalla, los importes y cantidades comerciales de un artículo En SAP permanecen bloqueados hasta cambiarlo a otro estado. La plantilla Excel puede modificarlos directamente mediante una función privada de Supabase, mientras el trigger continúa bloqueando actualizaciones SQL ordinarias. Si una importación nueva no informa estado, se usa En SAP cuando tiene Código SAP; de lo contrario, Propuesto. Un estado vacío en un repuesto existente conserva su estado actual.

`historial_estados` registra el estado inicial y cada cambio con su fecha. Repetir un mismo estado no duplica el historial. `repuestos.fecha_actualizacion_estado` guarda la fecha del último cambio y se actualiza automáticamente; la vista y el Excel la muestran sin permitir editarla. Los estados se registran por el operador.

## Campos para el maestro

En la pestaña Importar se descarga un maestro de datos técnicos, OEM, referencias, aplicaciones y clasificación. El estado, mínimo de compra, precios y cantidad de compra se trabajan en Hoja de trabajo. Los archivos maestro anteriores siguen siendo compatibles, pero esas cinco columnas se ignoran aunque aparezcan en el archivo. Los repuestos nuevos importados empiezan en Propuesto.

| Encabezado | Uso |
| --- | --- |
| `repuestos.codigo_proveedor` | Identifica el repuesto en todas las cargas. |
| `unidades_medida.nombre` | Pieza, Juego, Metro u otra unidad administrada por el usuario. |
| `marcas_repuestos.nombre` | Marca comercial del repuesto. También se acepta `repuestos.nombre_marca` y los alias anteriores. |
| `categorias_repuestos.nombre` | Categoría dentro de la marca comercial. Requiere una marca nueva o ya asignada al repuesto. |

En el CSV se aceptan punto o coma decimal, sin separadores de miles. Las celdas vacías conservan el valor existente; cero es un valor informado. Las listas de unidades, marcas y categorías se reutilizan por nombre, ignorando mayúsculas y espacios externos. Las categorías se reutilizan dentro de su marca. Al cambiar la marca del repuesto, se retira la categoría anterior para que pueda elegirse una de la nueva marca.

Los errores de datos técnicos aparecen durante la preparación. Si alguna fila falla al confirmar, se revierte toda la confirmación del lote.

## Uso en Streamlit

1. En Clasificación, crear o editar unidades, marcas comerciales y categorías. Un valor en uso no puede eliminarse.
2. Crear el repuesto con sus datos técnicos, clasificación y datos comerciales disponibles.
3. Abrir el repuesto y usar Guardar clasificación y gestión para completar cantidades, precios y elegir el estado.
4. Consultar Historial de estados y filtrar el catálogo por etapa.
5. Usar la plantilla Excel para corregir importes comerciales de artículos En SAP cuando corresponda.

## Migración

La actualización crea `catalogo.pre_gestion_comercial.sqlite3` antes de modificar una base anterior. Las marcas existentes se trasladan a `marcas_repuestos`, manteniendo la relación mediante `repuestos.marca_id`. `vista_repuestos` muestra la marca, unidad y categoría por nombre junto con todos los datos del artículo.

Los registros anteriores con código SAP se inicializan en En SAP; los demás, en Propuesto. Los nuevos importes, cantidades, unidades y categorías quedan vacíos hasta que el operador los complete. La migración conserva los identificadores y los datos técnicos y se ejecuta una sola vez.
