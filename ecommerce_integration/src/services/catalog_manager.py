import os
import requests
import json
import logging # Import the logging library
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from src.services.shopify_service import ShopifyService

# Configure logger
logger = logging.getLogger(__name__)

class CatalogManager:
    def __init__(self):
        self.shopify_service = ShopifyService()
        self.cache_duration = 3600  # 1 hour cache
        self._product_cache = {}
        self._cache_timestamp = None

    def sync_catalog(self, force_sync: bool = False) -> Dict[str, Any]:
        """Sync product catalog from Shopify"""
        try:
            if not force_sync and self._is_cache_valid():
                return {
                    'status': 'cached',
                    'message': 'Using cached catalog data',
                    'last_sync': self._cache_timestamp
                }

            products = self.shopify_service.get_all_products()
            processed_products = [self._process_product_data(p) for p in products]
            self._product_cache = {p['id']: p for p in processed_products}
            self._cache_timestamp = datetime.now()
            
            # --- Logging Addition ---
            # This will log the tags of the first product to help with diagnostics.
            if processed_products:
                logger.info(f"[Catalog Sync] Sample tags for product '{processed_products[0]['title']}': {processed_products[0]['tags']}")

            return {
                'status': 'synced',
                'message': f'Synced {len(processed_products)} products',
                'product_count': len(processed_products),
                'last_sync': self._cache_timestamp
            }
        except Exception as e:
            logger.error(f'Sync failed: {str(e)}') # Changed to logger.error for better tracking
            return {'status': 'error', 'message': f'Sync failed: {str(e)}'}

    def filter_products(self, filters: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Advanced product filtering with normalized inputs."""
        try:
            self._ensure_cache()
            filtered_products = list(self._product_cache.values())

            # Apply tag filters
            if filters.get('tags'):
                search_tags = [tag.lower().strip() for tag in filters['tags']]
                filtered_products = [
                    p for p in filtered_products
                    if any(tag in p.get('tags', []) for tag in search_tags)
                ]
            
            # (Other filters like price, category, etc. would go here)

            limit = filters.get('limit', 20)
            return filtered_products[:limit]
        except Exception as e:
            logger.error(f"Error filtering products: {str(e)}") # Changed to logger.error
            return []

    def _process_product_data(self, product: Dict[str, Any]) -> Dict[str, Any]:
        """Process, clean, and enhance product data."""
        try:
            # Main fix: Clean and normalize tags
            tags_raw = product.get('tags', '')
            processed_tags = [tag.strip().lower() for tag in tags_raw.split(',')] if tags_raw else []

            processed = {
                'id': product.get('id'),
                'title': product.get('title'),
                'tags': processed_tags,
                # ... other fields
            }

            # Robust price handling
            variants = product.get('variants', [])
            if variants:
                prices = [float(v.get('price') or 0) for v in variants if 'price' in v and v.get('price')]
                processed['price_range'] = {
                    'min': min(prices) if prices else 0,
                    'max': max(prices) if prices else 0
                }
            else:
                processed['price_range'] = {'min': 0, 'max': 0}

            return processed
        except Exception as e:
            logger.error(f"Error processing product data for ID {product.get('id')}: {str(e)}") # Changed to logger.error
            return {} # Return empty dict to avoid propagating faulty data
            
    def _ensure_cache(self):
        if not self._is_cache_valid():
            self.sync_catalog()

    def _is_cache_valid(self) -> bool:
        if not self._product_cache or not self._cache_timestamp:
            return False
        cache_age = (datetime.now() - self._cache_timestamp).total_seconds()
        return cache_age < self.cache_duration

    # ... The rest of the original methods (get_featured_products, etc.)