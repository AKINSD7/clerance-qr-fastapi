from dotenv import load_dotenv
import os

load_dotenv()

print("DATABASE_URL:", os.getenv("DATABASE_URL"))
print("BASE_URL:", os.getenv("BASE_URL"))
