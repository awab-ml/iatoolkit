import pytest
from unittest.mock import Mock, patch, MagicMock
import uuid

# Asumimos que los archivos están en el directorio 'infra'
from infra.gemini_adapter import GeminiAdapter
from exceptions import AppException
from infra.llm_response import LLMResponse, ToolCall, Usage

class TestGeminiAdapter:
    """Tests para la clase GeminiAdapter."""

    def setup_method(self):
        """Configura el entorno de prueba antes de cada test."""
        # Mock del cliente de Gemini
        self.mock_gemini_client = MagicMock()

        # Mock del modelo generativo que el cliente devuelve
        self.mock_generative_model = MagicMock()
        self.mock_gemini_client.GenerativeModel.return_value = self.mock_generative_model

        # Instancia del adaptador con el cliente mockeado
        self.adapter = GeminiAdapter(gemini_client=self.mock_gemini_client)

        # Patch de uuid para tener IDs predecibles
        self.uuid_patcher = patch('infra.gemini_adapter.uuid.uuid4')
        self.mock_uuid = self.uuid_patcher.start()
        self.mock_uuid.return_value = uuid.UUID('12345678-1234-5678-1234-567812345678')


    def teardown_method(self):
        """Limpia el entorno después de cada test."""
        self.uuid_patcher.stop()

    def _create_mock_gemini_response(
        self, text_content=None, function_call=None, finish_reason="STOP", usage_metadata=None
    ):
        """Crea un objeto de respuesta mock de Gemini."""
        mock_response = MagicMock()
        mock_candidate = MagicMock()
        mock_content = MagicMock()
        parts = []

        if text_content:
            part = MagicMock()
            part.text = text_content
            # Asegurarse de que el atributo function_call no exista o sea None
            del part.function_call
            parts.append(part)

        if function_call:
            part = MagicMock()
            # The 'name' kwarg in MagicMock is special and sets the mock's repr, not a 'name' attribute.
            # To fix this, we create the mock and set its 'name' attribute directly.
            mock_function_call_obj = MagicMock()
            mock_function_call_obj.name = function_call['name']
            mock_function_call_obj.args = function_call['args']
            part.function_call = mock_function_call_obj

            # Asegurarse de que el atributo text no exista o sea None
            del part.text
            parts.append(part)

        mock_content.parts = parts
        mock_candidate.content = mock_content
        mock_candidate.finish_reason = finish_reason
        mock_response.candidates = [mock_candidate]

        if usage_metadata:
            mock_response.usage_metadata = MagicMock(
                prompt_token_count=usage_metadata['input'],
                candidates_token_count=usage_metadata['output'],
                total_token_count=usage_metadata['total']
            )
        else:
            # Si no hay metadatos, el atributo no debe existir
            del mock_response.usage_metadata

        return mock_response

    def test_create_response_text_only(self):
        """Prueba una llamada simple que devuelve solo texto."""
        mock_gemini_response = self._create_mock_gemini_response(
            text_content="Hola mundo",
            usage_metadata={'input': 10, 'output': 5, 'total': 15}
        )
        self.mock_generative_model.generate_content.return_value = mock_gemini_response

        response = self.adapter.create_response(
            model="gemini-pro",
            input=[{"role": "user", "content": "di hola"}]
        )

        assert isinstance(response, LLMResponse)
        assert response.model == "gemini-pro"
        assert response.output_text == "Hola mundo"
        assert response.status == "completed"
        assert len(response.output) == 0
        assert response.usage.input_tokens == 10
        assert response.usage.output_tokens == 5
        assert response.usage.total_tokens == 15

        self.mock_gemini_client.GenerativeModel.assert_called_once()
        self.mock_generative_model.generate_content.assert_called_once()

    @patch('infra.gemini_adapter.MessageToDict')
    def test_create_response_with_tool_call(self, mock_message_to_dict):
        """Prueba una llamada que devuelve una function_call."""
        func_call_data = {'name': 'get_weather', 'args': {'location': 'Santiago'}}
        mock_gemini_response = self._create_mock_gemini_response(
            function_call=func_call_data,
            usage_metadata={'input': 25, 'output': 10, 'total': 35}
        )
        self.mock_generative_model.generate_content.return_value = mock_gemini_response

        # Configurar el mock para que devuelva la estructura esperada que la implementación usa
        mock_message_to_dict.return_value = {'args': func_call_data['args']}

        tools = [{
            "type": "function",
            "name": "get_weather",
            "description": "Obtiene el clima",
            "parameters": {"type": "object", "properties": {"location": {"type": "string"}}}
        }]

        response = self.adapter.create_response(
            model="gemini-flash",
            input=[{"role": "user", "content": "clima en santiago"}],
            tools=tools
        )

        assert len(response.output) == 1
        tool_call = response.output[0]
        assert isinstance(tool_call, ToolCall)
        assert tool_call.name == "get_weather"
        assert tool_call.type == "function_call"
        assert tool_call.arguments == '{"location": "Santiago"}'
        assert response.usage.total_tokens == 35

        # Verifica que se llamó con las herramientas preparadas
        call_args, call_kwargs = self.mock_generative_model.generate_content.call_args
        assert 'tools' in call_kwargs


    def test_create_response_api_error_handling(self):
        """Prueba que una excepción de la API se captura y se convierte en AppException."""
        self.mock_generative_model.generate_content.side_effect = Exception("Quota exceeded")

        with pytest.raises(AppException) as excinfo:
            self.adapter.create_response(model="gemini-pro", input=[])

        assert excinfo.value.error_type == AppException.ErrorType.LLM_ERROR
        # Verifica que el mensaje de error se personaliza
        assert "Se ha excedido la cuota de la API de Gemini" in str(excinfo.value)

    def test_map_blocked_status(self):
        """Prueba que el finish_reason 'SAFETY' se mapea a status 'blocked'."""
        mock_gemini_response = self._create_mock_gemini_response(
            text_content="Contenido bloqueado", finish_reason="SAFETY"
        )
        self.mock_generative_model.generate_content.return_value = mock_gemini_response

        response = self.adapter.create_response(model="gemini-pro", input=[])
        assert response.status == "blocked"

    def test_map_length_exceeded_status(self):
        """Prueba que el finish_reason 'MAX_TOKENS' se mapea a 'length_exceeded'."""
        mock_gemini_response = self._create_mock_gemini_response(
            text_content="Largo texto...", finish_reason="MAX_TOKENS"
        )
        self.mock_generative_model.generate_content.return_value = mock_gemini_response

        response = self.adapter.create_response(model="gemini-pro", input=[])
        assert response.status == "length_exceeded"

    def test_usage_estimation_when_no_metadata(self):
        """Prueba la estimación de tokens cuando usage_metadata no está presente."""
        mock_gemini_response = self._create_mock_gemini_response(text_content="12345678")  # 8 chars
        self.mock_generative_model.generate_content.return_value = mock_gemini_response

        response = self.adapter.create_response(model="gemini-pro", input=[])

        # La estimación es len // 4
        assert response.usage.output_tokens == 2
        assert response.usage.total_tokens == 2
        assert response.usage.input_tokens == 0


    @pytest.mark.parametrize("input_model, expected_gemini_model", [
        ("gemini-pro", "gemini-2.5-pro"),
        ("gemini-flash", "gemini-1.5-flash"),
        ("gemini-unknown", "gemini-unknown"), # Caso por defecto
    ])
    def test_map_model_name(self, input_model, expected_gemini_model):
        """Prueba el mapeo de nombres de modelos."""
        assert self.adapter._map_model_name(input_model) == expected_gemini_model

    def test_prepare_gemini_contents(self):
        """Prueba la conversión de mensajes de formato OpenAI a Gemini."""
        openai_input = [
            {"role": "system", "content": "Eres un asistente."},
            {"role": "user", "content": "Hola."},
            {"type": "function_call_output", "output": "{'status': 'ok'}"}
        ]
        gemini_contents = self.adapter._prepare_gemini_contents(openai_input)

        assert len(gemini_contents) == 3
        assert "[INSTRUCCIONES DEL SISTEMA]\nEres un asistente" in gemini_contents[0]['parts'][0]['text']
        assert gemini_contents[0]['role'] == 'user' # System se mapea a user
        assert gemini_contents[1]['parts'][0]['text'] == "Hola."
        assert gemini_contents[2]['role'] == 'function'
        assert gemini_contents[2]['parts'][0]['function_response']['response']['output'] == "{'status': 'ok'}"

    def test_prepare_gemini_tools_with_clean(self):
        """Prueba la preparación de herramientas y la limpieza de campos no soportados."""
        openai_tools = [{
            "type": "function",
            "name": "search",
            "description": "Busca algo",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "La búsqueda"},
                    "user_id": {"type": "integer", "format": "int64"} # 'format' no es soportado
                },
                "required": ["query"],
                "additionalProperties": False # no es soportado
            }
        }]

        gemini_tools = self.adapter._prepare_gemini_tools(openai_tools)

        assert gemini_tools is not None
        func_declaration = gemini_tools[0]['function_declarations'][0]
        params = func_declaration['parameters']

        assert "additionalProperties" not in params
        assert "format" not in params['properties']['user_id']
        assert params['properties']['query']['type'] == 'string'