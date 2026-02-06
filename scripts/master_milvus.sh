#!/bin/bash

# --- 1. DYNAMIC PATH CONFIGURATION ---
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

LOG_FILE="$PROJECT_ROOT/results/logs/milvus_debug.log"
MAIN_CSV="$PROJECT_ROOT/results/final_results_milvus.csv"
STATS_DIR="$PROJECT_ROOT/results/stats/milvus"
DOCKER_COMPOSE_FILE="$PROJECT_ROOT/docker/docker-compose.yml"
PYTHON_SCRIPT="$PROJECT_ROOT/src/ingestion/ingest_milvus.py"

VOLUME_PATH="/var/lib/docker/volumes/vector-bench_milvus_minio/_data"

mkdir -p "$STATS_DIR"
mkdir -p "$(dirname "$LOG_FILE")"

if [ ! -f "$MAIN_CSV" ]; then
    echo "Dimension,Dataset_Size,Time_Seconds,Throughput_VPS,Storage_Size" > "$MAIN_CSV"
fi

#  Test Matrix
DIMENSIONS=(128 512 1024)
SIZES=("small" "medium" "big")

echo "--- STARTING MILVUS AUTOMATION ---" | tee -a "$LOG_FILE"
echo "Timestamp: $(date)" >> "$LOG_FILE"

for dim in "${DIMENSIONS[@]}"; do
    for size in "${SIZES[@]}"; do
        
        TEST_ID="${dim}d_${size}"
        STATS_FILE="${STATS_DIR}/stats_${TEST_ID}.csv"
        
        echo "==============================================" | tee -a "$LOG_FILE"
        echo "🔄 RUNNING TEST: Dimension=$dim | Size=$size" | tee -a "$LOG_FILE"
        echo "==============================================" | tee -a "$LOG_FILE"

        # 1. SYSTEM RESET 
        echo "   [Status] Cleaning Docker environment..." | tee -a "$LOG_FILE"
        docker compose -f "$DOCKER_COMPOSE_FILE" -p vector-bench down -v >> "$LOG_FILE" 2>&1
        
        # 2. STARTUP
        echo "   [Status] Starting Milvus..." | tee -a "$LOG_FILE"
        docker compose -f "$DOCKER_COMPOSE_FILE" -p vector-bench up -d milvus-standalone milvus-minio milvus-etcd >> "$LOG_FILE" 2>&1
        
        # 3. STABILIZATION
        echo "   [Status] Waiting 45s for database health..." | tee -a "$LOG_FILE"
        sleep 45

        # --- STATS RECORDER ---
        echo "   [Status] Starting Stats Recorder -> $STATS_FILE" | tee -a "$LOG_FILE"
        echo "Timestamp,Container,CPU_Perc,Mem_Usage,Net_IO,Block_IO" > "$STATS_FILE"
        
        (
            while true; do
                timestamp=$(date +%H:%M:%S)
                # Φιλτράρουμε μόνο τα containers αυτού του project
                docker stats --no-stream --format "{{.Name}},{{.CPUPerc}},{{.MemUsage}},{{.NetIO}},{{.BlockIO}}" \
                $(docker ps --format "{{.Names}}" | grep "vector-bench") \
                | sed "s/^/$timestamp,/" >> "$STATS_FILE"
                sleep 5
            done
        ) &
        STATS_PID=$! 
        # ----------------------

        # 4. EXECUTION 
        echo "   [Status] Running Ingestion Script..." | tee -a "$LOG_FILE"
        cd "$PROJECT_ROOT" && run_output=$(python3 "$PYTHON_SCRIPT" $dim $size 2>&1)
        
        # --- STOP STATS ---
        kill $STATS_PID
        echo "   [Status] Stats Recorder Stopped." | tee -a "$LOG_FILE"

        echo "$run_output" >> "$LOG_FILE"

        # 5. METRIC EXTRACTION
        time_val=$(echo "$run_output" | grep "Time:" | awk '{print $3}')
        throughput_val=$(echo "$run_output" | grep "Throughput:" | awk '{print $3}')

        # 6. STORAGE MEASUREMENT 
        storage_val=$(du -sh $VOLUME_PATH 2>/dev/null | awk '{print $1}')
        if [ -z "$storage_val" ]; then storage_val="0B"; fi

        # 7. DATA COMMIT
        echo "$dim,$size,$time_val,$throughput_val,$storage_val" >> "$MAIN_CSV"
        
        echo "   [Result] Time: $time_val | Disk: $storage_val" | tee -a "$LOG_FILE"
        echo "   [Status] Test Complete." | tee -a "$LOG_FILE"
        
    done
done

echo "--- MILVUS SUITE COMPLETE ---" | tee -a "$LOG_FILE"