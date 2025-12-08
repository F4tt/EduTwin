"""add version tracking columns

Revision ID: 0005_add_ml_version_tracking
Revises: 0004_add_learning_goals
Create Date: 2025-11-19 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '0005b_add_ml_version_tracking'
down_revision = '0005a_add_user_id_to_knn_samples'
branch_labels = None
depends_on = None


def upgrade():
    # Add version to MLModelConfig
    op.execute("""
        ALTER TABLE ml_model_configs ADD COLUMN IF NOT EXISTS version INTEGER NOT NULL DEFAULT 1;
    """)
    
    # Add version to ModelParameters  
    op.execute("""
        ALTER TABLE model_parameters ADD COLUMN IF NOT EXISTS version INTEGER NOT NULL DEFAULT 1;
    """)
    
    # Add ml_config_version to Users
    op.execute("""
        ALTER TABLE users ADD COLUMN IF NOT EXISTS ml_config_version INTEGER DEFAULT 0;
    """)
    
    # Create index for faster lookups
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_users_ml_config_version ON users(ml_config_version);
    """)
    
    # Set initial version based on update timestamp
    op.execute("""
        UPDATE ml_model_configs SET version = 1 WHERE version IS NULL OR version = 0;
        UPDATE model_parameters SET version = 1 WHERE version IS NULL OR version = 0;
        UPDATE users SET ml_config_version = 0 WHERE ml_config_version IS NULL;
    """)
    
    # Create function to get current ML config version
    op.execute("""
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
    """)


def downgrade():
    op.execute("DROP FUNCTION IF EXISTS get_current_ml_version();")
    op.execute("DROP INDEX IF EXISTS idx_users_ml_config_version;")
    op.drop_column('users', 'ml_config_version')
    op.drop_column('model_parameters', 'version')
    op.drop_column('ml_model_configs', 'version')
