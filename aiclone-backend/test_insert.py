import psycopg2

# Connection parameters for internal access
connection_info = {
    'dbname': 'railway',  # the database name
    'user': 'postgres',    # the PostgreSQL user
    'password': 'dpDImMxLopKUUrwvzhFsFcCfuShFyBbt',  # your password
    'host': 'postgres.railway.internal',  # Internal host
    'port': '5432'  # Use the internal port
}

try:
    connection = psycopg2.connect(**connection_info)
    with connection:
        cursor = connection.cursor()
        # Create a test table if it doesn't exist
        cursor.execute("CREATE TABLE IF NOT EXISTS briefs (id SERIAL PRIMARY KEY, content TEXT, date TIMESTAMP);")
        
        # Insert a sample brief
        cursor.execute("INSERT INTO briefs (content, date) VALUES (%s, NOW());", ("Sample daily brief",))
        connection.commit()
        print("Data inserted successfully!")
except Exception as e:
    print(f"Connection failed: {e}")
finally:
    if 'connection' in locals():
        connection.close()
