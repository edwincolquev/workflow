# Workflow y Catálogo

Una sola aplicación Streamlit ofrece los módulos Workflow y Catálogo con el inicio de sesión de Workflow. Ejecute desde la raíz del repositorio:

```powershell
python -m pip install -r requirements.txt
streamlit run app.py
```

## Conexiones

Configure dos cadenas PostgreSQL independientes en `.streamlit/secrets.toml` para desarrollo local, o en **Secrets** de Streamlit Community Cloud:

```toml
DATABASE_URL = "postgresql://..."          # Workflow
CATALOGO_DATABASE_URL = "postgresql://..." # Catálogo
```

`CATALOGO_DATABASE_URL` también puede definirse como variable de entorno. Catálogo exige su conexión PostgreSQL y no crea una base SQLite dentro de la aplicación integrada. Nunca suba las credenciales a Git.

## Acceso y mantenimiento

La cuenta, los roles de proceso y el permiso general se gestionan desde **Administración → Admin → Usuarios y Roles**. Los roles de proceso determinan qué tareas puede atender el usuario; el permiso general se aplica tanto a Workflow como a Catálogo:

| Permiso | Alcance |
| --- | --- |
| Lectura | Consultar, filtrar y descargar información; no puede guardar, importar, crear, modificar, eliminar ni avanzar tareas. |
| Escritura | Operaciones de Lectura y cambios de datos, conforme a los roles de Workflow. |
| Administrador | Operaciones de Escritura y acceso a la sección Admin; reservado para permisos especiales futuros. |

Todos los usuarios autenticados y activos ven Workflow y Catálogo. Solo el permiso **Administrador** muestra la sección Admin, separada de Workflow. Los roles de proceso siguen determinando qué tareas puede atender cada usuario; pueden dejarse vacíos. El antiguo rol de proceso Administrador no se asigna a usuarios: el permiso Administrador permite atender los nodos que aún lo usan internamente. Los usuarios que tenían **Total** o el rol Administrador se migran al permiso **Administrador**. Los cambios de permiso, rol o estado se aplican en el siguiente ciclo de la sesión.

El código de Catálogo integrado vive en `catalogo/`, basado en el commit `9240797` de `C:\Catalogo`. A partir de esta integración, modifique esa carpeta para los cambios que deban aparecer en el portal; el repositorio independiente `C:\Catalogo` no se sincroniza automáticamente. Las migraciones de su Supabase están en `catalogo/supabase/migrations/`. Las bases de datos permanecen separadas.
