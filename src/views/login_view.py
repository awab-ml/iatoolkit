# Copyright (c) 2024 Fernando Libedinsky
# Producto: IAToolkit
# Todos los derechos reservados.
# En trámite de registro en el Registro de Propiedad Intelectual de Chile.

from flask.views import MethodView
from flask import request, redirect, render_template, url_for
from injector import inject
from services.profile_service import ProfileService

class LoginView(MethodView):
    @inject
    def __init__(self, profile_service: ProfileService):
        self.profile_service = profile_service

    def get(self, company_short_name: str):
        # get company info
        company = self.profile_service.get_company_by_short_name(company_short_name)
        if not company:
            return render_template('error.html', message="Empresa no encontrada"), 404

        return render_template('login.html',
                               company=company,
                               company_short_name=company_short_name)

    def post(self, company_short_name: str):
        # get company info
        company = self.profile_service.get_company_by_short_name(company_short_name)
        if not company:
            return render_template('error.html', message="Empresa no encontrada"), 404

        email = request.form.get('email')
        try:
            password = request.form.get('password')

            response = self.profile_service.login(
                company_short_name=company_short_name,
                email=email,
                password=password
                )

            if "error" in response:
                return render_template(
                'login.html',
                                    company_short_name=company_short_name,
                                    company=company,
                                    form_data={
                                           "email": email,
                                           "password": password,
                                       },
                                    alert_message=response["error"]), 400

            return redirect(url_for('chat', company_short_name=company_short_name))

        except Exception as e:
            return render_template("error.html",
                                   company=company,
                                   company_short_name=company_short_name,
                                   message="Ha ocurrido un error inesperado."), 500

