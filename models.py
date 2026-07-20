from datetime import datetime
from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, Table, Float, Text, UniqueConstraint
from sqlalchemy.orm import relationship
from database import Base

# Many-to-many relationship table between User and Role
user_role_association = Table(
    'wf_user_role',
    Base.metadata,
    Column('user_id', Integer, ForeignKey('wf_user.id', ondelete='CASCADE'), primary_key=True),
    Column('role_id', Integer, ForeignKey('wf_role.id', ondelete='CASCADE'), primary_key=True)
)

class WorkflowRole(Base):
    __tablename__ = 'wf_role'
    id = Column(Integer, primary_key=True)
    name = Column(String(50), unique=True, nullable=False)
    description = Column(Text, nullable=True)
    
    users = relationship('WorkflowUser', secondary=user_role_association, back_populates='roles')

class WorkflowUser(Base):
    __tablename__ = 'wf_user'
    id = Column(Integer, primary_key=True)
    username = Column(String(50), unique=True, nullable=False)
    email = Column(String(100), nullable=True)
    password_hash = Column(String(255), nullable=False)
    full_name = Column(String(100), nullable=False)
    active = Column(Boolean, default=True)
    
    roles = relationship('WorkflowRole', secondary=user_role_association, back_populates='users')

class WorkflowBrand(Base):
    __tablename__ = 'wf_brand'
    id = Column(Integer, primary_key=True)
    name = Column(String(100), unique=True, nullable=False)
    u_negocio = Column(String(100), nullable=False)
    leadtime = Column(Integer, nullable=False, default=0)
    active = Column(Boolean, default=True)

class WorkflowProcess(Base):
    __tablename__ = 'wf_process'
    id = Column(Integer, primary_key=True)
    name = Column(String(100), nullable=False)
    description = Column(Text, nullable=True)
    active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    nodes = relationship('WorkflowNode', back_populates='process', cascade='all, delete-orphan')
    transitions = relationship('WorkflowTransition', back_populates='process', cascade='all, delete-orphan')
    instances = relationship('WorkflowInstance', back_populates='process', cascade='all, delete-orphan')

class WorkflowNode(Base):
    __tablename__ = 'wf_node'
    id = Column(Integer, primary_key=True)
    process_id = Column(Integer, ForeignKey('wf_process.id', ondelete='CASCADE'), nullable=False)
    name = Column(String(100), nullable=False)
    type = Column(String(20), nullable=False)  # START, TASK, DECISION, GATEWAY, NOTIFICATION, END
    description = Column(Text, nullable=True)
    sla_hours = Column(Integer, nullable=True)
    role_id = Column(Integer, ForeignKey('wf_role.id', ondelete='SET NULL'), nullable=True)
    template_file_name = Column(String(255), nullable=True)
    template_file_path = Column(String(500), nullable=True)
    erp_query_id = Column(Integer, ForeignKey('wf_erp_query.id', ondelete='SET NULL'), nullable=True)

    process = relationship('WorkflowProcess', back_populates='nodes')
    role = relationship('WorkflowRole')
    erp_query = relationship('WorkflowErpQuery')

class WorkflowTransition(Base):
    __tablename__ = 'wf_transition'
    id = Column(Integer, primary_key=True)
    process_id = Column(Integer, ForeignKey('wf_process.id', ondelete='CASCADE'), nullable=False)
    source_node_id = Column(Integer, ForeignKey('wf_node.id', ondelete='CASCADE'), nullable=False)
    action_name = Column(String(100), nullable=False)
    target_node_id = Column(Integer, ForeignKey('wf_node.id', ondelete='CASCADE'), nullable=False)

    process = relationship('WorkflowProcess', back_populates='transitions')
    source_node = relationship('WorkflowNode', foreign_keys=[source_node_id])
    target_node = relationship('WorkflowNode', foreign_keys=[target_node_id])

