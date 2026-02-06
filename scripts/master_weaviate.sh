#!/bin/bash

# --- 1. DYNAMIC PATH CONFIGURATION ---
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

LOG_FILE="$PROJECT_ROOT/results/logs/weaviate_debug.log"
MAIN_CSV="$PROJECT_ROOT/results/final_results_weaviate.csv"
STATS_DIR="$PROJECT_ROOT/results/stats/weaviate"
DOCKER_COMPOSE_FILE="$PROJECT_ROOT/docker/docker-compose.yml"
PYTHON_SCRIPT="$PROJECT_ROOT/src/ingestion/ingest_weaviate.py"

CONTAINER_NAME="weaviate_db"

mkdir -p "$STATS_DIR"
mkdir -p "$(dirname "$LOG_FILE")"

if [ ! -f "$MAIN_CSV" ]; then
    echo "Dimension,Dataset_Size,Time_Seconds,Throughput_VPS,Storage_Size" > "$MAIN_CSV"
fi

# --- SAFETY TRAP  ---
cleanup() {
    echo ""
    echo " INTERRUPTED! Killing processes..."
    if [ ! -z "$STATS_PID" ]; then
        kill $STATS_PID 2>/dev/null
    fi
    exit 1
}
trap cleanup INT TERM

DIMENSIONS=(128 512 1024)
SIZES=("small" "medium" "big")

echo "--- STARTING WEAVIATE AUTOMATION ---" | tee -a "$LOG_FILE"
echo "Timestamp: $(date)" >> "$LOG_FILE"

for dim in "${DIMENSIONS[@]}"; do
    for size in "${SIZES[@]}"; do
        
        TEST_ID="${dim}d_${size}"
        STATS_FILE="${STATS_DIR}/stats_${TEST_ID}.csv"
        
        echo "==============================================" | tee -a "$LOG_FILE"
        echo "🔄 RUNNING TEST: Dim=$dim | Size=$size" | tee -a "$LOG_FILE"
        
        # 1. SURGICAL CLEANUP
        echo "   [Status] Stopping Weaviate..." | tee -a "$LOG_FILE"
    
        docker compose -f "$DOCKER_COMPOSE_FILE" -p vector-bench stop weaviate >> "$LOG_FILE" 2>&1
        docker compose -f "$DOCKER_COMPOSE_FILE" -p vector-bench rm -f weaviate >> "$LOG_FILE" 2>&1
      
        docker volume rm vector-bench_weaviate_data >> "$LOG_FILE" 2>&1
        
        # 2. STARTUP
        echo "   [Status] Starting Weaviate..." | tee -a "$LOG_FILE"
        docker compose -f "$DOCKER_COMPOSE_FILE" -p vector-bench up -d weaviate >> "$LOG_FILE" 2>&1
        
        # 3. WAIT 
        echo "   [Status] Waiting for Weaviate to allow connections..." | tee -a "$LOG_FILE"
     
        timeout 60s bash -c 'until curl -s -o /dev/null http://localhost:8080/v1/.well-known/ready; do sleep 2; done'
       
        sleep 5 
        
        # --- STATS RECORDER ---
        echo "   [Status] Recording Stats -> $STATS_FILE" | tee -a "$LOG_FILE"
        echo "Timestamp,Container,CPU_Perc,Mem_Usage,Net_IO,Block_IO" > "$STATS_FILE"
        (
            while true; do
                ts=$(date +%H:%M:%S)
                
                docker stats --no-stream --format "{{.Name}},{{.CPUPerc}},{{.MemUsage}},{{.NetIO}},{{.BlockIO}}" $CONTAINER_NAME \
                | sed "s/^/$ts,/" >> "$STATS_FILE"
                sleep 5
            done
        ) &
        STATS_PID=$!
        # ----------------------------

        # 4. RUN PYTHON LOADER
        echo "   [Status] Loading Data..." | tee -a "$LOG_FILE"
    
        cd "$PROJECT_ROOT" && run_output=$(python3 "$PYTHON_SCRIPT" $dim $size 2>&1)
        
        # --- STOP STATS ---
        kill $STATS_PID 2>/dev/null
        
        echo "$run_output" >> "$LOG_FILE"

        # 5. EXTRACT METRICS
   
        time_val=$(echo "$run_output" | grep "Time:" | awk '{print $3}')
        throughput_val=$(echo "$run_output" | grep "Throughput:" | awk '{print $3}')
        
        # 6. MEASURE STORAGE
    
        VOL_NAME="vector-bench_weaviate_data"
        storage_val=$(du -sh /var/lib/docker/volumes/$VOL_NAME/_data 2>/dev/null | awk '{print $1}')
        
        if [ -z "$storage_val" ]; then storage_val="0B"; fi

        # 7. SAVE RESULTS
    
        if [ -z "$time_val" ]; then
             echo "$dim,$size,FAILED,FAILED,$storage_val" >> "$MAIN_CSV"
             echo "   [Result] FAILED" | tee -a "$LOG_FILE"
        else
             echo "$dim,$size,$time_val,$throughput_val,$storage_val" >> "$MAIN_CSV"
             echo "   [Result] Time: $time_val | Disk: $storage_val" | tee -a "$LOG_FILE"
        fi
        
    done
done

echo "--- WEAVIATE SUITE COMPLETE ---" | tee -a "$LOG_FILE"