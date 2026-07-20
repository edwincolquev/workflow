import sys
import os
sys.path.append(r'C:\supply_chain')

from database import SessionLocal, engine, Base, init_db
from models import WorkflowBrand, WorkflowInstance

# ... BRANDS_DATA ...


BRANDS_DATA = [
    {"name": "3M", "u_negocio": "C-MOVIL", "leadtime": 28, "active": True},
    {"name": "AFA", "u_negocio": "C-MOVIL", "leadtime": 90, "active": True},
    {"name": "ASAHI", "u_negocio": "C-MOVIL", "leadtime": 180, "active": True},
    {"name": "AUTOTRAVI", "u_negocio": "C-MOVIL", "leadtime": 120, "active": True},
    {"name": "BEN", "u_negocio": "C-MOVIL", "leadtime": 240, "active": True},
    {"name": "CAÑERIA DE COBRE", "u_negocio": "C-MOVIL", "leadtime": 110, "active": True},
    {"name": "CAÑERIA DE FRENO", "u_negocio": "C-MOVIL", "leadtime": 115, "active": True},
    {"name": "CAUPLAS", "u_negocio": "NOVAPARTES", "leadtime": 120, "active": True},
    {"name": "CHAMPION", "u_negocio": "PROLINE", "leadtime": 210, "active": True},
    {"name": "CONTROIL", "u_negocio": "NOVAPARTES", "leadtime": 90, "active": True},
    {"name": "CORCHO ENGOMADO", "u_negocio": "C-MOVIL", "leadtime": 120, "active": True},
    {"name": "CTR", "u_negocio": "NOVAPARTES", "leadtime": 195, "active": True},
    {"name": "FANADEGO", "u_negocio": "C-MOVIL", "leadtime": 120, "active": True},
    {"name": "FIC", "u_negocio": "C-MOVIL", "leadtime": 182, "active": True},
    {"name": "FLEXRITE", "u_negocio": "C-MOVIL", "leadtime": 120, "active": True},
    {"name": "FRASLE", "u_negocio": "NOVAPARTES", "leadtime": 120, "active": True},
    {"name": "FRITEC", "u_negocio": "C-MOVIL", "leadtime": 158, "active": True},
    {"name": "GATES", "u_negocio": "C-MOVIL", "leadtime": 120, "active": True},
    {"name": "GAUSS", "u_negocio": "C-MOVIL", "leadtime": 150, "active": True},
    {"name": "GMB", "u_negocio": "C-MOVIL", "leadtime": 230, "active": True},
    {"name": "GSP", "u_negocio": "C-MOVIL", "leadtime": 155, "active": True},
    {"name": "HI LITE", "u_negocio": "C-MOVIL", "leadtime": 180, "active": True},
    {"name": "HI POWER", "u_negocio": "C-MOVIL", "leadtime": 180, "active": True},
    {"name": "HO", "u_negocio": "C-MOVIL", "leadtime": 150, "active": True},
    {"name": "HP FILTROS", "u_negocio": "C-MOVIL", "leadtime": 190, "active": True},
    {"name": "HP FRENO", "u_negocio": "NOVAPARTES", "leadtime": 210, "active": True},
    {"name": "HP LIMPIAPARABRISAS", "u_negocio": "C-MOVIL", "leadtime": 210, "active": True},
    {"name": "HWC", "u_negocio": "C-MOVIL", "leadtime": 180, "active": True},
    {"name": "IMPERIAL", "u_negocio": "C-MOVIL", "leadtime": 30, "active": True},
    {"name": "KIKI", "u_negocio": "C-MOVIL", "leadtime": 30, "active": True},
    {"name": "KRUG", "u_negocio": "C-MOVIL", "leadtime": 170, "active": True},
    {"name": "LUCIFLEX", "u_negocio": "C-MOVIL", "leadtime": 90, "active": True},
    {"name": "MARILIA", "u_negocio": "C-MOVIL", "leadtime": 90, "active": True},
    {"name": "MGI", "u_negocio": "C-MOVIL", "leadtime": 210, "active": True},
    {"name": "MITSUBOSHI", "u_negocio": "C-MOVIL", "leadtime": 252, "active": True},
    {"name": "MIYACO", "u_negocio": "C-MOVIL", "leadtime": 300, "active": True},
    {"name": "MRK", "u_negocio": "C-MOVIL", "leadtime": 210, "active": True},
    {"name": "MULTILIGHT", "u_negocio": "C-MOVIL", "leadtime": 90, "active": True},
    {"name": "MUSASHI", "u_negocio": "C-MOVIL", "leadtime": 240, "active": True},
    {"name": "NGK", "u_negocio": "C-MOVIL", "leadtime": 150, "active": True},
    {"name": "NIKKO", "u_negocio": "C-MOVIL", "leadtime": 295, "active": True},
    {"name": "NOK", "u_negocio": "C-MOVIL", "leadtime": 30, "active": True},
    {"name": "NPR", "u_negocio": "C-MOVIL", "leadtime": 266, "active": True},
    {"name": "NPW", "u_negocio": "NOVAPARTES", "leadtime": 240, "active": True},
    {"name": "PEVISA", "u_negocio": "C-MOVIL", "leadtime": 150, "active": True},
    {"name": "PHC VALEO", "u_negocio": "C-MOVIL", "leadtime": 150, "active": True},
    {"name": "REI", "u_negocio": "C-MOVIL", "leadtime": 30, "active": True},
    {"name": "RHC", "u_negocio": "C-MOVIL", "leadtime": 30, "active": True},
    {"name": "SANKEI DREIK", "u_negocio": "C-MOVIL", "leadtime": 240, "active": True},
    {"name": "SEIWA", "u_negocio": "C-MOVIL", "leadtime": 30, "active": True},
    {"name": "SIL", "u_negocio": "C-MOVIL", "leadtime": 90, "active": True},
    {"name": "SORL", "u_negocio": "C-MOVIL", "leadtime": 181, "active": True},
    {"name": "SUPRENS", "u_negocio": "C-MOVIL", "leadtime": 90, "active": True},
    {"name": "TAIDO", "u_negocio": "NOVAPARTES", "leadtime": 180, "active": True},
    {"name": "TAIDO SOLENOIDES", "u_negocio": "NOVAPARTES", "leadtime": 240, "active": True},
    {"name": "TAMA", "u_negocio": "C-MOVIL", "leadtime": 30, "active": True},
    {"name": "TOYO", "u_negocio": "NOVAPARTES", "leadtime": 210, "active": True},
    {"name": "TRAMONTINA ELETRIK", "u_negocio": "N/A", "leadtime": 0, "active": False},
    {"name": "TRAMONTINA HAGALO", "u_negocio": "C-MOVIL", "leadtime": 30, "active": True},
    {"name": "TRAMONTINA MASTER", "u_negocio": "C-MOVIL", "leadtime": 60, "active": True},
    {"name": "TRAMONTINA MULTI", "u_negocio": "N/A", "leadtime": 0, "active": False},
    {"name": "TRAMONTINA PRO", "u_negocio": "C-MOVIL", "leadtime": 30, "active": True},
    {"name": "VALEO", "u_negocio": "NOVAPARTES", "leadtime": 120, "active": True},
    {"name": "VIEMAR", "u_negocio": "NOVAPARTES", "leadtime": 90, "active": True},
    {"name": "WAGNER FRENOS", "u_negocio": "PROLINE", "leadtime": 90, "active": True},
    {"name": "WAGNER LIQUIDOS", "u_negocio": "PROLINE", "leadtime": 95, "active": True},
    {"name": "WEGA", "u_negocio": "C-MOVIL", "leadtime": 65, "active": True},
    {"name": "ZM", "u_negocio": "C-MOVIL", "leadtime": 168, "active": True},
    {"name": "ZUTAKA", "u_negocio": "C-MOVIL", "leadtime": 240, "active": True}
]