class WorkflowInstance(Base):
    __tablename__ = 'wf_instance'
    id = Column(Integer, primary_key=True)
    process_id = Column(Integer, ForeignKey('wf_process.id', ondelete='CASCADE'), nullable=False)
    title = Column(String(200), nullable=False)
    status = Column(String(20), default='ACTIVE')  # ACTIVE, COMPLETED, CANCELLED
    current_node_id = Column(Integer, ForeignKey('wf_node.id'), nullable=True)
    brand_id = Column(Integer, ForeignKey('wf_brand.id', ondelete='SET NULL'), nullable=True)
    external_ref = Column(String(100), nullable=True) # e.g. 'DocNum:10045' or 'ItemCode:XYZ'
    docnum = Column(String(50), nullable=True)
    internal_code = Column(String(50), unique=True, nullable=True)
    created_by_id = Column(Integer, ForeignKey('wf_user.id'), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    process = relationship('WorkflowProcess', back_populates='instances')
    current_node = relationship('WorkflowNode')
    brand = relationship('WorkflowBrand')
    created_by = relationship('WorkflowUser')
    tasks = relationship('WorkflowTask', back_populates='instance', cascade='all, delete-orphan')
    comments = relationship('WorkflowComment', back_populates='instance', cascade='all, delete-orphan')
    attachments = relationship('WorkflowAttachment', back_populates='instance', cascade='all, delete-orphan')
    history = relationship('WorkflowHistory', back_populates='instance', cascade='all, delete-orphan')

class WorkflowTask(Base):
    __tablename__ = 'wf_task'
    id = Column(Integer, primary_key=True)
    instance_id = Column(Integer, ForeignKey('wf_instance.id', ondelete='CASCADE'), nullable=False)
    node_id = Column(Integer, ForeignKey('wf_node.id'), nullable=False)
    assigned_role_id = Column(Integer, ForeignKey('wf_role.id'), nullable=False)
    assigned_user_id = Column(Integer, ForeignKey('wf_user.id'), nullable=True)
    status = Column(String(20), default='PENDING')  # PENDING, COMPLETED, CANCELLED
    sla_hours = Column(Integer, nullable=True)
    docnum = Column(String(50), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)
    completed_by_id = Column(Integer, ForeignKey('wf_user.id'), nullable=True)

    instance = relationship('WorkflowInstance', back_populates='tasks')
    node = relationship('WorkflowNode')
    assigned_role = relationship('WorkflowRole')
    assigned_user = relationship('WorkflowUser', foreign_keys=[assigned_user_id])
    completed_by = relationship('WorkflowUser', foreign_keys=[completed_by_id])

class WorkflowHistory(Base):
    __tablename__ = 'wf_history'
    id = Column(Integer, primary_key=True)
    instance_id = Column(Integer, ForeignKey('wf_instance.id', ondelete='CASCADE'), nullable=False)
    task_id = Column(Integer, ForeignKey('wf_task.id', ondelete='SET NULL'), nullable=True)
    source_node_id = Column(Integer, ForeignKey('wf_node.id', ondelete='SET NULL'), nullable=True)
    target_node_id = Column(Integer, ForeignKey('wf_node.id', ondelete='SET NULL'), nullable=True)
    user_id = Column(Integer, ForeignKey('wf_user.id'), nullable=False)
    action = Column(String(50), nullable=False)  # CREATE, TRANSITION, COMMENT, ATTACHMENT, REOPEN, CANCEL
    comment = Column(Text, nullable=True)
    timestamp = Column(DateTime, default=datetime.utcnow)

    instance = relationship('WorkflowInstance', back_populates='history')
    user = relationship('WorkflowUser')
    source_node = relationship('WorkflowNode', foreign_keys=[source_node_id])
    target_node = relationship('WorkflowNode', foreign_keys=[target_node_id])

class WorkflowComment(Base):
    __tablename__ = 'wf_comment'
    id = Column(Integer, primary_key=True)
    instance_id = Column(Integer, ForeignKey('wf_instance.id', ondelete='CASCADE'), nullable=False)
    task_id = Column(Integer, ForeignKey('wf_task.id', ondelete='SET NULL'), nullable=True)
    user_id = Column(Integer, ForeignKey('wf_user.id'), nullable=False)
    comment_text = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    instance = relationship('WorkflowInstance', back_populates='comments')
    user = relationship('WorkflowUser')

class WorkflowAttachment(Base):
    __tablename__ = 'wf_attachment'
    id = Column(Integer, primary_key=True)
    instance_id = Column(Integer, ForeignKey('wf_instance.id', ondelete='CASCADE'), nullable=False)
    task_id = Column(Integer, ForeignKey('wf_task.id', ondelete='SET NULL'), nullable=True)
    user_id = Column(Integer, ForeignKey('wf_user.id'), nullable=False)
    file_name = Column(String(255), nullable=False)
    file_path = Column(String(500), nullable=False)
    file_size = Column(Integer, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    instance = relationship('WorkflowInstance', back_populates='attachments')
    user = relationship('WorkflowUser')

class WorkflowObjective(Base):
    __tablename__ = 'wf_objective'
    id = Column(Integer, primary_key=True)
    metric_key = Column(String(50), unique=True, nullable=False)  # e.g., 'reduction_inventario'
    metric_name = Column(String(100), nullable=False)
    target_value = Column(Float, nullable=False)
    current_value = Column(Float, default=0.0)
    month_period = Column(String(7), nullable=False)  # YYYY-MM
    description = Column(Text, nullable=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class WorkflowEmailLog(Base):
    __tablename__ = 'wf_email_log'
    id = Column(Integer, primary_key=True)
    instance_id = Column(Integer, ForeignKey('wf_instance.id', ondelete='CASCADE'), nullable=False)
    task_id = Column(Integer, ForeignKey('wf_task.id', ondelete='SET NULL'), nullable=True)
    sender = Column(String(100), nullable=False)
    recipient = Column(String(100), nullable=False)
    subject = Column(String(200), nullable=False)
    body_html = Column(Text, nullable=False)
    attachments_json = Column(Text, nullable=True) # JSON list of dicts: [{"filename": "...", "size": 123}]
    sent_at = Column(DateTime, default=datetime.utcnow)
    status = Column(String(20), nullable=False)  # SENT, SIMULATED, FAILED
    error_message = Column(Text, nullable=True)

    instance = relationship('WorkflowInstance')
    task = relationship('WorkflowTask')

class WorkflowErpQuery(Base):
    __tablename__ = 'wf_erp_query'
    id = Column(Integer, primary_key=True)
    name = Column(String(100), unique=True, nullable=False)
    sql_query = Column(Text, nullable=False)
    description = Column(Text, nullable=True)

class WorkflowInstanceQueryDocNum(Base):
    __tablename__ = 'wf_instance_query_docnum'
    id = Column(Integer, primary_key=True)
    instance_id = Column(Integer, ForeignKey('wf_instance.id', ondelete='CASCADE'), nullable=False)
    query_id = Column(Integer, ForeignKey('wf_erp_query.id', ondelete='CASCADE'), nullable=False)
    docnum = Column(String(50), nullable=False)
    
    __table_args__ = (UniqueConstraint('instance_id', 'query_id', name='_instance_query_uc'),)

    instance = relationship('WorkflowInstance')
    query = relationship('WorkflowErpQuery')

