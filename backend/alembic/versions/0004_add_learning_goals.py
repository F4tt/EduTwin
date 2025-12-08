"""add learning goals table

Revision ID: 0004
Revises: 0003
Create Date: 2025-11-26
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '0004_add_learning_goals'
down_revision = '0003_add_first_login_flag'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create learning_goals table
    op.create_table(
        'learning_goals',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('target_average', sa.Float(), nullable=False),
        sa.Column('target_semester', sa.String(), nullable=False),
        sa.Column('target_grade_level', sa.String(), nullable=False),
        sa.Column('predicted_scores', sa.JSON(), nullable=True),
        sa.Column('trajectory_data', sa.JSON(), nullable=True),
        sa.Column('ai_analysis', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_learning_goals_id'), 'learning_goals', ['id'], unique=False)
    op.create_index(op.f('ix_learning_goals_user_id'), 'learning_goals', ['user_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_learning_goals_user_id'), table_name='learning_goals')
    op.drop_index(op.f('ix_learning_goals_id'), table_name='learning_goals')
    op.drop_table('learning_goals')
