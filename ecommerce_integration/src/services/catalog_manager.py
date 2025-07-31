import os
import requests
import json
import logging
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
            
            if processed_products:
                logger.info(f"[Catalog Sync] Sample tags for product '{processed_products[0]['title']}': {processed_products[0].get('tags')}")

            return {
                'status': 'synced',
                'message': f'Synced {len(processed_products)} products',
                'product_count': len(processed_products),
                'last_sync': self._cache_timestamp
            }
        except Exception as e:
            logger.error(f'Sync failed: {str(e)}')
            return {'status': 'error', 'message': f'Sync failed: {str(e)}'}

    def filter_products(self, filters: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Advanced product filtering with support for keywords, price range, and exact tag matching.
        """
        try:
            self._ensure_cache()
            products = list(self._product_cache.values())

            # --- Keyword Search ---
            # Searches in title, product_type, and vendor.
            if keywords := filters.get('keywords'):
                search_terms = [kw.lower().strip() for kw in keywords]
                products = [
                    p for p in products if any(
                        term in (p.get('title', '') + p.get('product_type', '') + p.get('vendor', '')).lower()
                        for term in search_terms
                    )
                ]

            # --- Exact Tag Filtering ---
            # Matches whole tags only.
            if tags := filters.get('tags'):
                search_tags = {tag.lower().strip() for tag in tags}
                products = [
                    p for p in products if search_tags.issubset(set(p.get('tags', [])))
                ]
            
            # --- Price Range Filtering ---
            # Filters based on a min and/or max price.
            min_price = filters.get('min_price')
            max_price = filters.get('max_price')
            if min_price is not None or max_price is not None:
                products = [
                    p for p in products if self._is_in_price_range(p, min_price, max_price)
                ]

            # (Other filters like vendor, product_type can be added here following the same pattern)

            limit = filters.get('limit', 20)
            return products[:limit]
        except Exception as e:
            logger.error(f"Error filtering products: {str(e)}")
            return []
            
    def _is_in_price_range(self, product: Dict[str, Any], min_price: Optional[float], max_price: Optional[float]) -> bool:
        """Helper function to check if a product's price is within the given range."""
        price_range = product.get('price_range', {})
        product_min_price = price_range.get('min', 0)
        
        if min_price is not None and product_min_price < min_price:
            return False
        if max_price is not None and product_min_price > max_price:
            return False
            
        return True


    def _process_product_data(self, product: Dict[str, Any]) -> Dict[str, Any]:
        """Process, clean, and enhance product data."""
        try:
            tags_raw = product.get('tags', '')
            processed_tags = [tag.strip().lower() for tag in tags_raw.split(',')] if tags_raw else []

            processed = {
                'id': product.get('id'),
                'title': product.get('title'),
                'vendor': product.get('vendor'),
                'product_type': product.get('product_type'),
                'tags': processed_tags,
            }

            variants = product.get('variants', [])
            if variants:
                prices = [float(v.get('price') or 0) for v in variants if v.get('price')]
                processed['price_range'] = {
                    'min': min(prices) if prices else 0,
                    'max': max(prices) if prices else 0
                }
            else:
                processed['price_range'] = {'min': 0, 'max': 0}

            return processed
        except Exception as e:
            logger.error(f"Error processing product data for ID {product.get('id')}: {str(e)}")
            return {}
            
    def _ensure_cache(self):
        if not self._is_cache_valid():
            self.sync_catalog()

    def _is_cache_valid(self) -> bool:
        if not self._product_cache or not self._cache_timestamp:
            return False
        cache_age = (datetime.now() - self._cache_timestamp).total_seconds()
        return cache_age < self.cache_duration