## Copyright (c) 2024 Fernando Libedinsky

from dotenv import load_dotenv
from iatoolkit import IAToolkit, register_company
from companies.sample_fintech.sample_fintech import SampleFintech

# load environment variables
load_dotenv()

# companies must be registered before creating the IAToolkit
register_company('sample_fintech', SampleFintech)

# create the IAToolkit and Flask instance
toolkit = IAToolkit()
app = toolkit.create_iatoolkit()

if __name__ == "__main__":
    app.run()