# Copyright (c) 2024 Fernando Libedinsky
# Product: IAToolkit
#
# IAToolkit is open source software.

FUNCTION_LIST = [
        {'name': 'Acceso via SQL a la base de datos.',
         'description': "Debes usar este servicio para consulta sobre Sample Company y sus "
                        "clientes, productos, ordenes , regiones, empleados.",
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
        {'name': 'busquedas en documentos: manuales internos, contratos de trabajo, procedimientos, legales',
         'description': "busquedas sobre documentos: manuales, contratos de trabajo de empleados,"
            'manuales de procedimientos, documentos legales, manuales de proveedores (supply-chain)',
         'function_name': "document_search",
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


PROMPT_LIST = [
            {
                'name': 'analisis_ventas',
                'description': 'Analisis de ventas',
                'order': 1,
                'custom_fields': [
                    {
                        "data_key": "init_date",
                        "label": "Fecha desde",
                        "type": "date",
                    },
                    {
                        "data_key": "end_date",
                        "label": "Fecha hasta",
                        "type": "date",
                    }
                ]
            },
            {
                'name': 'supplier_report',
                'description': 'Análisis de proveedores',
                'order': 2,
                'custom_fields': [
                    {
                        "data_key": "supplier_id",
                        "label": "Identificador del Proveedor",
                    }
                ]
            }
        ]

BRANDING = {
    # --- Estilos del Encabezado Principal ---
    "header_background_color": "#0D5D53",       # Fondo en el nuevo verde pino
    "header_text_color": "#FFFFFF",             # Texto principal en blanco
    "primary_font_weight": "600",
    "primary_font_size": "1.2rem",
    "secondary_font_weight": "400",
    "secondary_font_size": "0.9rem",
    "tertiary_font_weight": "400",
    "tertiary_font_size": "0.8rem",
    "tertiary_opacity": "0.7",

    # --- Estilos Globales de la Marca (Botones y acciones) ---
    "brand_primary_color": "#0D5D53",           # Verde pino como color de acción principal
    "brand_secondary_color": "#64748B",         # Se mantiene el gris pizarra para acciones secundarias
    "brand_text_on_primary": "#FFFFFF",         # Texto blanco sobre el verde
    "brand_text_on_secondary": "#FFFFFF",       # Texto blanco sobre el gris

    # --- Estilos para Alertas de Error ---
    "brand_danger_color": "#dc3545",
    "brand_danger_bg": "#f8d7da",
    "brand_danger_text": "#842029",
    "brand_danger_border": "#f5c2c7",

    # --- Estilos para Alertas Informativas ---
    "brand_info_bg": "#ECFDF5",                 # Un verde muy pálido, casi menta
    "brand_info_text": "#0D5D53",               # El mismo verde pino
    "brand_info_border": "#A7F3D0",             # Un borde verde menta claro

    # --- Estilos para el Asistente de Prompts ---
    "prompt_assistant_bg": "#f8f9fa",
    "prompt_assistant_border": "#dee2e6",
    "prompt_assistant_icon_color": "#0D5D53",    # Icono de la varita en verde pino
    "prompt_assistant_button_bg": "#FFFFFF",
    "prompt_assistant_button_text": "#334155",
    "prompt_assistant_button_border": "#cbd5e1",
    "prompt_assistant_dropdown_bg": "#FFFFFF",
    "prompt_assistant_header_bg": "#f1f3f5",
    "prompt_assistant_header_text": "#334155",
    "prompt_assistant_item_hover_bg": None,
    "prompt_assistant_item_hover_text": None,

    # --- Color para el botón de Enviar ---
    "send_button_color": "#0D5D53"               # El botón de enviar usa el color primario
}

BRANDING_AZUL = {
    # --- Estilos del Encabezado Principal ---
    "header_background_color": "#3D44C4",       # Fondo en el nuevo azul índigo
    "header_text_color": "#FFFFFF",             # Texto principal en blanco para contraste
    "primary_font_weight": "600",
    "primary_font_size": "1.2rem",
    "secondary_font_weight": "400",
    "secondary_font_size": "0.9rem",
    "tertiary_font_weight": "400",
    "tertiary_font_size": "0.8rem",
    "tertiary_opacity": "0.7",

    # --- Estilos Globales de la Marca (Botones y acciones) ---
    "brand_primary_color": "#3D44C4",           # Azul índigo como color de acción principal
    "brand_secondary_color": "#6c757d",         # Gris estándar para acciones secundarias
    "brand_text_on_primary": "#FFFFFF",         # Texto blanco sobre el azul
    "brand_text_on_secondary": "#FFFFFF",       # Texto blanco sobre el gris

    # --- Estilos para Alertas de Error ---
    "brand_danger_color": "#dc3545",
    "brand_danger_bg": "#f8d7da",
    "brand_danger_text": "#842029",
    "brand_danger_border": "#f5c2c7",

    # --- Estilos para Alertas Informativas ---
    "brand_info_bg": "#e8e9ff",
    "brand_info_text": "#3D44C4",
    "brand_info_border": "#d2d5ff",

    # --- Estilos para el Asistente de Prompts ---
    "prompt_assistant_bg": "#f8f9fa",
    "prompt_assistant_border": "#dee2e6",
    "prompt_assistant_icon_color": "#3D44C4",
    "prompt_assistant_button_bg": "#FFFFFF",
    "prompt_assistant_button_text": "#495057",
    "prompt_assistant_button_border": "#ced4da",
    "prompt_assistant_dropdown_bg": "#FFFFFF",
    "prompt_assistant_header_bg": "#f1f3f5",
    "prompt_assistant_header_text": "#212529",
    "prompt_assistant_item_hover_bg": None,
    "prompt_assistant_item_hover_text": None,

    # --- Color para el botón de Enviar ---
    "send_button_color": "#3D44C4"
}

ONBOARDING_CARDS = [
    {
        'icon': 'fas fa-database',
        'title': 'Sample Company',
        'text': 'Es una empresa ficticia para mostrarte como interactuar utilizar la IA a través de IAToolkit. Los datos dispobibles son un ejemplo de una empresa '
        'tipica que vende productos, gestiona ordenes de compra, proveedores, empleados y territorios. Se dispone de datos de los años 204 y 2025.'
    },
    {
        'icon': 'fas fa-database',
        'title': 'Datos disponibles',
        'text': 'Conozco los datos de: clientes, productos, ventas, empleados, territorios, etc..<br><br><strong>Ejemplo:</strong> ¿Cuál fue el producto más vendido en Alemania el año 2024?'
    },
    {
        'icon': 'fas fa-file-alt',
        'title': 'Documentos Internos',
        'text': 'Puedo buscar en manuales internos, contratos de trabajo y documentos legales para encontrar la información que necesitas.<br><br><strong>Ejemplo:</strong> ¿Cuál es el procedimiento para solicitar vacaciones?'
    },
    {
        'icon': 'fas fa-cogs',
        'title': 'Análisis SQL',
        'text': 'Puedes pedirme que ejecute consultas SQL directamente sobre la base de datos y te entregaré los resultados.<br><br><strong>Ejemplo:</strong> "SQL: SELECT * FROM Orders WHERE ShipCountry = \'France\' LIMIT 5"'
    },
    {'icon': 'fas fa-cogs', 'title': 'Personaliza tus Prompts',
     'text': 'Utiliza la varita magica y podras explorar los prompts predefinidos que he preparado para ti.'},
    {'icon': 'fas fa-table', 'title': 'Tablas y Excel',
     'text': 'Puedes pedirme la respuesta en formato de tablas o excel. <br><br><strong>Ejemplo:</strong> dame una tabla con los 10 certificados mas grande este año, columnas: rut, cliente, fecha, monto, tasa, comision, acreedor...'},
    {'icon': 'fas fa-shield-alt', 'title': 'Seguridad y Confidencialidad',
     'text': 'Toda tu información es procesada de forma segura y confidencial dentro de nuestro entorno protegido.'}
]
