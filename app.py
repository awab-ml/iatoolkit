## Copyright (c) 2024 Fernando Libedinsky

from dotenv import load_dotenv
from companies.sample_company.sample_company import SampleCompany
import os
import sys

# --- Try to import iatoolkit as an installed package ---
try:
    from iatoolkit import IAToolkit, register_company
except ImportError:
    # Fallback: running from source repo, add ./src to sys.path
    base_dir = os.path.dirname(os.path.abspath(__file__))
    src_path = os.path.join(base_dir, "src")
    if src_path not in sys.path:
        sys.path.insert(0, src_path)

    # Try again after modifying sys.path
    from iatoolkit import IAToolkit, register_company


# load environment variables
load_dotenv()

def create_app():
    # IMPORTANT: companies must be registered before creating the IAToolkit
    register_company('sample_company', SampleCompany)

    # create the IAToolkit and Flask instance
    toolkit = IAToolkit()
    return toolkit.create_iatoolkit()


app = create_app()

if __name__ == "__main__":
    if app:
        default_port = 5007
        app.run(debug=True, port=default_port)