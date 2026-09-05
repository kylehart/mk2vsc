"""``python -m mk2vsc`` runs the same CLI as the ``mk2vsc`` console script."""
import sys

from .cli import main

sys.exit(main())
