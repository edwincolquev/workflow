-- URL opcional de la foto referencial obtenida durante el scraping.
alter table public.repuestos
    add column if not exists imagen text;

create or replace view public.vista_repuestos with (security_invoker = true) as
select r.id, r.codigo_proveedor, r.codigo_sap, r.descripcion, r.medida,
       r.descripcion_larga, r.activo, r.fecha_creacion, r.fecha_actualizacion,
       r.unidad_id, r.marca_id, r.categoria_id, r.estado_gestion,
       r.minimo_compra, r.precio_compra, r.precio_venta, r.cantidad_compra,
       u.nombre as unidad, m.nombre as nombre_marca, c.nombre as categoria,
       r.fecha_actualizacion_estado, r.imagen
from public.repuestos r
left join public.unidades_medida u on u.id = r.unidad_id
left join public.marcas_repuestos m on m.id = r.marca_id
left join public.categorias_repuestos c on c.id = r.categoria_id;
