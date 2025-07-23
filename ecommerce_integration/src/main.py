# ecommerce_integration/src/main.py
import os
import logging
from flask import Flask
from flask_cors import CORS

# Correctly import blueprints from the 'src' package
from src.routes.catalog import catalog_bp
from src.routes.order_processing import order_processing_bp

logging.basicConfig(level=logging.INFO)

app = Flask(__name__)
CORS(app)

# REMOVED: All database and migration setup is now handled by whatsapp-gateway

# Register the blueprints to make their routes active
app.register_blueprint(catalog_bp, url_prefix='/ecommerce')
app.register_blueprint(order_processing_bp, url_prefix='/ecommerce')

# Health check endpoint for this service
@app.route('/ecommerce/health')
def health():
    return {"status": "healthy"}, 200

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5002)