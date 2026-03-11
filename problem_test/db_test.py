from app.services.vector_store import VectorStore

vs = VectorStore(collection_name="legal_contracts_v2_cosine")
info = vs.get_collection_info()
print(info)