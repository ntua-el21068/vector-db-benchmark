import os
import numpy as np
import json
import random

# --- CONFIGURATION ---

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.normpath(os.path.join(SCRIPT_DIR, "../../data"))

TOTAL_VECTORS = 2_500_000
TOTAL_VECTORS = 2_500_000 

EXPERIMENTS = [
    {"name": "exp_1_128d",  "dim": 128},
    {"name": "exp_2_512d",  "dim": 512},
    {"name": "exp_3_1024d", "dim": 1024},
]

def generate_dataset(config):
    folder = os.path.join(DATA_DIR, config["name"])
    os.makedirs(folder, exist_ok=True)
    
    vec_file = os.path.join(folder, "vectors.npy")
    payload_file = os.path.join(folder, "payloads.jsonl")
    
    print(f"--- GENERATING {config['name']} ({config['dim']}d) ---")
    
    # 1. Generate Vectors (Float32) with Header
    if os.path.exists(vec_file):
        print(f"  {vec_file} exists. Overwriting...")

    vectors = np.lib.format.open_memmap(vec_file, mode='w+', dtype='float32', shape=(TOTAL_VECTORS, config['dim']))
    
    chunk_size = 100_000
    for i in range(0, TOTAL_VECTORS, chunk_size):
        vectors[i:i+chunk_size] = np.random.rand(chunk_size, config['dim']).astype('float32')
        if i % 500_000 == 0:
            print(f"   -> Generated {i} vectors...")
            
    del vectors # Flush to disk
    print("    Vectors Saved.")

    # 2. Generate Payloads
    print("   -> Generating Metadata...")
    with open(payload_file, "w") as f:
        for i in range(TOTAL_VECTORS):
            record = {
                "id": i,
                "city_id": random.randint(1, 1000),
                "quality_score": round(random.random(), 2)
            }
            f.write(json.dumps(record) + "\n")
    print("    Metadata Saved.")

if __name__ == "__main__":
    for exp in EXPERIMENTS:
        generate_dataset(exp)