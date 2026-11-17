"""
Cephalo Vector Embedder Models (FastEmbed, Google Gemini API, ONNX).
"""

import logging
import os
import time
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

import numpy as np

logger = logging.getLogger("cephalo.embedders")

class BaseEmbedder(ABC):
    """Abstract interface for embedding models."""

    @property
    @abstractmethod
    def mode(self) -> str:
        pass

    @property
    @abstractmethod
    def model_name(self) -> str:
        pass

    @property
    @abstractmethod
    def dimension(self) -> int:
        pass

    @abstractmethod
    def embed_texts(self, texts: List[str]) -> List[List[float]]:
        """Embeds a list of clean texts into float vector arrays."""
        pass

    def embed_query(self, query: str) -> List[float]:
        """Embeds a single query string."""
        return self.embed_texts([query])[0]


def get_safe_onnx_providers() -> List[str]:
    """Returns verified ONNX runtime execution providers with zero stderr noise.

    Prevents noisy stderr error dumps on Windows/Linux systems when CUDA/TensorRT
    execution providers are reported by onnxruntime but missing driver/cuBLAS DLLs.
    """
    providers: List[str] = []
    try:
        import onnxruntime as ort
        available = ort.get_available_providers()
        if "CUDAExecutionProvider" in available:
            capi_dir = os.path.join(os.path.dirname(ort.__file__), "capi")
            if sys.platform == "win32":
                cuda_dll = os.path.join(capi_dir, "onnxruntime_providers_cuda.dll")
                if os.path.exists(cuda_dll):
                    try:
                        ctypes.CDLL(cuda_dll)
                        providers.append("CUDAExecutionProvider")
                    except Exception:
                        pass
            else:
                cuda_so = os.path.join(capi_dir, "libonnxruntime_providers_cuda.so")
                if os.path.exists(cuda_so):
                    try:
                        ctypes.CDLL(cuda_so)
                        providers.append("CUDAExecutionProvider")
                    except Exception:
                        pass
    except Exception:
        pass
    providers.append("CPUExecutionProvider")
    return providers


class FastEmbedEmbedder(BaseEmbedder):
    """Mode A: Local / Zero-Leak Embedding via FastEmbed.
    
    Zero data leaves the machine. Runs on ONNX runtime with on-demand GPU acceleration
    and automated CPU fallback.
    Default model: 'Qwen/Qwen3-Embedding-0.6B-Q' (1024 dimensions, 32,768 context tokens, Apache 2.0).
    Alternatives: 'BAAI/bge-small-en-v1.5' (384d), 'sentence-transformers/paraphrase-multilingual-mpnet-base-v2' (768d).
    """

    KNOWN_DIMENSIONS = {
        "Qwen/Qwen3-Embedding-0.6B-Q": 1024,
        "Qwen/Qwen3-Embedding-0.6B": 1024,
        "BAAI/bge-small-en-v1.5": 384,
        "BAAI/bge-base-en-v1.5": 768,
        "nomic-ai/nomic-embed-text-v1.5": 768,
        "nomic-ai/nomic-embed-text-v1.5-Q": 768,
        "sentence-transformers/all-MiniLM-L6-v2": 384,
        "sentence-transformers/paraphrase-multilingual-mpnet-base-v2": 768,
        "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2": 384,
        "jinaai/jina-embeddings-v3": 1024,
    }

    def __init__(self, model_name: str = "Qwen/Qwen3-Embedding-0.6B-Q"):
        self._model_name = model_name
        self._mode = "local"
        
        # Zero-Noise GPU Provider Configuration with Automated CPU Fallback
        providers = get_safe_onnx_providers()

        # Power & Thermal Safety: Determine safe threads to prevent battery spikes/shutdown
        power_threads = 1
        try:
            import psutil
            b = psutil.sensors_battery()
            if b and b.power_plugged:
                power_threads = min(2, os.cpu_count() or 2)
            else:
                power_threads = 1
        except Exception:
            power_threads = 1

        os.environ["OMP_NUM_THREADS"] = str(power_threads)
        os.environ["MKL_NUM_THREADS"] = str(power_threads)

        try:
            from fastembed import TextEmbedding
            self._engine = TextEmbedding(model_name=self._model_name, providers=providers, threads=power_threads)
        except ImportError as e:
            raise ImportError(
                "FastEmbed is not installed. Please install it via: pip install fastembed"
            ) from e

        # Determine dimensionality
        if self._model_name in self.KNOWN_DIMENSIONS:
            self._dimension = self.KNOWN_DIMENSIONS[self._model_name]
        else:
            sample = list(self._engine.embed(["dimension_probe"]))[0]
            self._dimension = len(sample)

    @property
    def mode(self) -> str:
        return self._mode

    @property
    def model_name(self) -> str:
        return self._model_name

    @property
    def dimension(self) -> int:
        return self._dimension

    def embed_texts(self, texts: List[str]) -> List[List[float]]:
        if not texts:
            return []
        embeddings = self._engine.embed(texts)
        return [emb.tolist() for emb in embeddings]

    def embed_query(self, query: str) -> List[float]:
        """Embeds a single query string with instruction prefix if model is Qwen."""
        if "qwen" in self._model_name.lower():
            # Qwen models achieve peak retrieval accuracy when queries use the instruction prefix
            formatted_query = f"Instruct: Given a search query, retrieve relevant passages that answer the query\nQuery:{query}"
            return self.embed_texts([formatted_query])[0]
        return self.embed_texts([query])[0]


