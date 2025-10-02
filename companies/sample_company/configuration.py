# Copyright (c) 2024 Fernando Libedinsky
# Product: IAToolkit
#
# IAToolkit is open source software.

FUNCTION_LIST = [
        {'name': 'Acceso via SQL a la base de datos.',
         'description': "Consultas sobre clientes, productos, ordenes e items de una orden.",
         'function_name': "sql_query",
         'params': {
                    "type": "object",
                    "properties": {
                        "query": {"type": "string",
                                  "description": "string con la consulta en sql"}
                    },
                    "required": ["query"]
                }
         },
        {'name': 'busquedas en documentos de fondos',
         'description': "Buscar y recuperar fragmentos relevantes desde factsheets/reglamentos/prospectos PDF de fondos propios de la compañía (y sus filiales), con filtros por comisiones, clase de activo, riesgo, ISIN, etc.",
         'function_name': "fund_search",
         'params': {
                    "type": "object",
                    "properties": {
                        "query": {"type": "string",
                                  "description": "Texto o pregunta a buscar en los documentos."}
                    },
                    "required": ["query"]
                }
         }
    ]
