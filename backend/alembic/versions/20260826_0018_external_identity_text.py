"""Store provider external identities as text."""

import sqlalchemy as sa
from alembic import op


revision = "20260826_0018"
down_revision = "20260826_0017"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column(
        "users",
        "external_user_id",
        existing_type=sa.BigInteger(),
        type_=sa.String(length=255),
        existing_nullable=True,
        postgresql_using="external_user_id::text",
    )
    op.drop_table("intervals_credentials")


def downgrade() -> None:
    pass