def run_migration():
    # Make sure metadata tables exist and SQLite migrations run
    init_db()
    
    db = SessionLocal()
    try:
        # 1. Seed brands
        print("Seeding brands...")
        brand_map = {}
        for b in BRANDS_DATA:
            existing = db.query(WorkflowBrand).filter(WorkflowBrand.name == b["name"]).first()
            if existing:
                existing.u_negocio = b["u_negocio"]
                existing.leadtime = b["leadtime"]
                existing.active = b["active"]
                brand_obj = existing
            else:
                brand_obj = WorkflowBrand(
                    name=b["name"],
                    u_negocio=b["u_negocio"],
                    leadtime=b["leadtime"],
                    active=b["active"]
                )
                db.add(brand_obj)
            db.flush()
            brand_map[b["name"].upper()] = brand_obj.id

        db.commit()
        print(f"Successfully seeded {len(BRANDS_DATA)} brands.")

        # 2. Retro-classify existing instances
        print("Classifying existing instances...")
        instances = db.query(WorkflowInstance).all()
        updated_count = 0
        
        # Mappings for prefixes
        prefix_to_brand = {
            "MBL": "MITSUBOSHI",
            "MRK": "MRK",
            "WEGA": "WEGA",
            "NGK": "NGK",
            "MARILIA": "MARILIA",
            "3M": "3M",
            "FIC": "FIC"
        }

        for inst in instances:
            title_upper = inst.title.strip().upper()
            matched_brand_name = None
            
            # Check prefix mappings first
            for prefix, brand_name in prefix_to_brand.items():
                if title_upper.startswith(prefix.upper()):
                    matched_brand_name = brand_name
                    break
            
            # If no prefix match, try direct brand name prefix match
            if not matched_brand_name:
                for b in BRANDS_DATA:
                    b_name = b["name"].upper()
                    if title_upper.startswith(b_name + " ") or title_upper == b_name:
                        matched_brand_name = b["name"]
                        break

            if matched_brand_name:
                b_id = brand_map.get(matched_brand_name.upper())
                if b_id:
                    inst.brand_id = b_id
                    updated_count += 1
                    print(f"  Instance #{inst.id} ('{inst.title}') -> Brand '{matched_brand_name}'")
            else:
                print(f"  Instance #{inst.id} ('{inst.title}') -> No brand match found")
        
        db.commit()
        print(f"Migration finished. Classified {updated_count} of {len(instances)} instances.")

    except Exception as e:
        db.rollback()
        print(f"ERROR running migration: {e}")
        raise e
    finally:
        db.close()

if __name__ == "__main__":
    run_migration()
