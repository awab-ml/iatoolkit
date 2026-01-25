from typing import Any, Dict, List
import base64
import io
import logging
import gc
import json

import requests
import torch
import numpy as np
from PIL import Image

# Transformers imports
from transformers import (
    CLIPProcessor, CLIPModel,
    AutoTokenizer, AutoModel,
    pipeline
)

class EndpointHandler:
    def __init__(self, path: str = ""):
        # Iniciamos sin modelos cargados para ahorrar RAM/VRAM en el arranque
        self.current_model_id = None
        self.model_instance = None
        self.processor_instance = None
        self.pipeline_instance = None

        # Definimos el dispositivo
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        logging.info(f"Handler initialized on device: {self.device}")

    def _clean_memory(self):
        """Libera memoria VRAM/RAM antes de cargar un nuevo modelo."""
        if self.model_instance is not None:
            del self.model_instance
        if self.processor_instance is not None:
            del self.processor_instance
        if self.pipeline_instance is not None:
            del self.pipeline_instance

        self.model_instance = None
        self.processor_instance = None
        self.pipeline_instance = None

        gc.collect()
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
            torch.cuda.ipc_collect()
        logging.info("Memory cleaned.")

    def _load_model(self, model_id: str, task: str = None):
        """Carga el modelo solicitado si no es el actual."""
        if self.current_model_id == model_id:
            return

        logging.info(f"Loading new model: {model_id}...")
        self._clean_memory()

        try:
            if "clip" in model_id.lower():
                self.processor_instance = CLIPProcessor.from_pretrained(model_id)
                self.model_instance = CLIPModel.from_pretrained(model_id).to(self.device)
                self.model_instance.eval()

            elif "minilm" in model_id.lower() or task == "feature-extraction":
                self.processor_instance = AutoTokenizer.from_pretrained(model_id)
                self.model_instance = AutoModel.from_pretrained(model_id).to(self.device)
                self.model_instance.eval()

            elif "whisper" in model_id.lower():
                # Whisper funciona mejor con pipelines optimizados
                self.pipeline_instance = pipeline(
                    "automatic-speech-recognition",
                    model=model_id,
                    device=self.device
                )

            elif "vibevoice" in model_id.lower() or task == "text-to-speech":
                # Asumimos que VibeVoice es compatible con pipeline TTS o similar
                # Nota: Si VibeVoice requiere código custom, iría aquí.
                # Usamos pipeline genérico por compatibilidad.
                self.pipeline_instance = pipeline(
                    "text-to-speech",
                    model=model_id,
                    device=self.device
                )

            self.current_model_id = model_id
            logging.info(f"Model {model_id} loaded successfully.")

        except Exception as e:
            logging.error(f"Failed to load model {model_id}: {e}")
            raise ValueError(f"Could not load model {model_id}. Error: {str(e)}")

    def _load_image(self, inputs: dict) -> Image.Image:
        url = inputs.get("presigned_url") or inputs.get("url")
        b64 = inputs.get("base64")

        if isinstance(url, str) and url.strip():
            r = requests.get(url, timeout=30)
            r.raise_for_status()
            return Image.open(io.BytesIO(r.content)).convert("RGB")
        elif isinstance(b64, str) and b64.strip():
            image_bytes = base64.b64decode(b64, validate=True)
            return Image.open(io.BytesIO(image_bytes)).convert("RGB")
        else:
            raise ValueError("Expected inputs.url or inputs.base64 for image task.")

    def _handle_clip(self, inputs: dict) -> dict:
        mode = inputs.get("mode")
        if mode == "text":
            text = inputs.get("text")
            inputs_pt = self.processor_instance(text=[text], return_tensors="pt", padding=True, truncation=True).to(self.device)
            with torch.no_grad():
                emb = self.model_instance.get_text_features(**inputs_pt)
        else:
            image = self._load_image(inputs)
            inputs_pt = self.processor_instance(images=image, return_tensors="pt").to(self.device)
            with torch.no_grad():
                emb = self.model_instance.get_image_features(**inputs_pt)

        emb = torch.nn.functional.normalize(emb, p=2, dim=-1)
        vec = emb[0].cpu().tolist()
        return {"embedding": vec, "dimensions": len(vec), "mode": mode}


    def _handle_minilm(self, inputs: dict) -> dict:
        # Mean Pooling - Take attention mask into account for correct averaging
        def mean_pooling(model_output, attention_mask):
            token_embeddings = model_output[0]
            input_mask_expanded = attention_mask.unsqueeze(-1).expand(token_embeddings.size()).float()
            return torch.sum(token_embeddings * input_mask_expanded, 1) / torch.clamp(input_mask_expanded.sum(1), min=1e-9)

        text = inputs.get("text")
        if not text:
            raise ValueError("Expected inputs.text for embedding.")

        encoded_input = self.processor_instance(text, padding=True, truncation=True, return_tensors='pt').to(self.device)

        with torch.no_grad():
            model_output = self.model_instance(**encoded_input)

        sentence_embeddings = mean_pooling(model_output, encoded_input['attention_mask'])
        sentence_embeddings = torch.nn.functional.normalize(sentence_embeddings, p=2, dim=1)

        vec = sentence_embeddings[0].cpu().tolist()
        return {"embedding": vec, "dimensions": len(vec)}

    def _handle_whisper(self, inputs: dict) -> dict:
        b64_audio = inputs.get("base64")
        if not b64_audio:
            raise ValueError("Expected inputs.base64 (audio bytes) for Whisper.")

        audio_bytes = base64.b64decode(b64_audio)

        # El pipeline de HF suele aceptar bytes directamente si ffmpeg está instalado en el endpoint
        # O podemos devolver texto
        result = self.pipeline_instance(audio_bytes)
        return {"text": result.get("text", "")}

    def _handle_tts(self, inputs: dict) -> dict:
        text = inputs.get("text")
        if not text:
            raise ValueError("Expected inputs.text for TTS.")

        # Generar audio
        output = self.pipeline_instance(text)
        # El formato de salida depende del pipeline, generalmente es {"audio": array, "sampling_rate": int}

        audio_data = output.get("audio")
        sampling_rate = output.get("sampling_rate")

        # Convertir a base64 para devolver
        # Esto es simplificado, idealmente convertiríamos numpy a wav/mp3 bytes primero
        # Aquí asumimos que devolvemos raw o implementamos una conversión simple

        # Para simplificar este ejemplo, devolvemos info. En prod, usar scipy.io.wavfile.write -> BytesIO -> Base64
        import scipy.io.wavfile
        wav_buffer = io.BytesIO()
        # Normalizar si es necesario y escribir
        scipy.io.wavfile.write(wav_buffer, rate=sampling_rate, data=audio_data.T)
        b64_out = base64.b64encode(wav_buffer.getvalue()).decode("utf-8")

        return {"audio_base64": b64_out, "sampling_rate": sampling_rate}

    def __call__(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Main entry point. Dispatches execution to the correct model handler.
        """
        inputs = data.get("inputs", {})
        parameters = data.get("parameters", {})

        # 1. Determinar qué modelo usar
        # El servicio envía el model_id en parameters.
        # Si no está, fallback a CLIP por defecto (compatibilidad hacia atrás)
        requested_model_id = parameters.get("model_id", "openai/clip-vit-base-patch32")

        # 2. Cargar/Swappear modelo
        self._load_model(requested_model_id)

        # 3. Ejecutar lógica específica según el modelo cargado
        model_lower = requested_model_id.lower()

        try:
            if "clip" in model_lower:
                result = self._handle_clip(inputs)
            elif "minilm" in model_lower:
                result = self._handle_minilm(inputs)
            elif "whisper" in model_lower:
                result = self._handle_whisper(inputs)
            elif "vibevoice" in model_lower:
                result = self._handle_tts(inputs)
            else:
                raise ValueError(f"No handler logic defined for model: {requested_model_id}")

            # Enriquecemos la respuesta con metadatos útiles
            result["model_executed"] = requested_model_id
            return result

        except Exception as e:
            logging.error(f"Error during inference execution: {e}")
            raise ValueError(f"Inference failed: {str(e)}")