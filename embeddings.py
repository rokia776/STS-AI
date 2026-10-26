"""The OpenRouter client and the embeddings built on it.

Used by both task.py (building the database) and app.py (chatting),
so the settings are written once."""

from functools import lru_cache

from langchain_core.embeddings import Embeddings
from openai import OpenAI

import config


@lru_cache(maxsize=1)
def get_client():
    """One shared client (OpenRouter uses the OpenAI API format)."""
    return OpenAI(api_key=config.require_api_key(), base_url=config.BASE_URL)


class OpenRouterEmbeddings(Embeddings):
    def embed_documents(self, texts):
        response = get_client().embeddings.create(model=config.EMBED_MODEL, input=texts)
        return [item.embedding for item in response.data]

    def embed_query(self, text):
        return self.embed_documents([text])[0]