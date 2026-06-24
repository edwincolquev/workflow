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
