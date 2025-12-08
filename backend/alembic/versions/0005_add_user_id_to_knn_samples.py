"""add user_id to knn_reference_samples

Revision ID: 0005
Revises: 0004
Create Date: 2025-11-28

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '0005a_add_user_id_to_knn_samples'
down_revision = '0004_add_learning_goals'
branch_labels = None
depends_on = None


def upgrade():
    # Add user_id column to knn_reference_samples
    op.add_column('knn_reference_samples', 
                  sa.Column('user_id', sa.Integer(), nullable=True))
    
    # Add foreign key constraint
    op.create_foreign_key(
        'fk_knn_reference_samples_user_id',
        'knn_reference_samples', 'users',
        ['user_id'], ['id'],
        ondelete='CASCADE'
    )
    
    # Add index for better query performance
    op.create_index(
        'ix_knn_reference_samples_user_id',
        'knn_reference_samples',
        ['user_id']
    )
    
    # WARNING: Existing data without user_id will remain (nullable=True)
    # You may want to manually assign or delete old records


def downgrade():
    op.drop_index('ix_knn_reference_samples_user_id', 'knn_reference_samples')
    op.drop_constraint('fk_knn_reference_samples_user_id', 'knn_reference_samples', type_='foreignkey')
    op.drop_column('knn_reference_samples', 'user_id')
