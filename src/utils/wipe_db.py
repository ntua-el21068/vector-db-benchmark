import weaviate
from pymilvus import connections, utility

# Καθαρισμός Weaviate
print("Wiping Weaviate...")
client = weaviate.Client("http://localhost:8080")
client.schema.delete_all()

# Καθαρισμός Milvus
print("Wiping Milvus...")
connections.connect("default", host="localhost", port="19530")
for col in utility.list_collections():
    utility.drop_collection(col)
connections.disconnect("default")

print("All databases are empty.")