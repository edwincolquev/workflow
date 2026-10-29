"""Permisos generales del portal, independientes de los roles de Workflow."""

LECTURA = "Lectura"
ESCRITURA = "Escritura"
ADMINISTRADOR = "Administrador"
ACCESS_LEVELS = (LECTURA, ESCRITURA, ADMINISTRADOR)


def access_level(user):
    if not user:
        return None
    value = user.get("access_level", ESCRITURA)
    return value if value in ACCESS_LEVELS else LECTURA


def can_write(user):
    return access_level(user) in (ESCRITURA, ADMINISTRADOR)


def can_manage(user):
    return access_level(user) == ADMINISTRADOR


def effective_role_ids(db, user):
    """Include the legacy workflow Administrator task role via permission."""
    role_ids = {role.id for role in user.roles}
    if can_manage({"access_level": user.access_level}):
        from models import WorkflowRole
        admin_role = db.query(WorkflowRole).filter(WorkflowRole.name == ADMINISTRADOR).first()
        if admin_role:
            role_ids.add(admin_role.id)
    return role_ids


def current_user():
    try:
        import streamlit as st
        if st.session_state.get("authenticated"):
            return st.session_state.get("user")
    except Exception:
        pass
    return None


def require_write():
    user = current_user()
    if user is not None and not can_write(user):
        raise PermissionError("Su permiso es Lectura; no puede modificar datos.")
