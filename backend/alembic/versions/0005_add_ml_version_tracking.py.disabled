"""
Migration script to add version tracking columns
Run this after updating models.py
"""

def add_version_columns_sql():
    """Generate SQL to add version columns to existing tables"""
    return """
-- Add version to MLModelConfig
ALTER TABLE ml_model_configs ADD COLUMN IF NOT EXISTS version INTEGER NOT NULL DEFAULT 1;

-- Add version to ModelParameters  
ALTER TABLE model_parameters ADD COLUMN IF NOT EXISTS version INTEGER NOT NULL DEFAULT 1;

-- Add ml_config_version to Users
ALTER TABLE users ADD COLUMN IF NOT EXISTS ml_config_version INTEGER DEFAULT 0;

-- Create index for faster lookups
CREATE INDEX IF NOT EXISTS idx_users_ml_config_version ON users(ml_config_version);

-- Set initial version based on update timestamp
UPDATE ml_model_configs SET version = 1 WHERE version IS NULL OR version = 0;
UPDATE model_parameters SET version = 1 WHERE version IS NULL OR version = 0;
UPDATE users SET ml_config_version = 0 WHERE ml_config_version IS NULL;

-- Create function to get current ML config version
CREATE OR REPLACE FUNCTION get_current_ml_version() RETURNS INTEGER AS $$
DECLARE
    model_ver INTEGER;
    param_ver INTEGER;
BEGIN
    SELECT COALESCE(version, 1) INTO model_ver FROM ml_model_configs ORDER BY updated_at DESC LIMIT 1;
    SELECT COALESCE(version, 1) INTO param_ver FROM model_parameters ORDER BY updated_at DESC LIMIT 1;
    -- Return max of both versions
    RETURN GREATEST(COALESCE(model_ver, 1), COALESCE(param_ver, 1));
END;
$$ LANGUAGE plpgsql;
"""

if __name__ == "__main__":
    print(add_version_columns_sql())
