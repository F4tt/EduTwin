"""Make teaching structure global (remove user_id) and drop learning_goals

Revision ID: 0010
Revises: 0009
Create Date: 2025-12-06

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '0010_make_structure_global'
down_revision = '0009_add_current_time_point'
branch_labels = None
depends_on = None


def upgrade():
    # Drop learning_goals table (feature removed)
    op.execute('DROP TABLE IF EXISTS learning_goals CASCADE')
    
    # Make custom_teaching_structures global by removing user_id
    # Step 1: Drop foreign key constraint and index (IF EXISTS)
    op.execute('ALTER TABLE custom_teaching_structures DROP CONSTRAINT IF EXISTS custom_teaching_structures_user_id_fkey')
    op.execute('DROP INDEX IF EXISTS ix_custom_teaching_structures_user_id')
    
    # Step 2: Drop user_id column if it exists
    op.execute('ALTER TABLE custom_teaching_structures DROP COLUMN IF EXISTS user_id')
    
    # Step 3: Ensure only one structure can be active at a time (global constraint)
    # Note: PostgreSQL doesn't support partial unique constraints directly,
    # but we can use a unique partial index
    op.execute('''
        CREATE UNIQUE INDEX IF NOT EXISTS ix_custom_teaching_structures_single_active 
        ON custom_teaching_structures (is_active) 
        WHERE is_active = true
    ''')
    
    # Step 4: Remove user_id from custom_reference_dataset (keep structure_id only)
    op.execute('ALTER TABLE custom_reference_dataset DROP CONSTRAINT IF EXISTS custom_reference_dataset_user_id_fkey')
    op.execute('DROP INDEX IF EXISTS ix_custom_reference_dataset_user_id')
    op.execute('ALTER TABLE custom_reference_dataset DROP COLUMN IF EXISTS user_id')
    
    # Step 5: Drop current_time_point from structure (users manage their own time points in user_scores)
    op.execute('ALTER TABLE custom_teaching_structures DROP COLUMN IF EXISTS current_time_point')


def downgrade():
    # Add back current_time_point
    op.add_column('custom_teaching_structures', 
                  sa.Column('current_time_point', sa.String(), nullable=True))
    
    # Add back user_id to custom_reference_dataset
    op.add_column('custom_reference_dataset',
                  sa.Column('user_id', sa.Integer(), nullable=True))
    op.create_index('ix_custom_reference_dataset_user_id', 'custom_reference_dataset', ['user_id'])
    op.execute('ALTER TABLE custom_reference_dataset ADD CONSTRAINT custom_reference_dataset_user_id_fkey FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE')
    
    # Drop unique active constraint
    op.drop_index('ix_custom_teaching_structures_single_active', table_name='custom_teaching_structures')
    
    # Add back user_id to custom_teaching_structures
    op.add_column('custom_teaching_structures',
                  sa.Column('user_id', sa.Integer(), nullable=True))
    op.create_index('ix_custom_teaching_structures_user_id', 'custom_teaching_structures', ['user_id'])
    op.execute('ALTER TABLE custom_teaching_structures ADD CONSTRAINT custom_teaching_structures_user_id_fkey FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE')
    
    # Recreate learning_goals table
    op.execute('''
        CREATE TABLE IF NOT EXISTS learning_goals (
            id SERIAL PRIMARY KEY,
            user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            university TEXT,
            major TEXT,
            target_score FLOAT,
            exam_blocks TEXT[],
            time_horizon TEXT,
            ai_strategy TEXT,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
            updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
        )
    ''')
    op.create_index('ix_learning_goals_id', 'learning_goals', ['id'])
    op.create_index('ix_learning_goals_user_id', 'learning_goals', ['user_id'])
