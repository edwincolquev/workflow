-- Ajuste aplicado al rol de la función privada. En Supabase, postgres conserva
-- membresía administrativa como creador, pero no puede SET ROLE ni heredar.
revoke admin option for catalogo_excel_writer from postgres;
revoke catalogo_excel_writer from postgres;
