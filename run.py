"""Ponto de entrada da aplicação Nota de Saída."""

import os

from dotenv import load_dotenv

from app import create_app

load_dotenv()

app = create_app(os.environ.get("FLASK_ENV", "development"))


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
