from datetime import datetime
from assignment_1.celery_config import celery
from assignment_1.database.database import SessionLocal
from assignment_1.model.model import AccessLog
from assignment_1.database import database
import sqlite3

@celery.task
def log_access(text: str):
    try:
        conn = sqlite3.connect('../database.db')
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM accesslog')
        rows = cursor.fetchall()

        # Print the rows
        for row in rows:
            print(row)

        conn.commit()
        cursor.close()
        conn.close()

    except Exception as e:
        print("Error in celery task", e)
