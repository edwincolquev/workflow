-- El estado es una selección libre. El historial conserva cada cambio.
alter table public.repuestos drop constraint if exists repuestos_sap_en_sap;
drop trigger if exists repuestos_estado_insertar on public.repuestos;
drop trigger if exists repuestos_estado_actualizar on public.repuestos;
drop function if exists public.validar_estado_repuesto();

-- Columna de consulta derivada del último evento; evita duplicar fechas.
create or replace view public.vista_repuestos with (security_invoker = true) as
select r.id, r.codigo_proveedor, r.codigo_sap, r.descripcion, r.medida,
       r.descripcion_larga, r.activo, r.fecha_creacion, r.fecha_actualizacion,
       r.unidad_id, r.marca_id, r.categoria_id, r.estado_gestion,
       r.minimo_compra, r.precio_compra, r.precio_venta, r.cantidad_compra,
       u.nombre as unidad, m.nombre as nombre_marca, c.nombre as categoria,
       (select h.fecha_cambio from public.historial_estados h
        where h.repuesto_id = r.id order by h.id desc limit 1) as fecha_actualizacion_estado
from public.repuestos r
left join public.unidades_medida u on u.id = r.unidad_id
left join public.marcas_repuestos m on m.id = r.marca_id
left join public.categorias_repuestos c on c.id = r.categoria_id;
