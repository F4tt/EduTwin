"""add institution ml data

Revision ID: 0007_add_institution_ml_data
Revises: 0006_add_institutions
Create Date: 2025-12-01

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

# revision identifiers, used by Alembic.
revision = '0007_add_institution_ml_data'
down_revision = '0006_add_institutions'
branch_labels = None
depends_on = None


def upgrade():
    # Add institution_id to knn_reference_samples ONLY if table exists
    # (table is created dynamically when first dataset is imported)
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    if 'knn_reference_samples' in inspector.get_table_names():
        op.add_column('knn_reference_samples', sa.Column('institution_id', sa.Integer(), nullable=True))
        op.create_index('ix_knn_reference_samples_institution_id', 'knn_reference_samples', ['institution_id'])
        op.create_foreign_key('fk_knn_reference_samples_institution', 'knn_reference_samples', 'institutions', ['institution_id'], ['id'], ondelete='CASCADE')
    
    # Create table for institution-specific model parameters
    op.create_table(
        'institution_model_parameters',
        sa.Column('id', sa.Integer(), primary_key=True, index=True),
        sa.Column('institution_id', sa.Integer(), sa.ForeignKey('institutions.id', ondelete='CASCADE'), nullable=False, unique=True),
        sa.Column('knn_n', sa.Integer(), nullable=False, default=15),
        sa.Column('kr_bandwidth', sa.Float(), nullable=False, default=1.25),
        sa.Column('lwlr_tau', sa.Float(), nullable=False, default=3.0),
        sa.Column('active_model', sa.String(), nullable=False, default='knn'),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now())
    )
    op.create_index('ix_institution_model_parameters_institution_id', 'institution_model_parameters', ['institution_id'])


def downgrade():
    op.drop_index('ix_institution_model_parameters_institution_id', 'institution_model_parameters')
    op.drop_table('institution_model_parameters')
    
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    if 'knn_reference_samples' in inspector.get_table_names():
        op.drop_constraint('fk_knn_reference_samples_institution', 'knn_reference_samples', type_='foreignkey')
        op.drop_index('ix_knn_reference_samples_institution_id', 'knn_reference_samples')
        op.drop_column('knn_reference_samples', 'institution_id')
