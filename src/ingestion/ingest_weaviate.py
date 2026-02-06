import weaviate
import numpy as np
import json
import time
import sys
import os

# --- 1. ROBUST PATH CONFIGURATION ---
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(CURRENT_DIR, "../../"))
DATA_ROOT = os.path.join(PROJECT_ROOT, "data")

# --- CONFIGURATION ---
INITIAL_BATCH_SIZE = 100 

if len(sys.argv) != 3:
    print("Usage: python3 ingest_weaviate.py <dim> <size>")
    sys.exit(1)

DIM = int(sys.argv[1])
SIZE_NAME = sys.argv[2] 

if DIM == 128:
    DATA_DIR = os.path.join(DATA_ROOT, "exp_1_128d")
elif DIM == 512:
    DATA_DIR = os.path.join(DATA_ROOT, "exp_2_512d")
else:
    DATA_DIR = os.path.join(DATA_ROOT, "exp_3_1024d")

VEC_FILE = os.path.join(DATA_DIR, "vectors.npy")
PAYLOAD_FILE = os.path.join(DATA_DIR, "payloads.jsonl")

if not os.path.exists(VEC_FILE):
    print(f"[Error] Vectors file not found: {VEC_FILE}")
    sys.exit(1)

# --- TARGETS ---
COUNTS = {"small": 100_000, "medium": 500_000, "big": 2_500_000}
if SIZE_NAME not in COUNTS:
    print(f"[Error] Unknown size: {SIZE_NAME}")
    sys.exit(1)
    
TARGET_COUNT = COUNTS[SIZE_NAME]

print(f"[Status] Connecting to Weaviate (Dim: {DIM}, Size: {SIZE_NAME})...")

client = weaviate.Client(
    url="http://localhost:8080",
    timeout_config=(5, 60),
    startup_period=30
)

class_name = f"Benchmark_{DIM}d"
if client.schema.exists(class_name):
    client.schema.delete_class(class_name)

schema = {
    "classes": [{
        "class": class_name,
        "vectorizer": "none",
        "properties": [
            {"name": "city_id", "dataType": ["int"]},
            {"name": "quality_score", "dataType": ["number"]}
        ]
    }]
}
client.schema.create(schema)
print(f"   -> Created Schema: {class_name}")

print(f"[Status] STARTING WEAVIATE BENCHMARK")
vectors = np.load(VEC_FILE, mmap_mode="r")
payloads = open(PAYLOAD_FILE, "r")

start_time = time.time()
inserted_count = 0

# --- CRITICAL STABILITY CONFIGURATION ---
# 1. batch_size=100: Μικρά πακέτα φεύγουν γρήγορα.
# 2. dynamic=True: Αν αργεί η βάση, το batch μικραίνει αυτόματα.
# 3. num_workers=1: Σειριακή αποστολή για να μην γίνει OOM Kill.
# 4. retries: Αν αποτύχει ένα πακέτο, ξαναπροσπαθεί 3 φορές.
client.batch.configure(
    batch_size=INITIAL_BATCH_SIZE, 
    dynamic=True,
    num_workers=1,
    timeout_retries=3,
    connection_error_retries=3
) 

try:
    with client.batch as batch:
        for i in range(TARGET_COUNT):
            vec = vectors[i]
            line = payloads.readline()
            
            if not line:
                break
                
            meta = json.loads(line)
            
            batch.add_data_object(
                data_object={
                    "city_id": meta["city_id"],
                    "quality_score": meta["quality_score"]
                },
                class_name=class_name,
                vector=vec
            )
            
            inserted_count += 1
            if inserted_count % 5000 == 0:
                print(f"   -> Inserted {inserted_count} / {TARGET_COUNT}")

except Exception as e:
    print(f"[ERROR] Batch ingestion failed: {e}")

finally:
    payloads.close()

end_time = time.time()
duration = end_time - start_time

if duration == 0: duration = 0.01

throughput = inserted_count / duration

print(f"[Result] FINISHED: {class_name}")
print(f"[Result] Time: {duration:.2f} seconds") 
print(f"[Result] Throughput: {throughput:.2f} vectors/sec")