import logging

from app.config import settings
from app.db import SessionLocal
from app.logging import configure_logging
from app.services.fit_import import FIT_IMPORT_PATH, FitImportService

logger = logging.getLogger(__name__)


def main() -> None:
    configure_logging(log_level=settings.log_level)
    session = SessionLocal()
    try:
        summary = FitImportService(session).run(import_path=FIT_IMPORT_PATH)
    finally:
        session.close()

    print("Local FIT import completed.")
    print(f"Scanned files: {summary.scanned_files}")
    print(f"Imported: {summary.imported_count}")
    print(f"Skipped duplicates: {summary.skipped_duplicate_count}")
    print(f"Skipped unsupported: {summary.skipped_unsupported_count}")
    print(f"Failed: {summary.failed_count}")
    if summary.duplicates:
        print("Duplicate files:")
        for duplicate in summary.duplicates:
            print(
                f"- {duplicate.path}: existing activity "
                f"{duplicate.existing_activity_id} ({duplicate.reason})"
            )
    if summary.failures:
        print("Failed or unsupported files:")
        for failure in summary.failures:
            print(f"- {failure.path}: {failure.reason}")


if __name__ == "__main__":
    main()
