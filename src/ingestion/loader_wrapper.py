import numpy as np
import time
import json
import sys
import gc
import os
import weaviate
from pymilvus import connections, FieldSchema, CollectionSchema, DataType, Collection, utility

# --- PATH CONFIGURATION ---
# Βρίσκουμε το Project Root (2 επίπεδα πάνω: src -> ingestion -> root)
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(CURRENT_DIR, "../../"))
DATA_ROOT = os.path.join(PROJECT_ROOT, "data")

# Ρυθμίσεις
MILVUS_CONFIG = {"host": "localhost", "port": "19530"}
WEAVIATE_URL = "http://localhost:8080"

def get_limits(size):
    if size == "small": return 100000
    if size == "medium": return 500000
    if size == "big": return 2000000
    return 0

def load_data(db, dim, size):
    limit = get_limits(size)
    
    # Absolute paths για τα data
    folder = f"exp_{1 if dim==128 else 2 if dim==512 else 3}_{dim}d"
    path_vectors = os.path.join(DATA_ROOT, folder, "vectors.npy")
    path_payloads = os.path.join(DATA_ROOT, folder, "payloads.jsonl")

    print(f"\n>>> LOADING {db.upper()} | DIM: {dim} | SIZE: {size} ({limit} vectors)")

    if not os.path.exists(path_vectors):
        print(f"ERROR: Data file not found at {path_vectors}")
        sys.exit(1)

    # 1. Φόρτωση Δεδομένων
    vectors = np.load(path_vectors, mmap_mode='r')[:limit]
    city_ids = []
    quality_scores = []
    
    with open(path_payloads, 'r') as f:
        for i, line in enumerate(f):
            if i >= limit: break
            data = json.loads(line)
            city_ids.append(data.get('city_id', 0))
            quality_scores.append(data.get('quality_score', 0.0))

    # 2. MILVUS LOAD
    if db == "milvus":
        connections.connect("default", **MILVUS_CONFIG)
        col_name = f"benchmark_{dim}d"
        
        # Reset με retry logic
        for attempt in range(5):
            try:
                if utility.has_collection(col_name):
                    print(f"   [RESET] Dropping collection for fresh {size} start...")
                    utility.drop_collection(col_name)
                    time.sleep(5)
                break
            except Exception as e:
                print(f"   [WAIT] Milvus syncing, retrying drop in 10s...")
                time.sleep(10)

        fields = [
            FieldSchema(name="id", dtype=DataType.INT64, is_primary=True, auto_id=False),
            FieldSchema(name="vector", dtype=DataType.FLOAT_VECTOR, dim=dim),
            FieldSchema(name="city_id", dtype=DataType.INT64),
            FieldSchema(name="quality_score", dtype=DataType.FLOAT)
        ]
        col = Collection(col_name, CollectionSchema(fields))
        # Δημιουργία Index κατευθείαν για να είναι έτοιμο για queries
        col.create_index("vector", {"metric_type": "L2", "index_type": "HNSW", "params": {"M": 16, "efConstruction": 256}})

        step = 5000 
        for i in range(0, len(vectors), step):
            end = i + step
            col.insert([list(range(i, end)), vectors[i:end].tolist(), city_ids[i:end], quality_scores[i:end]])
            if i % 50000 == 0:
                gc.collect()
        
        col.flush()
        col.load()
        print(f"   [DONE] Milvus loaded. Total Entities: {col.num_entities}")

    # 3. WEAVIATE LOAD
    elif db == "weaviate":
        client = weaviate.Client(
            url=WEAVIATE_URL,
            timeout_config=(10, 900)
        )
        class_name = f"Benchmark_{dim}d"
        
        if client.schema.exists(class_name):
            client.schema.delete_class(class_name)

        class_obj = {
            "class": class_name,
            "vectorIndexConfig": {"distance": "l2-squared"},
            "properties": [
                {"name": "city_id", "dataType": ["int"]},
                {"name": "quality_score", "dataType": ["number"]}
            ]
        }
        client.schema.create_class(class_obj)

        client.batch.configure(batch_size=100, dynamic=True)
        with client.batch as batch:
            for i in range(len(vectors)):
                batch.add_data_object({
                    "city_id": int(city_ids[i]),
                    "quality_score": float(quality_scores[i])
                }, class_name, vector=vectors[i])
                if i % 10000 == 0: gc.collect()
        print(f"   [DONE] Weaviate loaded.")

if __name__ == "__main__":
    if len(sys.argv) == 4:
        # Παράμετροι: db, dim, size (π.χ. milvus 128 small)
        load_data(sys.argv[1], int(sys.argv[2]), sys.argv[3])