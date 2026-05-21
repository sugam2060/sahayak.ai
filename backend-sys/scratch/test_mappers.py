import sys
import warnings
from sqlalchemy.orm import configure_mappers

# Force warnings to be printed
warnings.simplefilter("always")

try:
    print("Importing schema...")
    from shared.database.schema import Base
    print("Configuring mappers...")
    configure_mappers()
    print("Success: Mappers configured with no exception!")
except Exception as e:
    print(f"Error occurred: {e}", file=sys.stderr)
    import traceback
    traceback.print_exc()
