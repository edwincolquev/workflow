"""Permisos generales del portal, independientes de los roles de Workflow."""

LECTURA = "Lectura"
ESCRITURA = "Escritura"
TOTAL = "Total"
ACCESS_LEVELS = (LECTURA, ESCRITURA, TOTAL)


def access_level(user):
    if not user:
        return None
    value = user.get("access_level", ESCRITURA)
    return value if value in ACCESS_LEVELS else LECTURA


def can_write(user):
    return access_level(user) in (ESCRITURA, TOTAL)


def can_manage(user):
    return access_level(user) == TOTAL


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
