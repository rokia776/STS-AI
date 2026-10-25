import os
from dotenv import load_dotenv
from langchain_openai import OpenAIEmbeddings

load_dotenv()

embeddings = OpenAIEmbeddings(
    model="baai/bge-m3",
    api_key=os.getenv("OPENROUTER_API_KEY"),
    base_url="https://openrouter.ai/api/v1",
    check_embedding_ctx_length=False,
)

text = "GlowDerma moisturizer is suitable for dry skin."

vector = embeddings.embed_query(text)

print("Vector dimensions:", len(vector))
