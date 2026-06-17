import sys
import os
import tomllib
import streamlit as st

# Adjust path to find modules in workspace
sys.path.append('c:/supply_chain')

# Load secrets.toml manually
secrets_path = 'c:/supply_chain/.streamlit/secrets.toml'
if not os.path.exists(secrets_path):
    print("Error: secrets.toml not found at:", secrets_path)
    sys.exit(1)

with open(secrets_path, "rb") as f:
    secrets_data = tomllib.load(f)

# Mock st.secrets
try:
    st.secrets.update(secrets_data)
except AttributeError:
    try:
        st.secrets._secrets.update(secrets_data)
    except Exception as e:
        # fallback: mock st.secrets by monkeypatching
        class MockSecrets(dict):
            def __getattr__(self, name):
                return self.get(name)
        st.secrets = MockSecrets(secrets_data)

# Import email service AFTER mocking secrets
from services.email_service import send_email_with_attachments

print("Loaded secrets keys:", list(st.secrets.keys()))
if "email" in st.secrets:
    print("Email settings found under [email]:")
    for k in st.secrets["email"]:
        print(f"  - {k}: {'***' if 'password' in k.lower() else st.secrets['email'][k]}")
elif "email_workflow" in st.secrets:
    print("Email settings found under [email_workflow]:")
    for k in st.secrets["email_workflow"]:
        print(f"  - {k}: {'***' if 'password' in k.lower() else st.secrets['email_workflow'][k]}")
else:
    print("WARNING: Neither [email] nor [email_workflow] found in secrets!")

# Test recipient
to_email = "edwincolquev@gmail.com"
print(f"\nSending test email to: {to_email}")

# Empty the simulated emails directory or note current state to check if a new simulator file was created
sim_dir = 'c:/supply_chain/uploads/simulated_emails'
existing_files = set(os.listdir(sim_dir)) if os.path.exists(sim_dir) else set()

send_email_with_attachments(
    to_email=to_email,
    subject="PRUEBA SMTP REAL",
    html_content="""
    <html>
      <body>
        <h3>Conexión SMTP exitosa</h3>
        <p>Este es un correo de prueba enviado directamente desde el script de diagnóstico.</p>
      </body>
    </html>
    """
)

# Check if a new simulated file was generated
new_files = set(os.listdir(sim_dir)) if os.path.exists(sim_dir) else set()
diff_files = new_files - existing_files

if diff_files:
    print("\n[FALLBACK] El correo no pudo enviarse y cayó en el SIMULADOR:")
    for f in diff_files:
        print("-", f)
    print("\nPor favor revisa la consola de salida arriba para ver si hay mensajes de error de conexión SMTP.")
else:
    print("\n[OK] ¡El correo se envió a través del servidor SMTP real! (No se generó archivo en el simulador)")
