import time
import numpy as np
import json
import sys
import os
from pymilvus import (
    connections,
    utility,
    FieldSchema,
    CollectionSchema,
    DataType,
    Collection,
)

# --- 1. ROBUST PATH CONFIGURATION ---
# Βρίσκουμε το Project Root δυναμικά (2 επίπεδα πάνω από το src/ingestion/)
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(CURRENT_DIR, "../../"))
DATA_ROOT = os.path.join(PROJECT_ROOT, "data")

# --- CONFIGURATION ---
HOST = "localhost"
PORT = "19530"
BATCH_SIZE = 5000

# Map dimensions to their folder names using ABSOLUTE PATHS
EXPERIMENTS = {
    128:  {"folder": os.path.join(DATA_ROOT, "exp_1_128d")},
    512:  {"folder": os.path.join(DATA_ROOT, "exp_2_512d")},
    1024: {"folder": os.path.join(DATA_ROOT, "exp_3_1024d")},
}

# --- TARGETS ---
COUNTS = {"small": 100_000, "medium": 500_000, "big": 2_500_000}

def connect_db():
    print(f"[Status] Connecting to Milvus at {HOST}:{PORT}...")
    connections.connect("default", host=HOST, port=PORT)

def create_collection(collection_name, dim):
    if utility.has_collection(collection_name):
        print(f"[Status] Dropping old collection: {collection_name}")
        utility.drop_collection(collection_name)

    print(f"[Status] Creating new collection: {collection_name} (Dim: {dim})")
    fields = [
        FieldSchema(name="id", dtype=DataType.INT64, is_primary=True, auto_id=False),
        FieldSchema(name="vector", dtype=DataType.FLOAT_VECTOR, dim=dim),
        FieldSchema(name="city_id", dtype=DataType.INT32),
        FieldSchema(name="quality_score", dtype=DataType.FLOAT),
    ]
    schema = CollectionSchema(fields, f"Benchmark dim {dim}")
    return Collection(collection_name, schema)

def load_data(dim, mode):
    connect_db()
    
    config = EXPERIMENTS[dim]
    collection_name = f"benchmark_{dim}d"
    
    # Χρησιμοποιούμε τα absolute paths που ορίσαμε στο EXPERIMENTS
    vectors_file = os.path.join(config["folder"], "vectors.npy")
    payloads_file = os.path.join(config["folder"], "payloads.jsonl")
    
    if not os.path.exists(vectors_file):
        print(f"[Error] Data file not found: {vectors_file}")
        sys.exit(1)

    limit_count = COUNTS[mode]
    collection = create_collection(collection_name, dim)
    
    print(f"\n[Status] STARTING BENCHMARK: DIM={dim} | MODE={mode.upper()}")
    print(f"   Target: {limit_count:,} vectors")
    
    # Check actual file size (Assuming master dataset is 2.5M)
    file_shape = (2_500_000, dim) 
    vectors = np.memmap(vectors_file, dtype='float32', mode='r', shape=file_shape)
    
    start_time = time.time()
    
    metadata_buffer = []
    vector_buffer = []
    ids_buffer = []
    
    with open(payloads_file, "r") as f:
        for i, line in enumerate(f):
            if i >= limit_count: break
                
            record = json.loads(line)
            ids_buffer.append(record["id"])
            vector_buffer.append(vectors[i])
            metadata_buffer.append({
                "city_id": record["city_id"], 
                "quality_score": record["quality_score"]
            })
            
            if len(ids_buffer) >= BATCH_SIZE:
                collection.insert([
                    ids_buffer,
                    vector_buffer,
                    [m["city_id"] for m in metadata_buffer],
                    [m["quality_score"] for m in metadata_buffer]
                ])
                ids_buffer, vector_buffer, metadata_buffer = [], [], []
                print(f"   -> Inserted {i+1:,} / {limit_count:,}", end="\r")

    if ids_buffer:
        collection.insert([
            ids_buffer,
            vector_buffer,
            [m["city_id"] for m in metadata_buffer],
            [m["quality_score"] for m in metadata_buffer]
        ])

    print("\n   [Status] Flushing data to disk...")
    collection.flush()
    duration = time.time() - start_time
    
    print(f"\n[Result] FINISHED: DIM={dim} | MODE={mode.upper()}")
    print(f"[Result] Time: {duration:.2f} seconds")
    print(f"[Result] Throughput: {limit_count / duration:.2f} vectors/sec")

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python3 ingest_milvus.py [dim] [small|medium|big]")
        sys.exit(1)
        
    dim = int(sys.argv[1])
    mode = sys.argv[2]
    load_data(dim, mode)