import psycopg2
import json

class VectorSerializer:
    def __init__(self, connection_params):
        self.connection_params = {
    'dbname': 'railway',
    'user': 'postgres',
    'password': 'dpDImMxLopKUUrwvzhFsFcCfuShFyBbt',
    'host': 'postgres-production-6a64.up.railway.app',
    'port': '5432'
}

    def serialize_vector(self, vector_data):
        # Convert the vector data to JSON format
        return json.dumps(vector_data)

    def store_vector(self, vector_id, vector_data):
        serialized_data = self.serialize_vector(vector_data)
        
        # Connect to the Postgres database
        with psycopg2.connect(**self.connection_params) as conn:
            with conn.cursor() as cursor:
                cursor.execute("INSERT INTO vectors (vector_id, data) VALUES (%s, %s);",
                               (vector_id, serialized_data))
                conn.commit()  
                
    def retrieve_vector(self, vector_id):
        with psycopg2.connect(**self.connection_params) as conn:
            with conn.cursor() as cursor:
                cursor.execute("SELECT data FROM vectors WHERE vector_id = %s;", (vector_id,))
                result = cursor.fetchone()
                if result:
                    # Return parsed JSON data
                    return json.loads(result[0])
                return None

# Example usage if this script is run directly:
# Example usage if this script is run directly:
if __name__ == '__main__':
    connection_info = {
        'dbname': 'railway',
        'user': 'postgres',
        'password': 'dpDImMxLopKUUrwvzhFsFcCfuShFyBbt',
        'host': 'postgres-production-6a64.up.railway.app',
        'port': '5432',
    }
    connection_info = {
    'dbname': 'railway',
    'user': 'postgres',
    'password': 'dpDImMxLopKUUrwvzhFsFcCfuShFyBbt',
    'host': 'postgres-production-6a64.up.railway.app',
    'port': '5432',
    'host': 'postgres-production-6a64.up.railway.app',

        'dbname': 'your_db_name',
        'user': 'your_username',
        'password': 'your_password',
        'host': 'localhost',
        'port': '5432'
    }
    serializer = VectorSerializer(connection_info)
    # Replace these with realistic test values
    sample_vector_id = 'vector_1'
    sample_vector_data = [0.1, 0.2, 0.3, 0.4]  
    serializer.store_vector(sample_vector_id, sample_vector_data)
    retrieved_vector = serializer.retrieve_vector(sample_vector_id)
    print(retrieved_vector)  
