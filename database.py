
import os
import psycopg
from dotenv import load_dotenv

load_dotenv()


def get_db_connection():
    connection = psycopg.connect(
        host=os.getenv("DB_HOST"),
        port=os.getenv("DB_PORT"),
        dbname=os.getenv("DB_NAME"),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD")
    )

    return connection


def test_connection():
    connection = get_db_connection()

    try:
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT
                    current_database(),
                    PostGIS_Full_Version();
            """)

            result = cursor.fetchone()
            return result

    finally:
        connection.close()
