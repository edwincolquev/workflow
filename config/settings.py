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
        'admin': True
    },
    'Gerencia': {
        'dashboard': True,
        'bandeja': True,
        'detalle_workflow': True,
        'admin': False
    },
    'Compras': {
        'dashboard': True,
        'bandeja': True,
        'detalle_workflow': True,
        'admin': False
    },
    'Importaciones': {
        'dashboard': True,
        'bandeja': True,
        'detalle_workflow': True,
        'admin': False
    },
    'Logística': {
        'dashboard': True,
        'bandeja': True,
        'detalle_workflow': True,
        'admin': False
    }
}


def has_access(user, section):
    """Use all roles assigned to a Workflow user for page authorization."""
    if not user:
        return False
    if section == 'catalogo':
        return True
    roles = user.get('roles') or ([user['role']] if user.get('role') else [])
    return any(ROLE_ACCESS.get(role, {}).get(section, False) for role in roles)
