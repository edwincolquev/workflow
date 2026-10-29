-- Fecha física del último cambio de estado; el historial conserva todos.
alter table public.repuestos
    add column if not exists fecha_actualizacion_estado timestamptz;

update public.repuestos r
   set fecha_actualizacion_estado = coalesce(
       (select h.fecha_cambio from public.historial_estados h
        where h.repuesto_id = r.id order by h.id desc limit 1),
       r.fecha_actualizacion, now()
   )
 where r.fecha_actualizacion_estado is null;

alter table public.repuestos
    alter column fecha_actualizacion_estado set default now(),
    alter column fecha_actualizacion_estado set not null;

create function public.marcar_fecha_estado_repuesto()
returns trigger language plpgsql set search_path = '' as $$
begin
    if tg_op = 'INSERT' or new.estado_gestion is distinct from old.estado_gestion then
        new.fecha_actualizacion_estado := now();
    else
        new.fecha_actualizacion_estado := old.fecha_actualizacion_estado;
    end if;
    return new;
end;
$$;

create trigger repuestos_fecha_estado
before insert or update of estado_gestion on public.repuestos
for each row execute function public.marcar_fecha_estado_repuesto();

create or replace view public.vista_repuestos with (security_invoker = true) as
select r.id, r.codigo_proveedor, r.codigo_sap, r.descripcion, r.medida,
       r.descripcion_larga, r.activo, r.fecha_creacion, r.fecha_actualizacion,
       r.unidad_id, r.marca_id, r.categoria_id, r.estado_gestion,
       r.minimo_compra, r.precio_compra, r.precio_venta, r.cantidad_compra,
       u.nombre as unidad, m.nombre as nombre_marca, c.nombre as categoria,
       r.fecha_actualizacion_estado
from public.repuestos r
left join public.unidades_medida u on u.id = r.unidad_id
left join public.marcas_repuestos m on m.id = r.marca_id
left join public.categorias_repuestos c on c.id = r.categoria_id;
