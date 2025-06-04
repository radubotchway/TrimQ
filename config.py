import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    SECRET_KEY = os.getenv('SECRET_KEY') or 'your-secret-key-here'
    SQLALCHEMY_DATABASE_URI = os.getenv('DATABASE_URL') or 'postgresql://username:password@localhost/trimq'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    ADMIN_USERNAME = os.getenv('ADMIN_USERNAME') or 'admin'
    ADMIN_PASSWORD = os.getenv('ADMIN_PASSWORD') or 'password'
    BRANCHES = ['main', 'downtown', 'uptown']