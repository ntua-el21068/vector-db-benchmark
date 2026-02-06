# 🚀 Vector Database Benchmark Suite: Milvus vs. Weaviate

A comprehensive benchmarking framework designed to evaluate and compare the performance of **Milvus** and **Weaviate** vector databases. This project tests ingestion throughput, resource utilization (CPU/RAM), and query latency across different vector dimensions and dataset sizes.

## 📊 Overview

This suite conducts experiments based on the following parameters:
* **Dimensions:** 128d, 512d, 1024d
* **Dataset Sizes:** Small (100k), Medium (500k), Big (2.5M)
* **Metrics:**
    * Ingestion Time & Throughput (Vectors Per Second)
    * System Resource Usage (Docker Stats)
    * Query Latency (Avg, P95, P99) & QPS (Queries Per Second)

---

## 🛠️ Prerequisites

* **Python 3.8+**
* **Docker** & **Docker Compose**
* Python dependencies:
    ```bash
    pip install -r requirements.txt
    ```

---

## 🚦 Execution Guide

Follow these steps sequentially to reproduce the benchmark results.

### 1. Data Generation

First, generate the synthetic datasets (vectors `.npy` and metadata `.jsonl`). The script automatically organizes data into experiment folders (e.g., `data/exp_1_128d`).

```bash
cd src/generators
python3 generate_data.py
```
> **Output:** Data will be generated in the `../../data/` directory relative to the script.

### 2. Environment Setup

Start the containerized environment. This initializes Milvus (Standalone), Etcd, MinIO, and Weaviate.

```bash
# From the project root
docker compose -f docker/docker-compose.yml -p vector-bench up -d
```
*Wait approximately 30-60 seconds for all services to become healthy.*

### 3. Ingestion & Indexing Benchmarks

We use dedicated bash scripts to automate the lifecycle of the benchmark: **Stop Container -> Wipe Volume -> Start -> Record Stats -> Ingest Data**.

#### Run Milvus Benchmark:
```bash
cd scripts
chmod +x master_milvus.sh
./master_milvus.sh
```

#### Run Weaviate Benchmark:
```bash
cd scripts
chmod +x master_weaviate.sh
./master_weaviate.sh
```

> **Results:**
> * **CSV Metrics:** `results/final_results_milvus.csv` & `results/final_results_weaviate.csv`
> * **Resource Stats:** Detailed CPU/MEM logs per second in `results/stats/`

### 4. Query Performance Suite

Once data is ingested, run the query benchmark suite to measure search performance (Latency & QPS). You can target specific databases or dimensions using flags.

```bash
cd scripts

# Run full suite (All DBs, All Dimensions)
python3 run_full_suite.py

# OR run specific tests
python3 run_full_suite.py --db milvus --dim 128
python3 run_full_suite.py --db weaviate --dim 1024
```

> **Results:** Query metrics are saved in `results/queries/summary_metrics.csv`.

---

## 📂 Project Structure

```text
vector-db-benchmark/
├── data/                 # Generated datasets (Not in git)
├── docker/               # Docker Compose configuration
├── results/              # CSV outputs and Logs
├── scripts/              # Automation shell scripts (Master scripts)
├── src/
│   ├── generators/       # Data generation logic
│   ├── ingestion/        # Database loaders (Python)
│   ├── queries/          # Search scenarios
│   └── utils/            # Helper scripts
└── README.md
```

## ⚠️ Troubleshooting

* **OOM Kill:** If Weaviate crashes during ingestion, ensure `ingest_weaviate.py` is configured with `num_workers=1` to limit concurrent HTTP requests on memory-constrained systems.
* **Docker Conflicts:** If containers fail to start, use `docker stop $(docker ps -q)` to stop all running containers and try again.
