import time, random, numpy as np, weaviate, sys, os
from pymilvus import connections, Collection

# --- PATH CONFIGURATION ---
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(CURRENT_DIR, "../../"))
sys.path.append(PROJECT_ROOT)
from src.utils.metrics import BenchmarkMetrics

def run_experiment(db_type, dim, dataset_size, batch_size=100):
    folder = f"exp_{1 if dim==128 else 2 if dim==512 else 3}_{dim}d"
    path_vectors = os.path.join(PROJECT_ROOT, "data", folder, "vectors.npy")
    
    if not os.path.exists(path_vectors): return

    vectors = np.load(path_vectors, mmap_mode='r')
    max_idx = min(100000 if dataset_size == "small" else 500000 if dataset_size == "medium" else 2000000, vectors.shape[0])
    
    queries = [(vectors[random.randint(0, max_idx - 1)].tolist(), round(random.uniform(0.4, 0.8), 2)) for _ in range(batch_size)]
    tracker = BenchmarkMetrics()

    if db_type == "milvus":
        connections.connect("default", host="localhost", port="19530")
        col = Collection(f"benchmark_{dim}d")
        col.load()
        tracker.start()
        for i, (vec, score) in enumerate(queries):
            start_q = time.time()
            col.search(data=[vec], anns_field="vector", param={"metric_type": "L2", "params": {"nprobe": 10}}, limit=10, expr=f"quality_score > {score}")
            tracker.record_latency(time.time() - start_q)
            if i % 10 == 0: tracker.sample_system_resources()
        tracker.stop()
        col.release()
    elif db_type == "weaviate":
        client = weaviate.Client("http://localhost:8080")
        class_name = f"Benchmark_{dim}d"
        tracker.start()
        for i, (vec, score) in enumerate(queries):
            start_q = time.time()
            where_filter = {"path": ["quality_score"], "operator": "GreaterThan", "valueNumber": score}
            client.query.get(class_name, ["quality_score"]).with_near_vector({"vector": vec}).with_where(where_filter).with_limit(10).do()
            tracker.record_latency(time.time() - start_q)
            if i % 10 == 0: tracker.sample_system_resources()
        tracker.stop()

    results_file = os.path.join(PROJECT_ROOT, "results/stats/query2_range_filter.csv")
    tracker.save_to_csv(results_file, db_type, dim, dataset_size)

if __name__ == "__main__":
    if len(sys.argv) == 4: run_experiment(sys.argv[1], int(sys.argv[2]), sys.argv[3])