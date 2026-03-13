import psycopg2

connection_info = {
    'dbname': 'railway',
    'user': 'postgres',
    'password': 'dpDImMxLopKUUrwvzhFsFcCfuShFyBbt',
    'host': 'postgres-production-6a64.up.railway.app',
    'port': '5432'
}

try:
    connection = psycopg2.connect(**connection_info)
    print("Connection successful!")
except Exception as e:
    print(f"Connection failed: {e}")
