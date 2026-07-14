import os 
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker


database_url = os.environ["DATABASE_URL"]
engine = create_engine(database_url)
SessionLocal = sessionmaker(bind=engine)



def check_connection():
    with engine.connect() as connectoin:
        postgres_ver = connectoin.execute(text("SELECT version()")).scalar_one()
        print(postgres_ver)

if __name__ == "__main__":
    check_connection()