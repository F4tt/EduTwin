"""add teaching structure and pipeline toggle

Revision ID: 0008
Revises: 0007
Create Date: 2025-12-01 04:35:00

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '0008'
down_revision = '0007'
branch_labels = None
depends_on = None


def upgrade():
    # Add pipeline_enabled column to institution_model_parameters
    op.add_column('institution_model_parameters', 
                  sa.Column('pipeline_enabled', sa.Boolean(), server_default=sa.text('true'), nullable=False))
    
    # Create teaching_structures table
    op.create_table('teaching_structures',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('institution_id', sa.Integer(), nullable=False),
        sa.Column('num_time_points', sa.Integer(), nullable=False),
        sa.Column('num_subjects', sa.Integer(), nullable=False),
        sa.Column('time_point_labels', sa.JSON(), nullable=False),
        sa.Column('subject_labels', sa.JSON(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['institution_id'], ['institutions.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('institution_id')
    )
    op.create_index(op.f('ix_teaching_structures_id'), 'teaching_structures', ['id'], unique=False)


def downgrade():
    op.drop_index(op.f('ix_teaching_structures_id'), table_name='teaching_structures')
    op.drop_table('teaching_structures')
    op.drop_column('institution_model_parameters', 'pipeline_enabled')
