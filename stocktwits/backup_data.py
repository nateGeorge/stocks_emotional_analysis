"""
backs up data to dropbox
"""

import os
from glob import iglob
import shutil

root, dirs, files = list(os.walk('data/'))
