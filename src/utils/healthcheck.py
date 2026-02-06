import weaviate
from pymilvus import connections, utility

def check_weaviate():
    print("--- Έλεγχος Weaviate ---")
    try:
        # Σύνδεση με τον παλιό τρόπο (v3)
        client = weaviate.Client("http://localhost:8080")
        
        if client.is_ready():
            print("✅ Weaviate: ONLINE")
            schema = client.schema.get()
            classes = schema.get('classes', [])
            if not classes:
                print("ℹ️  Δεν βρέθηκαν Classes (είναι άδεια).")
            else:
                print(f"📊 Βρέθηκαν {len(classes)} classes:")
                for c in classes:
                    # Παίρνουμε τον αριθμό των αντικειμένων
                    count = client.query.aggregate(c['class']).with_meta_count().do()
                    total = count['data']['Aggregate'][c['class']][0]['meta']['count']
                    print(f"   - {c['class']}: {total} vectors")
        else:
            print("❌ Weaviate: NOT READY")
    except Exception as e:
        print(f"❌ Σφάλμα σύνδεσης στη Weaviate: {e}")

def check_milvus():
    print("\n--- Έλεγχος Milvus ---")
    try:
        # Σύνδεση στη Milvus
        connections.connect("default", host="localhost", port="19530")
        print("✅ Milvus: ONLINE")
        
        collections = utility.list_collections()
        if not collections:
            print("ℹ️  Δεν βρέθηκαν Collections (είναι άδεια).")
        else:
            print(f"📊 Βρέθηκαν {len(collections)} collections:")
            for col_name in collections:
                from pymilvus import Collection
                col = Collection(col_name)
                print(f"   - {col_name}: {col.num_entities} vectors")
    except Exception as e:
        print(f"❌ Σφάλμα σύνδεσης στη Milvus: {e}")

if __name__ == "__main__":
    check_weaviate()
    check_milvus()
