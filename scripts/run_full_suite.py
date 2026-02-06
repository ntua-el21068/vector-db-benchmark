import subprocess
import time
import os
import sys
import argparse 

# --- DEFAULT CONFIGURATION ---
ALL_DATABASES = ["milvus", "weaviate"]
ALL_DIMENSIONS = [128, 512, 1024]
SIZES = ["small", "medium", "big"]

QUERIES = [
    "src/queries/query1_city.py",
    "src/queries/query2_range.py",
    "src/queries/query3_combined.py",
    "src/queries/query4_pure_l2.py",
    "src/queries/query5_pure_ip.py"
]

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(SCRIPT_DIR, "../"))

def docker_reset(db):
    print(f"\n[DOCKER] Hard Reset for {db}...")
    if db == "milvus":
        subprocess.run(["docker", "stop", "weaviate_db"], capture_output=True)
        subprocess.run(["docker", "restart", "milvus_db", "milvus-etcd", "milvus-minio"], capture_output=True)
    else:
        subprocess.run(["docker", "stop", "milvus_db", "milvus-etcd", "milvus-minio"], capture_output=True)
        subprocess.run(["docker", "restart", "weaviate_db"], capture_output=True)
    
    print("   -> Waiting 45s for DB to stabilize...")
    time.sleep(45) 

def main():
    # --- 1. ARGUMENT PARSING ---
    parser = argparse.ArgumentParser(description="Run Full Benchmark Suite")
    parser.add_argument("--db", type=str, choices=["milvus", "weaviate", "all"], default="all", help="Database to benchmark")
    parser.add_argument("--dim", type=int, choices=[128, 512, 1024, 0], default=0, help="Dimension to run (0 for all)")
    
    args = parser.parse_args()

    # --- 2. FILTERING BASED ON ARGS ---
    if args.db != "all":
        target_databases = [args.db]
    else:
        target_databases = ALL_DATABASES

    if args.dim != 0:
        target_dimensions = [args.dim]
    else:
        target_dimensions = ALL_DIMENSIONS

    # --- 3. EXECUTION ---
    os.chdir(PROJECT_ROOT)
    print(f"Working Directory set to: {os.getcwd()}")
    print(f"Target DBs: {target_databases}")
    print(f"Target Dims: {target_dimensions}")

    for db in target_databases:
        for dim in target_dimensions:
            
            docker_reset(db) 
            
            for size in SIZES:
                print(f"\n🚀 STARTING EXPERIMENT: {db} | {dim}d | {size}")
                
                load_cmd = ["python3", "src/ingestion/loader_wrapper.py", db, str(dim), size]
                load_proc = subprocess.run(load_cmd)
                
                if load_proc.returncode != 0:
                    print(f" CRASH DURING LOADING {db} {dim} {size}. Skipping queries...")
                    continue 
                
                for q_script in QUERIES:
                    print(f"   -> Running {q_script}...")
                    subprocess.run(["python3", q_script, db, str(dim), size])
                
    print("\n BENCHMARK SUITE COMPLETE. Check results/ folder.")

if __name__ == "__main__":
    main()