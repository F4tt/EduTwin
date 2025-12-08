"""update custom model structure

Revision ID: 0006
Revises: 0005
Create Date: 2025-12-03

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '0006b_update_custom_model_structure'
down_revision = '0006a_add_custom_user_scores'
branch_labels = None
depends_on = None


def upgrade():
    # Drop unique constraint on user_id from custom_teaching_structures
    op.drop_constraint('custom_teaching_structures_user_id_key', 'custom_teaching_structures', type_='unique')
    
    # Add new columns to custom_teaching_structures
    op.add_column('custom_teaching_structures', sa.Column('structure_name', sa.String(), nullable=True))
    op.add_column('custom_teaching_structures', sa.Column('is_active', sa.Boolean(), nullable=True, server_default='true'))
    
    # Update existing rows to have default structure_name
    op.execute("UPDATE custom_teaching_structures SET structure_name = 'Cấu trúc mặc định' WHERE structure_name IS NULL")
    
    # Make structure_name not nullable after setting defaults
    op.alter_column('custom_teaching_structures', 'structure_name', nullable=False)
    op.alter_column('custom_teaching_structures', 'is_active', nullable=False)
    
    # Add structure_id column to custom_dataset_samples
    op.add_column('custom_dataset_samples', sa.Column('structure_id', sa.Integer(), nullable=True))
    
    # Link existing samples to their user's structure
    op.execute("""
        UPDATE custom_dataset_samples cds
        SET structure_id = cts.id
        FROM custom_teaching_structures cts
        WHERE cds.user_id = cts.user_id
    """)
    
    # Make structure_id not nullable and add foreign key
    op.alter_column('custom_dataset_samples', 'structure_id', nullable=False)
    op.create_foreign_key(
        'custom_dataset_samples_structure_id_fkey',
        'custom_dataset_samples',
        'custom_teaching_structures',
        ['structure_id'],
        ['id'],
        ondelete='CASCADE'
    )
    
    # Create index on structure_id
    op.create_index(
        op.f('ix_custom_dataset_samples_structure_id'),
        'custom_dataset_samples',
        ['structure_id'],
        unique=False
    )


def downgrade():
    # Remove foreign key and index
    op.drop_index(op.f('ix_custom_dataset_samples_structure_id'), table_name='custom_dataset_samples')
    op.drop_constraint('custom_dataset_samples_structure_id_fkey', 'custom_dataset_samples', type_='foreignkey')
    
    # Remove structure_id column
    op.drop_column('custom_dataset_samples', 'structure_id')
    
    # Remove new columns from custom_teaching_structures
    op.drop_column('custom_teaching_structures', 'is_active')
    op.drop_column('custom_teaching_structures', 'structure_name')
    
    # Restore unique constraint on user_id
    op.create_unique_constraint('custom_teaching_structures_user_id_key', 'custom_teaching_structures', ['user_id'])
