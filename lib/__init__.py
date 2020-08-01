# -*- coding: utf-8 -*-
"""
unokiwi-processing
~~~~~

UnoKiwi community processing code dependencies.

"""

# Logging
from .logger import Logger

__all__ = [
    'Logger'
]

# Controls if click should emit the warning about the use of unicode
# literals.
disable_unicode_literals_warning = False

__version__ = '1.0'
