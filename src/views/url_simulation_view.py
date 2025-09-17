# Copyright (c) 2024 Fernando Libedinsky
# Producto: IAToolkit
# Todos los derechos reservados.
# En trámite de registro en el Registro de Propiedad Intelectual de Chile.

from flask import request, jsonify
from flask.views import MethodView


class URLSimulationView(MethodView):
    def get(self, company_short_name, object_name):
        rut = request.args.get('rut')

        response_data = {}
        if company_short_name == "maxxa":
            if object_name == "risk_file":
                response_data = {
                "company": "MAS_AVAL",
                "client_rut": rut,
                "client_name": "Fernando Libedinsky",
                "client_type": "NATURAL",
                "file_num": 300,
                "date": "2019-04-18",
                "max_exposure": 30000000,
                "executive": "cgarcia",
                "annual_sales": 100000000,
                "approval_status": "ACCEPTED",
            }
            elif object_name == "contact_book":
                response_data = {
                    "client_rut": rut,
                    "client_name": "Opensoft S.A.",
                    "contact_list": [
                        {'name': 'Fernando', 'phone': '1234', 'email': 'fernando@company.cl'},
                        {'name': 'Juanito', 'phone': '5678', 'email': 'juanito@company.cl'},
                    ]
                }

        return response_data, 200

    def post(self, company_short_name, object_name):
        data = request.get_json() or {}

        response_data = {}
        return response_data, 200