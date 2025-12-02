from db.database import engine
from sqlalchemy import text

with engine.connect() as conn:
    # Add column to knn_reference_samples
    conn.execute(text("""
        ALTER TABLE knn_reference_samples 
        ADD COLUMN IF NOT EXISTS institution_id INTEGER 
        REFERENCES institutions(id) ON DELETE CASCADE
    """))
    
    # Add index for knn_reference_samples
    conn.execute(text("""
        CREATE INDEX IF NOT EXISTS ix_knn_reference_samples_institution_id 
        ON knn_reference_samples(institution_id)
    """))
    
    # Add column to data_import_logs
    conn.execute(text("""
        ALTER TABLE data_import_logs 
        ADD COLUMN IF NOT EXISTS institution_id INTEGER 
        REFERENCES institutions(id) ON DELETE CASCADE
    """))
    
    # Add index for data_import_logs
    conn.execute(text("""
        CREATE INDEX IF NOT EXISTS ix_data_import_logs_institution_id 
        ON data_import_logs(institution_id)
    """))
    
    conn.commit()
    print("✅ Column institution_id added to knn_reference_samples successfully")
    print("✅ Column institution_id added to data_import_logs successfully")
