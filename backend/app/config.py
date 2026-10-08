import os
from dotenv import load_dotenv

load_dotenv()

MINIMOTH_API_KEY = os.getenv("MINIMOTH_API_KEY", "")
DATABASE_PATH = os.getenv("DATABASE_PATH", "./journal.db")
MINIMOTH_BASE_URL = "https://api.minimoth.dev"
