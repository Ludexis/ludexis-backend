"""company_name_keys
Revision ID: b2e7c4a9d156
Revises: 9d4b6c8e1f35
Create Date: 2026-10-07 10:00:00.000000
"""

import re

from alembic import op
import sqlalchemy as sa


revision = 'b2e7c4a9d156'
down_revision = '9d4b6c8e1f35'
branch_labels = None
depends_on = None

# Frozen copy of app.utils.normalization.company_key, so this migration keeps its meaning if the app's rule changes.
SUFFIXES = {
    "ltd", "limited", "inc", "incorporated", "llc", "corp", "corporation", "co", "company",
    "gmbh", "ag", "sa", "srl", "bv", "kk", "plc", "pty", "oy", "ab", "sro", "spa",
}


def company_key(name: str) -> str:
    words = re.findall(r"[a-z0-9]+", name.lower().replace("&", " and "))
    if len(words) > 1 and words[0] == "the":
        words = words[1:]
    while len(words) > 1 and words[-1] in SUFFIXES:
        words = words[:-1]
    return "".join(words) or name.strip().lower()


def _merge(table: str, link_table: str, link_column: str) -> None:
    # Records whose names share a key become one: the record with the plainest name (not all caps, shortest)
    # is kept and the others' entry links move to it.
    bind = op.get_bind()
    groups: dict[str, list[tuple[str, str]]] = {}
    for record_id, name in bind.execute(sa.text(f"SELECT id, name FROM {table}")):
        groups.setdefault(company_key(name), []).append((record_id, name))
    for key, records in groups.items():
        records.sort(key=lambda record: (record[1].isupper(), len(record[1]), record[1]))
        keeper = records[0][0]
        for duplicate, _ in records[1:]:
            bind.execute(
                sa.text(
                    f"INSERT INTO {link_table} (archive_entry_id, {link_column}) "
                    f"SELECT archive_entry_id, :keeper FROM {link_table} WHERE {link_column} = :duplicate "
                    f"ON CONFLICT DO NOTHING"
                ),
                {"keeper": keeper, "duplicate": duplicate},
            )
            bind.execute(sa.text(f"DELETE FROM {table} WHERE id = :duplicate"), {"duplicate": duplicate})
        bind.execute(sa.text(f"UPDATE {table} SET name_key = :key WHERE id = :keeper"), {"key": key, "keeper": keeper})


def upgrade() -> None:
    for table, link_table, link_column in (
        ("developers", "archive_entry_developers", "developer_id"),
        ("publishers", "archive_entry_publishers", "publisher_id"),
    ):
        op.add_column(table, sa.Column('name_key', sa.String(length=256), nullable=True))
        _merge(table, link_table, link_column)
        op.alter_column(table, 'name_key', nullable=False)
        op.create_unique_constraint(f'{table}_name_key_key', table, ['name_key'])


def downgrade() -> None:
    # Merged duplicates are not restored.
    for table in ("developers", "publishers"):
        op.drop_constraint(f'{table}_name_key_key', table, type_='unique')
        op.drop_column(table, 'name_key')
