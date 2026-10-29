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

La cuenta y los roles se gestionan desde **Workflow → Admin → Usuarios y Roles**. Todos los usuarios autenticados y activos pueden usar Catálogo, incluidas sus funciones de edición e importación. Los permisos de las demás secciones se definen en `config/settings.py`; la desactivación de una cuenta se aplica en el siguiente ciclo de la sesión.

El código de Catálogo integrado vive en `catalogo/`, basado en el commit `9240797` de `C:\Catalogo`. A partir de esta integración, modifique esa carpeta para los cambios que deban aparecer en el portal; el repositorio independiente `C:\Catalogo` no se sincroniza automáticamente. Las migraciones de su Supabase están en `catalogo/supabase/migrations/`. Las bases de datos permanecen separadas.
