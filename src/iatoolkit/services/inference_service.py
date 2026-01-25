# iatoolkit/services/inference_service.py
# Copyright (c) 2024 Fernando Libedinsky
# Product: IAToolkit

import os
import logging
from typing import Optional, Dict, Any
from injector import inject
from iatoolkit.services.configuration_service import ConfigurationService
from iatoolkit.services.i18n_service import I18nService
from iatoolkit.infra.call_service import CallServiceClient

class InferenceService:
    """
    Service specific for interacting with the custom Hugging Face Inference Endpoint.
    It handles configuration loading per company and manages the HTTP communication.
    """

    @inject
    def __init__(self,
                 config_service: ConfigurationService,
                 call_service: CallServiceClient,
                 i18n_service: I18nService):
        self.config_service = config_service
        self.call_service = call_service
        self.i18n_service = i18n_service

    def predict(self, company_short_name: str, tool_name: str, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Executes an inference task by calling the configured HF endpoint.

        Args:
            company_short_name: The company identifier.
            tool_name: The specific tool key in company.yaml (e.g., 'object_detection', 'sentiment').
            input_data: The payload required for the model (e.g., {'image': url} or {'text': '...'}).

        Returns:
            Dict containing the model's response.
        """
        # 1. Load configuration for the specific tool
        config = self._get_tool_config(company_short_name, tool_name)

        endpoint_url = config.get('endpoint_url')
        api_key_name = config.get('api_key_name', 'HF_TOKEN') # Default to HF_TOKEN if not specified
        model_id = config.get('model_id') # Optional specific model ID to pass to the handler
        model_parameters = config.get('model_parameters', {})

        if not endpoint_url:
            raise ValueError(f"Missing 'endpoint_url' for tool '{tool_name}' in company '{company_short_name}'.")

        # 2. Get the API Key
        api_key = os.getenv(api_key_name)
        if not api_key:
            raise ValueError(f"Environment variable '{api_key_name}' is not set.")

        # 3. Construct the payload
        # We wrap the user input into the structure expected by your custom Handler
        # You mentioned your handler expects: inputs: { mode: "...", text/url: "..." }
        # We allow the caller to pass the exact structure, or we can enrich it here.

        # Scenario A: The input_data IS the full 'inputs' dict required by the handler
        payload = {
            "inputs": input_data
        }

        # Scenario B (Optional enrichment): If we need to pass the model_id dynamically to the handler
        parameters = {}
        if model_id:
            parameters["model_id"] = model_id

        if model_parameters:
            parameters.update(model_parameters)

        if parameters:
            payload["parameters"] = parameters

        # 4. Execute Call
        return self._call_endpoint(endpoint_url, api_key, payload)

    def _get_tool_config(self, company_short_name: str, tool_name: str) -> dict:
        """Helper to safely extract tool configuration from company.yaml."""
        # Looking for a section like 'inference_tools' in company.yaml
        inference_config = self.config_service.get_configuration(company_short_name, 'inference_tools')

        if not inference_config:
            raise ValueError(f"Section 'inference_tools' not found for company '{company_short_name}'.")

        tool_config = inference_config.get(tool_name)
        if not tool_config:
            raise ValueError(f"Tool '{tool_name}' not configured in 'inference_tools' for '{company_short_name}'.")

        return tool_config

    def _call_endpoint(self, url: str, api_key: str, payload: dict) -> dict:
        """Performs the POST request to the HF Endpoint."""
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

        try:
            resp, status = self.call_service.post(
                url,
                json_dict=payload,
                headers=headers,
                timeout=(5, 60.0) # 5s connect, 60s read (models can be slow)
            )

            if status != 200:
                error_msg = f"Inference Endpoint Error {status}"
                if isinstance(resp, dict) and 'error' in resp:
                    error_msg += f": {resp['error']}"
                logging.error(f"{error_msg} | Payload keys: {list(payload.keys())}")
                raise ValueError(error_msg)

            return resp

        except Exception as e:
            logging.error(f"Failed to call inference endpoint: {e}")
            raise