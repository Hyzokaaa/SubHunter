import os
import sys

# Bundled Bazarr libraries (subliminal fork, subliminal_patch, subzero) must
# shadow any pip-installed subliminal, so they go first on the path.
_VENDOR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "vendor")
if _VENDOR not in sys.path:
    sys.path.insert(0, _VENDOR)
