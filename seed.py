import hashlib
from database import get_db, init_db
from models import (
    WorkflowRole, WorkflowUser, WorkflowProcess, WorkflowNode, 
    WorkflowTransition, WorkflowObjective
)

def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode('utf-8')).hexdigest()

def seed_data():
    print("Inicializando base de datos...")
    init_db()
    
    with get_db() as db:
        # 1. Seeding Roles
        roles_names = ['Administrador', 'Gerencia', 'Compras', 'Importaciones', 'Logística']
        roles_dict = {}
        for role_name in roles_names:
            role = db.query(WorkflowRole).filter(WorkflowRole.name == role_name).first()
            if not role:
                role = WorkflowRole(name=role_name, description=f"Rol de {role_name}")
                db.add(role)
                db.flush()
            roles_dict[role_name] = role

        # 2. Seeding Users
        users_data = [
            ('admin', 'admin@empresa.com', 'admin123', 'Administrador Principal', 'Administrador'),
            ('gerente', 'gerente@empresa.com', 'gerente123', 'Gerente General', 'Gerencia'),
            ('comprador', 'compras@empresa.com', 'compras123', 'Comprador Senior', 'Compras'),
            ('importador', 'importaciones@empresa.com', 'import123', 'Coordinador de Importaciones', 'Importaciones'),
            ('logistico', 'logistica@empresa.com', 'logistica123', 'Supervisor de Logística', 'Logística')
        ]
        
        for username, email, password, full_name, role_name in users_data:
            user = db.query(WorkflowUser).filter(WorkflowUser.username == username).first()
            if not user:
                user = WorkflowUser(
                    username=username,
                    email=email,
                    password_hash=hash_password(password),
                    full_name=full_name,
                    active=True
                )
                user.roles.append(roles_dict[role_name])
                # Grant Administrador also to user admin
                db.add(user)
        
        # 3. Seeding Process 1: Importaciones
        proc_imp = db.query(WorkflowProcess).filter(WorkflowProcess.name == "Importaciones").first()
        if not proc_imp:
            proc_imp = WorkflowProcess(
                name="Importaciones", 
                description="Flujo de seguimiento de Importaciones desde Oferta de Compra hasta ingreso al almacén"
            )
            db.add(proc_imp)
            db.flush()
            
            # Nodes for Importaciones
            nodes = {
                'start': WorkflowNode(process_id=proc_imp.id, name="Inicio", type="START", description="Punto de partida"),
                'oc': WorkflowNode(process_id=proc_imp.id, name="OC Emitida", type="TASK", description="Se revisa y emite la Orden de Compra"),
                'viaje': WorkflowNode(process_id=proc_imp.id, name="Viaje Marítimo", type="TASK", description="Contenedor en tránsito en barco"),
                'aduana': WorkflowNode(process_id=proc_imp.id, name="Aduana", type="TASK", description="Trámites aduanales e internación"),
                'canal': WorkflowNode(process_id=proc_imp.id, name="Canal Rojo", type="TASK", description="Revisión exhaustiva por canal rojo en puerto"),
                'tlocal': WorkflowNode(process_id=proc_imp.id, name="Transporte Local", type="TASK", description="Traslado terrestre del contenedor al CD"),
                'almacen': WorkflowNode(process_id=proc_imp.id, name="Almacén", type="TASK", description="Recepción y conteo físico de mercadería"),
                'end': WorkflowNode(process_id=proc_imp.id, name="Ingresado", type="END", description="Carga ingresada al stock operativo")
            }
            for node in nodes.values():
                db.add(node)
            db.flush()
            
            # Transitions for Importaciones
            transitions = [
                # START -> OC Emitida (Autocompletado)
                WorkflowTransition(
                    process_id=proc_imp.id, 
                    source_node_id=nodes['start'].id, 
                    role_id=roles_dict['Administrador'].id, 
                    action_name="Auto-Iniciar", 
                    target_node_id=nodes['oc'].id, 
                    target_role_id=roles_dict['Compras'].id
                ),
                # OC Emitida -> Viaje Marítimo
                WorkflowTransition(
                    process_id=proc_imp.id, 
                    source_node_id=nodes['oc'].id, 
                    role_id=roles_dict['Compras'].id, 
                    action_name="Enviar a Viaje Marítimo", 
                    target_node_id=nodes['viaje'].id, 
                    target_role_id=roles_dict['Importaciones'].id
                ),
                # OC Emitida -> Observar OC
                WorkflowTransition(
                    process_id=proc_imp.id, 
                    source_node_id=nodes['oc'].id, 
                    role_id=roles_dict['Compras'].id, 
                    action_name="Revisar y Observar OC", 
                    target_node_id=nodes['oc'].id, 
                    target_role_id=roles_dict['Compras'].id
                ),
                # OC Emitida -> Cancelar
                WorkflowTransition(
                    process_id=proc_imp.id, 
                    source_node_id=nodes['oc'].id, 
                    role_id=roles_dict['Compras'].id, 
                    action_name="Cancelar Importación", 
                    target_node_id=nodes['end'].id, 
                    target_role_id=roles_dict['Administrador'].id
                ),
                # Viaje Marítimo -> Aduana
                WorkflowTransition(
                    process_id=proc_imp.id, 
                    source_node_id=nodes['viaje'].id, 
                    role_id=roles_dict['Importaciones'].id, 
                    action_name="Llegada a Puerto (Aduana)", 
                    target_node_id=nodes['aduana'].id, 
                    target_role_id=roles_dict['Logística'].id
                ),
                # Viaje Marítimo -> Reportar Retraso
                WorkflowTransition(
                    process_id=proc_imp.id, 
                    source_node_id=nodes['viaje'].id, 
                    role_id=roles_dict['Importaciones'].id, 
                    action_name="Reportar Retraso Marítimo", 
                    target_node_id=nodes['viaje'].id, 
                    target_role_id=roles_dict['Importaciones'].id
                ),
                # Aduana -> Transporte Local (Canal Verde)
                WorkflowTransition(
                    process_id=proc_imp.id, 
                    source_node_id=nodes['aduana'].id, 
                    role_id=roles_dict['Logística'].id, 
                    action_name="Liberar Canal Verde", 
                    target_node_id=nodes['tlocal'].id, 
                    target_role_id=roles_dict['Logística'].id
                ),
                # Aduana -> Canal Rojo
                WorkflowTransition(
                    process_id=proc_imp.id, 
                    source_node_id=nodes['aduana'].id, 
                    role_id=roles_dict['Logística'].id, 
                    action_name="Desviar a Canal Rojo", 
                    target_node_id=nodes['canal'].id, 
                    target_role_id=roles_dict['Logística'].id
                ),
                # Aduana -> Observar / Devolver
                WorkflowTransition(
                    process_id=proc_imp.id, 
                    source_node_id=nodes['aduana'].id, 
                    role_id=roles_dict['Logística'].id, 
                    action_name="Devolver a Viaje (Falta Documentos)", 
                    target_node_id=nodes['viaje'].id, 
                    target_role_id=roles_dict['Importaciones'].id
                ),
                # Canal Rojo -> Transporte Local
                WorkflowTransition(
                    process_id=proc_imp.id, 
                    source_node_id=nodes['canal'].id, 
                    role_id=roles_dict['Logística'].id, 
                    action_name="Liberar de Canal Rojo", 
                    target_node_id=nodes['tlocal'].id, 
                    target_role_id=roles_dict['Logística'].id
                ),
                # Canal Rojo -> Devolver a Aduana
                WorkflowTransition(
                    process_id=proc_imp.id, 
                    source_node_id=nodes['canal'].id, 
                    role_id=roles_dict['Logística'].id, 
                    action_name="Devolver a Aduana (Ajustar Trámite)", 
                    target_node_id=nodes['aduana'].id, 
                    target_role_id=roles_dict['Logística'].id
                ),
                # Transporte Local -> Almacén
                WorkflowTransition(
                    process_id=proc_imp.id, 
                    source_node_id=nodes['tlocal'].id, 
                    role_id=roles_dict['Logística'].id, 
                    action_name="Entregar Contenedor a Almacén", 
                    target_node_id=nodes['almacen'].id, 
                    target_role_id=roles_dict['Logística'].id
                ),
                # Almacén -> Ingresado (END)
                WorkflowTransition(
                    process_id=proc_imp.id, 
                    source_node_id=nodes['almacen'].id, 
                    role_id=roles_dict['Logística'].id, 
                    action_name="Confirmar Ingreso a Stock", 
                    target_node_id=nodes['end'].id, 
                    target_role_id=roles_dict['Gerencia'].id
                )
            ]
            for transition in transitions:
                db.add(transition)

        # 4. Seeding Process 2: Items Nuevos
        proc_new = db.query(WorkflowProcess).filter(WorkflowProcess.name == "Items Nuevos").first()
        if not proc_new:
            proc_new = WorkflowProcess(
                name="Items Nuevos", 
                description="Proceso de preparación, homologación y habilitación de nuevos SKUs en el catálogo de ventas"
            )
            db.add(proc_new)
            db.flush()
            
            # Nodes for Items Nuevos
            nodes = {
                'start': WorkflowNode(process_id=proc_new.id, name="Inicio", type="START", description="Item creado en base de datos"),
                'creado': WorkflowNode(process_id=proc_new.id, name="Item Creado", type="TASK", description="Se verifica la ficha técnica inicial"),
                'catalogo': WorkflowNode(process_id=proc_new.id, name="Preparación Catálogos", type="TASK", description="Fotos, descripciones y compatibilidades"),
                'homol': WorkflowNode(process_id=proc_new.id, name="Homologación", type="TASK", description="Certificaciones y pruebas de compatibilidad nacional"),
                'espacio': WorkflowNode(process_id=proc_new.id, name="Asignación de Espacios CDC", type="TASK", description="Definir ubicación física en rack/almacén"),
                'aprob': WorkflowNode(process_id=proc_new.id, name="Aprobación Final", type="TASK", description="Habilitar precio de lista y activar flag de ventas"),
                'end': WorkflowNode(process_id=proc_new.id, name="Item Liberado", type="END", description="Producto disponible para la venta")
            }
            for node in nodes.values():
                db.add(node)
            db.flush()
            
            # Transitions for Items Nuevos
            transitions = [
                # START -> Creado
                WorkflowTransition(
                    process_id=proc_new.id, 
                    source_node_id=nodes['start'].id, 
                    role_id=roles_dict['Administrador'].id, 
                    action_name="Habilitar Ficha", 
                    target_node_id=nodes['creado'].id, 
                    target_role_id=roles_dict['Compras'].id
                ),
                # Creado -> Catálogos
                WorkflowTransition(
                    process_id=proc_new.id, 
                    source_node_id=nodes['creado'].id, 
                    role_id=roles_dict['Compras'].id, 
                    action_name="Enviar a Preparar Catálogos", 
                    target_node_id=nodes['catalogo'].id, 
                    target_role_id=roles_dict['Compras'].id
                ),
                # Catálogos -> Homologación
                WorkflowTransition(
                    process_id=proc_new.id, 
                    source_node_id=nodes['catalogo'].id, 
                    role_id=roles_dict['Compras'].id, 
                    action_name="Enviar a Homologación", 
                    target_node_id=nodes['homol'].id, 
                    target_role_id=roles_dict['Logística'].id
                ),
                # Homologación -> Espacios
                WorkflowTransition(
                    process_id=proc_new.id, 
                    source_node_id=nodes['homol'].id, 
                    role_id=roles_dict['Logística'].id, 
                    action_name="Aprobar Certificación", 
                    target_node_id=nodes['espacio'].id, 
                    target_role_id=roles_dict['Logística'].id
                ),
                # Homologación -> Observar (devuelve a Item Creado)
                WorkflowTransition(
                    process_id=proc_new.id, 
                    source_node_id=nodes['homol'].id, 
                    role_id=roles_dict['Logística'].id, 
                    action_name="Observar Ficha Técnica", 
                    target_node_id=nodes['creado'].id, 
                    target_role_id=roles_dict['Compras'].id
                ),
                # Espacios -> Aprobación Final
                WorkflowTransition(
                    process_id=proc_new.id, 
                    source_node_id=nodes['espacio'].id, 
                    role_id=roles_dict['Logística'].id, 
                    action_name="Definir Ubicación Almacén", 
                    target_node_id=nodes['aprob'].id, 
                    target_role_id=roles_dict['Gerencia'].id
                ),
                # Aprobación Final -> Liberado (END)
                WorkflowTransition(
                    process_id=proc_new.id, 
                    source_node_id=nodes['aprob'].id, 
                    role_id=roles_dict['Gerencia'].id, 
                    action_name="Aprobar y Publicar Item", 
                    target_node_id=nodes['end'].id, 
                    target_role_id=roles_dict['Gerencia'].id
                ),
                # Aprobación Final -> Devolver a Espacios
                WorkflowTransition(
                    process_id=proc_new.id, 
                    source_node_id=nodes['aprob'].id, 
                    role_id=roles_dict['Gerencia'].id, 
                    action_name="Rechazar Espacio Asignado", 
                    target_node_id=nodes['espacio'].id, 
                    target_role_id=roles_dict['Logística'].id
                )
            ]
            for transition in transitions:
                db.add(transition)

        # 5. Seeding KPIs/Objectives
        kpis = [
            ('reduction_inventario', 'Reducir sobrestock global', 10.0, 4.2, '2026-06', 'Reducción del capital inmovilizado en exceso de inventario'),
            ('target_ici', 'Incrementar Índice de Calidad de Inventario (ICI)', 75.0, 74.5, '2026-06', 'Asegurar que el stock corresponda con artículos de alta rotación'),
            ('reduction_quiebres', 'Reducir quiebres de stock críticos', 20.0, 8.5, '2026-06', 'Disminuir la venta perdida por quiebre de items top 100')
        ]
        for key, name, target, current, period, desc in kpis:
            kpi = db.query(WorkflowObjective).filter(WorkflowObjective.metric_key == key).first()
            if not kpi:
                kpi = WorkflowObjective(
                    metric_key=key,
                    metric_name=name,
                    target_value=target,
                    current_value=current,
                    month_period=period,
                    description=desc
                )
                db.add(kpi)

        db.commit()
    print("Base de datos inicializada y poblada con éxito.")

if __name__ == "__main__":
    seed_data()
