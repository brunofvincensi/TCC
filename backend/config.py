import os
from datetime import timedelta
from dotenv import load_dotenv

load_dotenv()

class Config:
    SQLALCHEMY_DATABASE_URI = os.getenv('DATABASE_URL')
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    JWT_SECRET_KEY = os.getenv('JWT_SECRET_KEY')
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(hours=1)
    APP_NAME = os.getenv('APP_NAME', 'Flask JWT API')  # 'Flask JWT API' é o padrão
    APP_VERSION = '1.0.0'

    # Configurações do scheduler de preços
    ENABLE_PRICE_SCHEDULER = os.getenv('ENABLE_PRICE_SCHEDULER', 'false').lower() == 'true'
    PRICE_SCHEDULER_HOUR = int(os.getenv('PRICE_SCHEDULER_HOUR', '23'))
    PRICE_SCHEDULER_MINUTE = int(os.getenv('PRICE_SCHEDULER_MINUTE', '0'))