"""Simplify HyperparameterConfig table - keep only essential metrics

Revision ID: simplify_hyperparams
Revises:
Create Date: 2025-11-20

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'simplify_hyperparams'
down_revision = None  # Update this if you have previous migrations
branch_labels = None
depends_on = None


def upgrade():
    """Remove unnecessary metric columns, keep only the 3 essential ones."""
    # Remove columns that are no longer needed
    with op.batch_alter_table('hyperparameter_configs', schema=None) as batch_op:
        # Remove standard deviation columns
        batch_op.drop_column('hypervolume_std')
        batch_op.drop_column('execution_time_std')

        # Remove spread and spacing metrics
        batch_op.drop_column('spread_mean')
        batch_op.drop_column('spread_std')
        batch_op.drop_column('spacing_mean')
        batch_op.drop_column('spacing_std')

        # Remove pareto size
        batch_op.drop_column('pareto_size_mean')

        # Remove metadata fields
        batch_op.drop_column('n_runs')
        batch_op.drop_column('n_configurations_tested')


def downgrade():
    """Re-add the removed columns (data will be lost)."""
    with op.batch_alter_table('hyperparameter_configs', schema=None) as batch_op:
        # Re-add standard deviation columns
        batch_op.add_column(sa.Column('hypervolume_std', sa.Float(), nullable=True))
        batch_op.add_column(sa.Column('execution_time_std', sa.Float(), nullable=True))

        # Re-add spread and spacing metrics
        batch_op.add_column(sa.Column('spread_mean', sa.Float(), nullable=True))
        batch_op.add_column(sa.Column('spread_std', sa.Float(), nullable=True))
        batch_op.add_column(sa.Column('spacing_mean', sa.Float(), nullable=True))
        batch_op.add_column(sa.Column('spacing_std', sa.Float(), nullable=True))

        # Re-add pareto size
        batch_op.add_column(sa.Column('pareto_size_mean', sa.Float(), nullable=True))

        # Re-add metadata fields
        batch_op.add_column(sa.Column('n_runs', sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column('n_configurations_tested', sa.Integer(), nullable=True))
