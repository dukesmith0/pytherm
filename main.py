import sys

from src.app import create_app
from src.errors import install_error_handler

if __name__ == "__main__":
    install_error_handler()
    app, window = create_app()
    sys.exit(app.exec())
