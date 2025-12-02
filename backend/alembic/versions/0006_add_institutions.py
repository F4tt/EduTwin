"""Add institutions table

Revision ID: 0006_add_institutions
Revises: 0005_add_user_id_to_knn_samples
Create Date: 2025-12-01

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '0006_add_institutions'
down_revision = '0005_add_user_id_to_knn_samples'
branch_labels = None
depends_on = None


def upgrade():
    # Create institutions table
    op.create_table(
        'institutions',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('institution_name', sa.String(), nullable=False),
        sa.Column('institution_type', sa.String(), nullable=True),
        sa.Column('username', sa.String(), nullable=False),
        sa.Column('hashed_password', sa.String(), nullable=False),
        sa.Column('email', sa.String(), nullable=True),
        sa.Column('phone', sa.String(), nullable=True),
        sa.Column('address', sa.String(), nullable=True),
        sa.Column('website', sa.String(), nullable=True),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('logo_url', sa.String(), nullable=True),
        sa.Column('contact_person', sa.String(), nullable=True),
        sa.Column('metadata', sa.JSON(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.text('true')),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create indexes
    op.create_index(op.f('ix_institutions_id'), 'institutions', ['id'], unique=False)
    op.create_index(op.f('ix_institutions_username'), 'institutions', ['username'], unique=True)


def downgrade():
    # Drop indexes
    op.drop_index(op.f('ix_institutions_username'), table_name='institutions')
    op.drop_index(op.f('ix_institutions_id'), table_name='institutions')
    
    # Drop table
    op.drop_table('institutions')
