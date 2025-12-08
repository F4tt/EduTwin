"""rename model_parameters to ml_model_parameters

Revision ID: 0014_rename_model_parameters
Revises: 0013_add_ml_model_config
Create Date: 2025-12-07

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '0014_rename_model_parameters'
down_revision = '0013_add_ml_model_config'
branch_labels = None
depends_on = None


def upgrade():
    # Drop old model_parameters table if exists (ml_model_parameters already exists from migration 0007)
    op.execute('DROP TABLE IF EXISTS model_parameters CASCADE')


def downgrade():
    # Rename back
    op.execute('ALTER TABLE IF EXISTS ml_model_parameters RENAME TO model_parameters')
