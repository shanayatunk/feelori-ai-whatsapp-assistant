import os
import requests
from typing import List, Dict, Any, Optional

class ShopifyService:
    def __init__(self):
        self.store_url = os.getenv("SHOPIFY_STORE_URL")
        self.access_token = os.getenv("SHOPIFY_ACCESS_TOKEN")
        self.api_version = "2024-01"
        self.base_url = f"https://{self.store_url}/admin/api/{self.api_version}"
        self.headers = {
            "Content-Type": "application/json",
            "X-Shopify-Access-Token": self.access_token,
        }

    def get_all_products(self) -> List[Dict[str, Any]]:
        """Fetches all products from the Shopify store."""
        products = []
        endpoint = "/products.json"
        url = self.base_url + endpoint

        while url:
            response = requests.get(url, headers=self.headers)
            if response.status_code == 200:
                data = response.json()
                products.extend(data.get("products", []))

                # Check for the next page link in the headers
                link_header = response.headers.get("Link")
                if link_header:
                    links = requests.utils.parse_header_links(link_header)
                    url = None
                    for link in links:
                        if link.get("rel") == "next":
                            url = link.get("url")
                            break
                else:
                    url = None
            else:
                print(f"Failed to fetch products: {response.status_code} - {response.text}")
                break
        return products

    def get_order(self, order_id: str) -> Optional[Dict[str, Any]]:
        """Retrieves a single order by its ID."""
        endpoint = f"/orders/{order_id}.json"
        url = self.base_url + endpoint
        response = requests.get(url, headers=self.headers)
        if response.status_code == 200:
            return response.json().get("order")
        else:
            print(f"Failed to fetch order {order_id}: {response.status_code} - {response.text}")
            return None