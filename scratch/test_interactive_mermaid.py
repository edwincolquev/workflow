import sys
import os
sys.path.append('c:/supply_chain')

from database import get_db
from models import WorkflowProcess, WorkflowNode, WorkflowTransition
from components.ui_helpers import UIHelpers

def test_mermaid():
    print("Testing render_interactive_mermaid...")
    with get_db() as db:
        proc = db.query(WorkflowProcess).first()
        if not proc:
            print("No processes found.")
            return
        
        nodes = db.query(WorkflowNode).filter(WorkflowNode.process_id == proc.id).all()
        transitions = db.query(WorkflowTransition).filter(WorkflowTransition.process_id == proc.id).all()
        
        print(f"Loaded process '{proc.name}' with {len(nodes)} nodes and {len(transitions)} transitions.")
        
        # Test method call without rendering to streamlit UI (st.components.v1.html mock/execution)
        # We verify node details generation and mermaid string creation
        try:
            import streamlit as st
            # Run
            UIHelpers.render_interactive_mermaid(nodes, transitions)
            print("SUCCESS: render_interactive_mermaid executed cleanly.")
        except Exception as ex:
            print(f"Error during execution: {ex}")

if __name__ == "__main__":
    test_mermaid()
