# System roles
ROLES = [
    'Administrador',
    'Gerencia',
    'Compras',
    'Importaciones',
    'Logística'
]

# Role navigation access mapping
# True indicates the role has access to that specific page
ROLE_ACCESS = {
    'Administrador': {
        'dashboard': True,
        'bandeja': True,
        'detalle_workflow': True,
        'admin': True,
        'catalogo': True
    },
    'Gerencia': {
        'dashboard': True,
        'bandeja': True,
        'detalle_workflow': True,
        'admin': False,
        'catalogo': False
    },
    'Compras': {
        'dashboard': True,
        'bandeja': True,
        'detalle_workflow': True,
        'admin': False,
        'catalogo': True
    },
    'Importaciones': {
        'dashboard': True,
        'bandeja': True,
        'detalle_workflow': True,
        'admin': False,
        'catalogo': False
    },
    'Logística': {
        'dashboard': True,
        'bandeja': True,
        'detalle_workflow': True,
        'admin': False,
        'catalogo': False
    }
}


def has_access(user, section):
    """Use all roles assigned to a Workflow user for page authorization."""
    if not user:
        return False
    roles = user.get('roles') or ([user['role']] if user.get('role') else [])
    return any(ROLE_ACCESS.get(role, {}).get(section, False) for role in roles)
