#!/usr/bin/env python3
"""
Integration Tests for AI-Powered Conversational Assistant
Tests the integration between all system components
"""

import requests
import json
import time
import sys
from typing import Dict, Any, List

class IntegrationTester:
    def __init__(self):
        self.base_urls = {
            'whatsapp_gateway': 'http://localhost:5000',
            'ai_conversation_engine': 'http://localhost:5001',
            'ecommerce_integration': 'http://localhost:5002'
        }
        self.test_results = []
        
    def log_test(self, test_name: str, success: bool, message: str = ""):
        """Log test results"""
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"{status} {test_name}: {message}")
        self.test_results.append({
            'test': test_name,
            'success': success,
            'message': message
        })
    
    def test_service_health(self, service_name: str, url: str) -> bool:
        """Test if a service is running and healthy"""
        try:
            response = requests.get(f"{url}/health", timeout=5)
            if response.status_code == 200:
                self.log_test(f"{service_name} Health Check", True, f"Service running on {url}")
                return True
            else:
                self.log_test(f"{service_name} Health Check", False, f"HTTP {response.status_code}")
                return False
        except requests.exceptions.RequestException as e:
            self.log_test(f"{service_name} Health Check", False, f"Connection failed: {str(e)}")
            return False
    
    def test_whatsapp_webhook(self) -> bool:
        """Test WhatsApp webhook endpoint"""
        try:
            # Test webhook verification
            params = {
                'hub.mode': 'subscribe',
                'hub.challenge': 'test_challenge',
                'hub.verify_token': 'test_token'
            }
            response = requests.get(f"{self.base_urls['whatsapp_gateway']}/webhook", params=params, timeout=5)
            
            if response.status_code == 200:
                self.log_test("WhatsApp Webhook Verification", True, "Webhook verification successful")
                return True
            else:
                self.log_test("WhatsApp Webhook Verification", False, f"HTTP {response.status_code}")
                return False
        except requests.exceptions.RequestException as e:
            self.log_test("WhatsApp Webhook Verification", False, f"Request failed: {str(e)}")
            return False
    
    def test_ai_conversation_flow(self) -> bool:
        """Test AI conversation processing"""
        try:
            test_message = {
                'message': 'Hello, I need help with my order',
                'customer_id': 'test_customer_123',
                'conversation_id': 'test_conv_456'
            }
            
            response = requests.post(
                f"{self.base_urls['ai_conversation_engine']}/process",
                json=test_message,
                timeout=10
            )
            
            if response.status_code == 200:
                result = response.json()
                if 'response' in result and 'intent' in result:
                    self.log_test("AI Conversation Processing", True, f"Intent: {result.get('intent', 'unknown')}")
                    return True
                else:
                    self.log_test("AI Conversation Processing", False, "Invalid response format")
                    return False
            else:
                self.log_test("AI Conversation Processing", False, f"HTTP {response.status_code}")
                return False
        except requests.exceptions.RequestException as e:
            self.log_test("AI Conversation Processing", False, f"Request failed: {str(e)}")
            return False
    
    def test_product_search(self) -> bool:
        """Test product search functionality"""
        try:
            response = requests.get(
                f"{self.base_urls['ecommerce_integration']}/products/search",
                params={'query': 'shirt'},
                timeout=5
            )
            
            if response.status_code == 200:
                result = response.json()
                if 'products' in result:
                    self.log_test("Product Search", True, f"Found {len(result['products'])} products")
                    return True
                else:
                    self.log_test("Product Search", False, "Invalid response format")
                    return False
            else:
                self.log_test("Product Search", False, f"HTTP {response.status_code}")
                return False
        except requests.exceptions.RequestException as e:
            self.log_test("Product Search", False, f"Request failed: {str(e)}")
            return False
    
    def test_order_lookup(self) -> bool:
        """Test order lookup functionality"""
        try:
            response = requests.get(
                f"{self.base_urls['ecommerce_integration']}/orders/ORD001",
                timeout=5
            )
            
            if response.status_code == 200:
                result = response.json()
                if 'order' in result:
                    self.log_test("Order Lookup", True, f"Order found: {result['order'].get('id', 'unknown')}")
                    return True
                else:
                    self.log_test("Order Lookup", False, "Invalid response format")
                    return False
            else:
                self.log_test("Order Lookup", False, f"HTTP {response.status_code}")
                return False
        except requests.exceptions.RequestException as e:
            self.log_test("Order Lookup", False, f"Request failed: {str(e)}")
            return False
    
    def test_knowledge_base_search(self) -> bool:
        """Test knowledge base search"""
        try:
            response = requests.get(
                f"{self.base_urls['ai_conversation_engine']}/knowledge/search",
                params={'query': 'return policy'},
                timeout=5
            )
            
            if response.status_code == 200:
                result = response.json()
                if 'documents' in result:
                    self.log_test("Knowledge Base Search", True, f"Found {len(result['documents'])} documents")
                    return True
                else:
                    self.log_test("Knowledge Base Search", False, "Invalid response format")
                    return False
            else:
                self.log_test("Knowledge Base Search", False, f"HTTP {response.status_code}")
                return False
        except requests.exceptions.RequestException as e:
            self.log_test("Knowledge Base Search", False, f"Request failed: {str(e)}")
            return False
    
    def test_end_to_end_flow(self) -> bool:
        """Test complete end-to-end conversation flow"""
        try:
            # Simulate a complete customer interaction
            print("\n🔄 Testing End-to-End Flow...")
            
            # Step 1: Customer sends message to WhatsApp
            webhook_payload = {
                'entry': [{
                    'changes': [{
                        'value': {
                            'messages': [{
                                'from': '1234567890',
                                'text': {'body': 'I want to check my order status'},
                                'timestamp': str(int(time.time()))
                            }]
                        }
                    }]
                }]
            }
            
            response = requests.post(
                f"{self.base_urls['whatsapp_gateway']}/webhook",
                json=webhook_payload,
                timeout=10
            )
            
            if response.status_code != 200:
                self.log_test("End-to-End Flow", False, f"WhatsApp webhook failed: HTTP {response.status_code}")
                return False
            
            # Step 2: Check if AI processed the message
            time.sleep(2)  # Allow processing time
            
            # Step 3: Verify conversation was created
            response = requests.get(
                f"{self.base_urls['whatsapp_gateway']}/conversations/1234567890",
                timeout=5
            )
            
            if response.status_code == 200:
                self.log_test("End-to-End Flow", True, "Complete flow successful")
                return True
            else:
                self.log_test("End-to-End Flow", False, f"Conversation not found: HTTP {response.status_code}")
                return False
                
        except requests.exceptions.RequestException as e:
            self.log_test("End-to-End Flow", False, f"Request failed: {str(e)}")
            return False
    
    def test_performance(self) -> bool:
        """Test system performance under load"""
        try:
            print("\n⚡ Testing Performance...")
            
            # Test response times
            start_time = time.time()
            
            # Make multiple concurrent requests
            import concurrent.futures
            import threading
            
            def make_request():
                try:
                    response = requests.get(f"{self.base_urls['whatsapp_gateway']}/health", timeout=5)
                    return response.status_code == 200
                except:
                    return False
            
            with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
                futures = [executor.submit(make_request) for _ in range(20)]
                results = [future.result() for future in concurrent.futures.as_completed(futures)]
            
            end_time = time.time()
            duration = end_time - start_time
            success_rate = sum(results) / len(results) * 100
            
            if success_rate >= 90 and duration < 10:
                self.log_test("Performance Test", True, f"Success rate: {success_rate:.1f}%, Duration: {duration:.2f}s")
                return True
            else:
                self.log_test("Performance Test", False, f"Success rate: {success_rate:.1f}%, Duration: {duration:.2f}s")
                return False
                
        except Exception as e:
            self.log_test("Performance Test", False, f"Test failed: {str(e)}")
            return False
    
    def run_all_tests(self) -> Dict[str, Any]:
        """Run all integration tests"""
        print("🚀 Starting Integration Tests for AI Conversational Assistant\n")
        
        # Test service health
        print("📋 Testing Service Health...")
        health_results = []
        for service, url in self.base_urls.items():
            health_results.append(self.test_service_health(service, url))
        
        # Only continue if all services are healthy
        if not all(health_results):
            print("\n❌ Some services are not running. Please start all services before running tests.")
            return self.generate_report()
        
        print("\n📡 Testing API Endpoints...")
        self.test_whatsapp_webhook()
        self.test_ai_conversation_flow()
        self.test_product_search()
        self.test_order_lookup()
        self.test_knowledge_base_search()
        
        print("\n🔄 Testing Integration...")
        self.test_end_to_end_flow()
        
        print("\n⚡ Testing Performance...")
        self.test_performance()
        
        return self.generate_report()
    
    def generate_report(self) -> Dict[str, Any]:
        """Generate test report"""
        total_tests = len(self.test_results)
        passed_tests = sum(1 for result in self.test_results if result['success'])
        failed_tests = total_tests - passed_tests
        
        report = {
            'total_tests': total_tests,
            'passed': passed_tests,
            'failed': failed_tests,
            'success_rate': (passed_tests / total_tests * 100) if total_tests > 0 else 0,
            'results': self.test_results
        }
        
        print(f"\n📊 Test Report:")
        print(f"Total Tests: {total_tests}")
        print(f"Passed: {passed_tests}")
        print(f"Failed: {failed_tests}")
        print(f"Success Rate: {report['success_rate']:.1f}%")
        
        if failed_tests > 0:
            print(f"\n❌ Failed Tests:")
            for result in self.test_results:
                if not result['success']:
                    print(f"  - {result['test']}: {result['message']}")
        
        return report

def main():
    """Main function to run integration tests"""
    tester = IntegrationTester()
    
    # Check if services should be started
    if len(sys.argv) > 1 and sys.argv[1] == '--start-services':
        print("🔧 Starting services is not implemented in this test script.")
        print("Please start services manually before running tests.")
        return
    
    # Run tests
    report = tester.run_all_tests()
    
    # Save report
    with open('/home/ubuntu/integration_test_report.json', 'w') as f:
        json.dump(report, f, indent=2)
    
    print(f"\n📄 Report saved to: /home/ubuntu/integration_test_report.json")
    
    # Exit with appropriate code
    if report['success_rate'] < 80:
        print("\n⚠️  Integration tests failed. Please check the services and try again.")
        sys.exit(1)
    else:
        print("\n✅ Integration tests passed successfully!")
        sys.exit(0)

if __name__ == "__main__":
    main()

