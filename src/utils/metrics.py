import time
import psutil
import numpy as np
import os
import csv

class BenchmarkMetrics:
    def __init__(self):
        self.latencies = []
        self.cpu_readings = []
        self.memory_readings = []
        self.start_time = 0
        self.end_time = 0

    def start(self):
        self.latencies = []
        self.cpu_readings = []
        self.memory_readings = []
        self.start_time = time.time()

    def stop(self):
        self.end_time = time.time()

    def record_latency(self, seconds):
        self.latencies.append(seconds)

    def sample_system_resources(self):
        self.cpu_readings.append(psutil.cpu_percent(interval=None))
        self.memory_readings.append(psutil.virtual_memory().percent)

    def get_stats(self):
        """Υπολογίζει τα meaningful statistics"""
        total_time = self.end_time - self.start_time
        count = len(self.latencies)
        
        if count == 0:
            return None

        avg_lat = np.mean(self.latencies)
        p95_lat = np.percentile(self.latencies, 95) # Το 95% των queries κάτω από αυτό
        std_dev = np.std(self.latencies)           # Η σταθερότητα της βάσης
        throughput = count / total_time if total_time > 0 else 0
        
        avg_cpu = np.mean(self.cpu_readings) if self.cpu_readings else 0
        avg_mem = np.mean(self.memory_readings) if self.memory_readings else 0

        return {
            "Avg Latency (s)": round(avg_lat, 5),
            "P95 Latency (s)": round(p95_lat, 5),
            "Std Dev (s)": round(std_dev, 5),
            "Throughput (QPS)": round(throughput, 2),
            "Avg CPU (%)": round(avg_cpu, 1),
            "Avg MEM (%)": round(avg_mem, 1)
        }

    def save_to_csv(self, file_path, db_name, dimension, dataset_size):
        """Αποθηκεύει τα αποτελέσματα στο Master CSV του συγκεκριμένου Query"""
        stats = self.get_stats()
        if not stats:
            return

        # Αν ο φάκελος δεν υπάρχει, τον φτιάχνουμε
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        
        file_exists = os.path.isfile(file_path)
        
        with open(file_path, mode='a', newline='') as csvfile:
            fieldnames = ["Database", "Dimension", "Dataset_Size"] + list(stats.keys())
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)

            if not file_exists:
                writer.writeheader() # Γράφει κεφαλίδες μόνο την πρώτη φορά

            # Συνδυάζουμε τα info με τα στατιστικά
            row = {"Database": db_name, "Dimension": dimension, "Dataset_Size": dataset_size}
            row.update(stats)
            writer.writerow(row)