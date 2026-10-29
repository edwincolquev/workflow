-- Edición comercial desde Excel mediante una función de alcance limitado.
-- El rol no tiene LOGIN ni está concedido a clientes de la API. La membresía
-- administrativa del creador postgres no permite SET ROLE ni hereda permisos.
-- El trigger sigue rechazando las escrituras ordinarias en artículos En SAP.
create role catalogo_excel_writer nologin noinherit;
grant usage on schema public to catalogo_excel_writer;
grant select on public.repuestos to catalogo_excel_writer;
grant update (minimo_compra, precio_compra, precio_venta, cantidad_compra, fecha_actualizacion)
    on public.repuestos to catalogo_excel_writer;
create policy catalogo_excel_writer_select on public.repuestos
    for select to catalogo_excel_writer using (true);
create policy catalogo_excel_writer_update on public.repuestos
    for update to catalogo_excel_writer using (true) with check (true);

-- La pertenencia temporal permite crear la función con propietario NOLOGIN.
grant catalogo_excel_writer to postgres;
create schema catalogo_privado authorization catalogo_excel_writer;
set role catalogo_excel_writer;
create function catalogo_privado.actualizar_comercial_excel(
    p_id bigint, p_minimo numeric, p_compra numeric, p_venta numeric, p_cantidad numeric
) returns void
language plpgsql security definer set search_path = '' as $$
begin
    if session_user <> 'postgres' then
        raise exception 'Acceso no autorizado a importación comercial';
    end if;
    update public.repuestos
       set minimo_compra = p_minimo,
           precio_compra = p_compra,
           precio_venta = p_venta,
           cantidad_compra = p_cantidad,
           fecha_actualizacion = now()
     where id = p_id;
    if not found then
        raise exception 'El repuesto no existe';
    end if;
end;
$$;
revoke all on schema catalogo_privado from public, anon, authenticated, service_role;
revoke all on function catalogo_privado.actualizar_comercial_excel(bigint,numeric,numeric,numeric,numeric)
    from public, anon, authenticated, service_role;
grant usage on schema catalogo_privado to postgres;
grant execute on function catalogo_privado.actualizar_comercial_excel(bigint,numeric,numeric,numeric,numeric)
    to postgres;
reset role;
revoke catalogo_excel_writer from postgres;

create or replace function public.validar_comercial_repuesto()
returns trigger language plpgsql set search_path = '' as $$
begin
    if old.estado_gestion = 'en_sap' and (
        new.minimo_compra is distinct from old.minimo_compra or
        new.precio_compra is distinct from old.precio_compra or
        new.precio_venta is distinct from old.precio_venta or
        new.cantidad_compra is distinct from old.cantidad_compra
    ) and current_user <> 'catalogo_excel_writer' then
        raise exception 'El seguimiento comercial esta cerrado en SAP';
    end if;
    return new;
end;
$$;
