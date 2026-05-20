# packages/core/sutram_core/models/checkpoint.py
from __future__ import annotations

import uuid
from collections.abc import Callable
from typing import Any, ClassVar

from .base import SutramBaseModel

# Migrators: {from_version: callable(variables) -> variables}
MigratorFn = Callable[[dict[str, Any]], dict[str, Any]]
MigratorMap = dict[int, MigratorFn]


class Checkpoint(SutramBaseModel):
    execution_id: uuid.UUID
    tenant_id: uuid.UUID
    step_name: str
    step_index: int
    variables: dict[str, Any]
    state: dict[str, Any]
    schema_version: int = 1

    # Class-level migration registry — services register migrators here
    migrators: ClassVar[MigratorMap] = {}

    def migrate_to_current(self) -> Checkpoint:
        """Apply registered migrators forward from schema_version to latest."""
        variables = self.variables
        version = self.schema_version
        sorted_versions = sorted(v for v in self.migrators if v >= version)
        for v in sorted_versions:
            variables = self.migrators[v](variables)
            version = v + 1
        return self.model_copy(update={"variables": variables, "schema_version": version})
