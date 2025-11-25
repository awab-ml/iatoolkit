# iatoolkit/views/index_view.py

from flask import render_template, request
from flask.views import MethodView
from iatoolkit.common.util import Utility
from injector import inject


class IndexView(MethodView):
    """
    Handles the rendering of the generic landing page, which no longer depends
    on a specific company.
    """
    @inject
    def __init__(self, util: Utility):
        self.util = util

    def get(self):
        template_name = self.util.get_template_by_language("index")
        return render_template(template_name)
