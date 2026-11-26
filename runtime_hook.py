import sys
import os

# Add bundled paths to sys.path
if getattr(sys, 'frozen', False):
    base = sys._MEIPASS
    for folder in ['admin', 'core']:
        path = os.path.join(base, folder)
        if os.path.isdir(path) and path not in sys.path:
            sys.path.insert(0, path)
    if base not in sys.path:
        sys.path.insert(0, base)
