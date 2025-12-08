"""add ml_model_config table

Revision ID: 0013_add_ml_model_config
Revises: 0012_add_structure_documents
Create Date: 2025-12-07 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '0013_add_ml_model_config'
down_revision = '0012_add_structure_documents'
branch_labels = None
depends_on = None


def upgrade():
    # Create ml_model_config table
    op.create_table(
        'ml_model_config',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('active_model', sa.String(), nullable=False, server_default='knn'),
        sa.Column('updated_by', sa.Integer(), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(['updated_by'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Insert default row
    op.execute("""
        INSERT INTO ml_model_config (id, active_model) VALUES (1, 'knn')
        ON CONFLICT DO NOTHING
    """)


def downgrade():
    op.drop_table('ml_model_config')