class GoogleEmbedder(BaseEmbedder):
    """Mode B: Google Cloud Embeddings via 'text-embedding-004'.
    
    Supports native Matryoshka dimension truncation (e.g. 768 down to 256 or 128).
    Implements Google GenAI SDK with automatic HTTP REST fallback.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        model_name: str = "text-embedding-004",
        dimension: int = 768,
    ):
        self._mode = "google"
        self._model_name = model_name
        self._dimension = dimension
        self.api_key = api_key or os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")

        if not self.api_key:
            raise ValueError(
                "Google Cloud embedding mode requires an API key.\n"
                "Provide it via: --api-key <KEY>, or set environment variable "
                "GEMINI_API_KEY or GOOGLE_API_KEY in .env, or use '--mode local'."
            )

        self._genai_client = None
        try:
            from google import genai
            self._genai_client = genai.Client(api_key=self.api_key)
        except Exception as e:
            logger.debug(f"google-genai client initialization skipped: {e}. Will use REST API.")

    @property
    def mode(self) -> str:
        return self._mode

    @property
    def model_name(self) -> str:
        return self._model_name

    @property
    def dimension(self) -> int:
        return self._dimension

    def _embed_via_sdk(self, texts: List[str]) -> List[List[float]]:
        """Calls Google GenAI SDK."""
        from google.genai import types

        config = types.EmbedContentConfig(output_dimensionality=self._dimension)
        # Google SDK supports list of strings for batch embedding
        response = self._genai_client.models.embed_content(
            model=self._model_name,
            contents=texts,
            config=config,
        )
        return [emb.values for emb in response.embeddings]

    def _embed_via_rest(self, texts: List[str]) -> List[List[float]]:
        """Fallback REST API call."""
        import requests

        url = (
            f"https://generativelanguage.googleapis.com/v1beta/models/"
            f"{self._model_name}:batchEmbedContents?key={self.api_key}"
        )
        payload = {
            "requests": [
                {
                    "model": f"models/{self._model_name}",
                    "content": {"parts": [{"text": t}]},
                    "outputDimensionality": self._dimension,
                }
                for t in texts
            ]
        }
        headers = {"Content-Type": "application/json"}
        resp = requests.post(url, headers=headers, data=json.dumps(payload), timeout=30)
        if resp.status_code != 200:
            raise RuntimeError(
                f"Google Embedding REST API returned HTTP {resp.status_code}: {resp.text}"
            )

        data = resp.json()
        embeddings = data.get("embeddings", [])
        return [item["values"] for item in embeddings]

    def embed_texts(self, texts: List[str]) -> List[List[float]]:
        if not texts:
            return []

        # Batch in chunks of 50 to respect API request constraints
        chunk_size = 50
        all_embeddings: List[List[float]] = []

        for i in range(0, len(texts), chunk_size):
            chunk = texts[i : i + chunk_size]
            if self._genai_client:
                try:
                    all_embeddings.extend(self._embed_via_sdk(chunk))
                    continue
                except Exception as sdk_err:
                    logger.warning(f"SDK embedding call failed ({sdk_err}), trying REST fallback...")

            # REST fallback
            all_embeddings.extend(self._embed_via_rest(chunk))

        return all_embeddings


# ==============================================================================
# 3. Storage Layer (LanceDB Columnar Vector Store)
# ==============================================================================

def create_embedder(
    mode: str = "local",
    model: Optional[str] = None,
    dimension: Optional[int] = None,
    api_key: Optional[str] = None,
) -> BaseEmbedder:
    """Factory creating either FastEmbed (Local) or Google Cloud embedder."""
    if mode.lower() == "local":
        model_name = model or "Qwen/Qwen3-Embedding-0.6B-Q"
        return FastEmbedEmbedder(model_name=model_name)
    elif mode.lower() in ("google", "cloud"):
        model_name = model or "text-embedding-004"
        dim = dimension or 768
        return GoogleEmbedder(api_key=api_key, model_name=model_name, dimension=dim)
    else:
        raise ValueError(f"Unknown embedding mode: '{mode}'. Choose 'local' or 'google'.")


