"""Start the app: python -m attendance_radar [data.db] [--port 8030]"""
import sys

from .fieldkit import main_cli
from .web import create_app

sys.exit(main_cli(create_app, "attendance.db", 8030, sys.argv))
