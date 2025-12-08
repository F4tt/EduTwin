"""Add custom_user_scores table

Revision ID: 0006
Revises: 0005
Create Date: 2025-12-04 07:40:06

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '0006a_add_custom_user_scores'
down_revision = '0005b_add_ml_version_tracking'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'custom_user_scores',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('structure_id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('subject', sa.String(), nullable=False),
        sa.Column('time_point', sa.String(), nullable=False),
        sa.Column('actual_score', sa.Float(), nullable=True),
        sa.Column('predicted_score', sa.Float(), nullable=True),
        sa.Column('predicted_source', sa.String(), nullable=True),
        sa.Column('predicted_status', sa.String(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['structure_id'], ['custom_teaching_structures.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    )
    op.create_index('ix_custom_user_scores_id', 'custom_user_scores', ['id'])
    op.create_index('ix_custom_user_scores_structure_id', 'custom_user_scores', ['structure_id'])
    op.create_index('ix_custom_user_scores_user_id', 'custom_user_scores', ['user_id'])
    op.create_index(
        'ix_custom_user_score_unique',
        'custom_user_scores',
        ['user_id', 'structure_id', 'subject', 'time_point'],
        unique=True
    )


def downgrade():
    op.drop_index('ix_custom_user_score_unique', table_name='custom_user_scores')
    op.drop_index('ix_custom_user_scores_user_id', table_name='custom_user_scores')
    op.drop_index('ix_custom_user_scores_structure_id', table_name='custom_user_scores')
    op.drop_index('ix_custom_user_scores_id', table_name='custom_user_scores')
    op.drop_table('custom_user_scores')
