# ecommerce_integration/src/routes/catalog.py

from flask import Blueprint, request, jsonify, abort
from src.services.shopify_service import ShopifyService
from src.services.catalog_manager import CatalogManager
import logging

# Setup logger
logger = logging.getLogger(__name__)

catalog_bp = Blueprint('catalog', __name__)
shopify_service = ShopifyService()
catalog_manager = CatalogManager()

def success_response(data: dict, code=200):
    """Consistent success response"""
    response = {'success': True}
    response.update(data)
    return jsonify(response), code

def error_response(message: str, code=500):
    """Consistent error response"""
    logger.error(message)
    return jsonify({'success': False, 'error': message}), code

@catalog_bp.route('/catalog/sync', methods=['POST'])
def sync_catalog():
    """Sync product catalog from Shopify"""
    try:
        force_sync = request.args.get('force', 'false').lower() == 'true'
        result = catalog_manager.sync_catalog(force_sync)
        return success_response({'result': result})
    except Exception as e:
        logger.exception("Failed to sync catalog")
        return error_response("Internal server error")

@catalog_bp.route('/catalog/products/featured', methods=['GET'])
def get_featured_products():
    try:
        limit = int(request.args.get('limit', 10))
        featured = catalog_manager.get_featured_products(limit)
        return success_response({'products': featured, 'count': len(featured)})
    except Exception as e:
        logger.exception("Failed to get featured products")
        return error_response("Internal server error")

@catalog_bp.route('/catalog/products/trending', methods=['GET'])
def get_trending_products():
    try:
        limit = int(request.args.get('limit', 10))
        days = int(request.args.get('days', 7))
        trending = catalog_manager.get_trending_products(limit, days)
        return success_response({'products': trending, 'count': len(trending)})
    except Exception as e:
        logger.exception("Failed to get trending products")
        return error_response("Internal server error")

@catalog_bp.route('/catalog/products/similar/<product_id>', methods=['GET'])
def get_similar_products(product_id):
    try:
        limit = int(request.args.get('limit', 5))
        similar = catalog_manager.get_similar_products(product_id, limit)
        return success_response({'products': similar, 'count': len(similar)})
    except Exception as e:
        logger.exception(f"Failed to get similar products for {product_id}")
        return error_response("Internal server error")

@catalog_bp.route('/catalog/products/bundle', methods=['POST'])
def create_product_bundle():
    try:
        data = request.get_json() or {}
        product_ids = data.get('product_ids')
        if not isinstance(product_ids, list):
            return error_response("product_ids must be a list", 400)
        bundle_name = data.get('bundle_name', 'Custom Bundle')
        discount = float(data.get('discount_percentage', 0))

        bundle = catalog_manager.create_product_bundle(product_ids, bundle_name, discount)
        return success_response({'bundle': bundle}, code=201)
    except Exception as e:
        logger.exception("Failed to create product bundle")
        return error_response("Internal server error")

@catalog_bp.route('/catalog/inventory/low-stock', methods=['GET'])
def get_low_stock_products():
    try:
        threshold = int(request.args.get('threshold', 10))
        low_stock = catalog_manager.get_low_stock_products(threshold)
        return success_response({'products': low_stock, 'count': len(low_stock)})
    except Exception as e:
        logger.exception("Failed to get low stock products")
        return error_response("Internal server error")

@catalog_bp.route('/catalog/inventory/update', methods=['POST'])
def update_inventory():
    try:
        data = request.get_json() or {}
        updates = data.get('updates', [])
        if not isinstance(updates, list):
            return error_response("updates must be a list", 400)

        results = []
        for update in updates:
            variant_id = update.get('variant_id')
            quantity = update.get('quantity')
            if variant_id is not None and quantity is not None:
                result = catalog_manager.update_inventory(variant_id, quantity)
                results.append(result)
        return success_response({'results': results, 'count': len(results)})
    except Exception as e:
        logger.exception("Failed to update inventory")
        return error_response("Internal server error")

@catalog_bp.route('/catalog/products/personalized', methods=['POST'])
def get_personalized_recommendations():
    try:
        data = request.get_json() or {}
        customer_id = data.get('customer_id')
        customer_phone = data.get('customer_phone')
        limit = int(data.get('limit', 10))
        recs = catalog_manager.get_personalized_recommendations(customer_id, customer_phone, limit)
        return success_response({'recommendations': recs, 'count': len(recs)})
    except Exception as e:
        logger.exception("Failed to get personalized recommendations")
        return error_response("Internal server error")

@catalog_bp.route('/catalog/products/filter', methods=['POST'])
def filter_products():
    try:
        data = request.get_json() or {}
        filters = {
            'price_min': data.get('price_min'),
            'price_max': data.get('price_max'),
            'categories': data.get('categories', []),
            'vendors': data.get('vendors', []),
            'tags': data.get('tags', []),
            'in_stock_only': data.get('in_stock_only', False),
            'sort_by': data.get('sort_by', 'relevance'),
            'limit': data.get('limit', 20)
        }
        filtered = catalog_manager.filter_products(filters)
        return success_response({'products': filtered, 'count': len(filtered), 'filters_applied': filters})
    except Exception as e:
        logger.exception("Failed to filter products")
        return error_response("Internal server error")

@catalog_bp.route('/catalog/analytics/popular', methods=['GET'])
def get_popular_products():
    try:
        period = request.args.get('period', '30d')
        limit = int(request.args.get('limit', 10))
        popular = catalog_manager.get_popular_products(period, limit)
        return success_response({'products': popular, 'count': len(popular), 'period': period})
    except Exception as e:
        logger.exception("Failed to get popular products")
        return error_response("Internal server error")

@catalog_bp.route('/catalog/search/suggestions', methods=['GET'])
def get_search_suggestions():
    try:
        query = request.args.get('q', '')
        limit = int(request.args.get('limit', 10))
        suggestions = catalog_manager.get_search_suggestions(query, limit)
        return success_response({'suggestions': suggestions, 'count': len(suggestions)})
    except Exception as e:
        logger.exception("Failed to get search suggestions")
        return error_response("Internal server error")
