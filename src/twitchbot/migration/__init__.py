"""Read-only, fixture-first legacy source inspection boundary."""

from .inspector import InspectionError, InspectionReport, LegacySourceInspector, MigrationPlan, build_migration_plan
from .importer import CandidateImportError, CandidateImporter, CandidateImportReport

__all__ = ["InspectionError", "InspectionReport", "LegacySourceInspector", "MigrationPlan", "build_migration_plan", "CandidateImportError", "CandidateImporter", "CandidateImportReport"]
