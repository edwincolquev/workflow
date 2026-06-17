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
        'transitos': True,
        'inventarios': True,
        'quebrados': True,
        'nuevos': True,
        'discontinuados': True,
        'bandeja': True,
        'admin': True
    },
    'Gerencia': {
        'dashboard': True,
        'transitos': True,
        'inventarios': True,
        'quebrados': True,
        'nuevos': True,
        'discontinuados': True,
        'bandeja': True,
        'admin': False
    },
    'Compras': {
        'dashboard': True,
        'transitos': False,
        'inventarios': True,
        'quebrados': True,
        'nuevos': True,
        'discontinuados': True,
        'bandeja': True,
        'admin': False
    },
    'Importaciones': {
        'dashboard': True,
        'transitos': True,
        'inventarios': False,
        'quebrados': False,
        'nuevos': False,
        'discontinuados': False,
        'bandeja': True,
        'admin': False
    },
    'Logística': {
        'dashboard': True,
        'transitos': True,
        'inventarios': True,
        'quebrados': False,
        'nuevos': False,
        'discontinuados': False,
        'bandeja': True,
        'admin': False
    }
}
