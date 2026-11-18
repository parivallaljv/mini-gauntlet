"""Importing this package imports every module in it, which registers all checks.

Adding a check therefore means writing one decorated function (in an existing
module or a new one in this folder); nothing else has to change.
"""

import importlib
import pkgutil

for _module in pkgutil.iter_modules(__path__):
    importlib.import_module(f"{__name__}.{_module.name}")
