#!/usr/bin/env python3
"""
Deployment Script for AI-Powered Conversational Assistant
Handles deployment of all system components
"""

import os
import sys
import json
import subprocess
import time
import signal
from typing import Dict, List, Optional
from pathlib import Path

class DeploymentManager:
    def __init__(self):
        self.base_dir = Path('/home/ubuntu')
        self.services = {
            'whatsapp_gateway': {
                'path': self.base_dir / 'whatsapp_gateway',
                'port': 5000,
                'process': None,
                'health_endpoint': '/health'
            },
            'ai_conversation_engine': {
                'path': self.base_dir / 'ai_conversation_engine',
                'port': 5001,
                'process': None,
                'health_endpoint': '/health'
            },
            'ecommerce_integration': {
                'path': self.base_dir / 'ecommerce_integration',
                'port': 5002,
                'process': None,
                'health_endpoint': '/health'
            },
            'admin_dashboard': {
                'path': self.base_dir / 'admin-dashboard',
                'port': 5173,
                'process': None,
                'health_endpoint': '/',
                'type': 'frontend'
            }
        }
        self.running_processes = []
    
    def log(self, message: str, level: str = "INFO"):
        """Log deployment messages"""
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
        print(f"[{timestamp}] {level}: {message}")
    
    def check_dependencies(self) -> bool:
        """Check if all required dependencies are installed"""
        self.log("Checking dependencies...")
        
        # Check Python
        try:
            result = subprocess.run(['python3', '--version'], capture_output=True, text=True)
            if result.returncode == 0:
                self.log(f"Python: {result.stdout.strip()}")
            else:
                self.log("Python 3 not found", "ERROR")
                return False
        except FileNotFoundError:
            self.log("Python 3 not found", "ERROR")
            return False
        
        # Check Node.js
        try:
            result = subprocess.run(['node', '--version'], capture_output=True, text=True)
            if result.returncode == 0:
                self.log(f"Node.js: {result.stdout.strip()}")
            else:
                self.log("Node.js not found", "ERROR")
                return False
        except FileNotFoundError:
            self.log("Node.js not found", "ERROR")
            return False
        
        # Check npm
        try:
            result = subprocess.run(['npm', '--version'], capture_output=True, text=True)
            if result.returncode == 0:
                self.log(f"npm: {result.stdout.strip()}")
            else:
                self.log("npm not found", "ERROR")
                return False
        except FileNotFoundError:
            self.log("npm not found", "ERROR")
            return False
        
        return True
    
    def setup_environment(self, service_name: str) -> bool:
        """Set up environment for a service"""
        service = self.services[service_name]
        service_path = service['path']
        
        if not service_path.exists():
            self.log(f"Service directory not found: {service_path}", "ERROR")
            return False
        
        self.log(f"Setting up environment for {service_name}...")
        
        # For Python services
        if service.get('type') != 'frontend':
            # Check if virtual environment exists
            venv_path = service_path / 'venv'
            if not venv_path.exists():
                self.log(f"Creating virtual environment for {service_name}...")
                result = subprocess.run(
                    ['python3', '-m', 'venv', 'venv'],
                    cwd=service_path,
                    capture_output=True,
                    text=True
                )
                if result.returncode != 0:
                    self.log(f"Failed to create virtual environment: {result.stderr}", "ERROR")
                    return False
            
            # Install Python dependencies
            requirements_file = service_path / 'requirements.txt'
            if requirements_file.exists():
                self.log(f"Installing Python dependencies for {service_name}...")
                result = subprocess.run(
                    [str(venv_path / 'bin' / 'pip'), 'install', '-r', 'requirements.txt'],
                    cwd=service_path,
                    capture_output=True,
                    text=True
                )
                if result.returncode != 0:
                    self.log(f"Failed to install dependencies: {result.stderr}", "ERROR")
                    return False
        
        # For Node.js services
        else:
            package_json = service_path / 'package.json'
            if package_json.exists():
                self.log(f"Installing Node.js dependencies for {service_name}...")
                result = subprocess.run(
                    ['npm', 'install'],
                    cwd=service_path,
                    capture_output=True,
                    text=True
                )
                if result.returncode != 0:
                    self.log(f"Failed to install dependencies: {result.stderr}", "ERROR")
                    return False
        
        return True
    
    def create_env_files(self) -> bool:
        """Create environment files for all services"""
        self.log("Creating environment files...")
        
        # WhatsApp Gateway .env
        whatsapp_env = self.services['whatsapp_gateway']['path'] / '.env'
        with open(whatsapp_env, 'w') as f:
            f.write("""# WhatsApp Business API Configuration
WHATSAPP_API_KEY=your_whatsapp_api_key_here
WHATSAPP_PHONE_NUMBER_ID=your_phone_number_id_here
WHATSAPP_BUSINESS_ACCOUNT_ID=your_business_account_id_here
WHATSAPP_WEBHOOK_VERIFY_TOKEN=your_webhook_verify_token_here

# AI Service Configuration
AI_SERVICE_URL=http://localhost:5001

# E-commerce Service Configuration
ECOMMERCE_SERVICE_URL=http://localhost:5002

# Database Configuration
DATABASE_URL=sqlite:///whatsapp_gateway.db

# Flask Configuration
FLASK_ENV=production
FLASK_DEBUG=False
""")
        
        # AI Conversation Engine .env
        ai_env = self.services['ai_conversation_engine']['path'] / '.env'
        with open(ai_env, 'w') as f:
            f.write("""# AI Configuration
GEMINI_API_KEY=your_gemini_api_key_here
OPENAI_API_KEY=your_openai_api_key_here
AI_MODEL=gemini-pro
AI_TEMPERATURE=0.7
MAX_TOKENS=2048

# Mock Mode (set to true for testing without API keys)
MOCK_MODE=true

# Database Configuration
DATABASE_URL=sqlite:///ai_conversation.db

# Flask Configuration
FLASK_ENV=production
FLASK_DEBUG=False
""")
        
        # E-commerce Integration .env
        ecommerce_env = self.services['ecommerce_integration']['path'] / '.env'
        with open(ecommerce_env, 'w') as f:
            f.write("""# Shopify Configuration
SHOPIFY_API_KEY=your_shopify_api_key_here
SHOPIFY_API_SECRET=your_shopify_api_secret_here
SHOPIFY_STORE_URL=your-store.myshopify.com
SHOPIFY_ACCESS_TOKEN=your_shopify_access_token_here

# Shipping Configuration
EASYPOST_API_KEY=your_easypost_api_key_here
FEDEX_API_KEY=your_fedex_api_key_here
UPS_API_KEY=your_ups_api_key_here

# Mock Mode (set to true for testing without API keys)
MOCK_MODE=true

# Database Configuration
DATABASE_URL=sqlite:///ecommerce_integration.db

# Flask Configuration
FLASK_ENV=production
FLASK_DEBUG=False
""")
        
        # Admin Dashboard .env
        dashboard_env = self.services['admin_dashboard']['path'] / '.env'
        with open(dashboard_env, 'w') as f:
            f.write("""# API Endpoints
VITE_API_BASE_URL=http://localhost:5000
VITE_WHATSAPP_API_URL=http://localhost:5000
VITE_ECOMMERCE_API_URL=http://localhost:5002
VITE_AI_API_URL=http://localhost:5001

# Feature Flags
VITE_ENABLE_ANALYTICS=true
VITE_ENABLE_REAL_TIME=true
VITE_ENABLE_NOTIFICATIONS=true
""")
        
        self.log("Environment files created successfully")
        return True
    
    def start_service(self, service_name: str) -> bool:
        """Start a specific service"""
        service = self.services[service_name]
        service_path = service['path']
        port = service['port']
        
        self.log(f"Starting {service_name} on port {port}...")
        
        try:
            if service.get('type') == 'frontend':
                # Start Node.js service
                process = subprocess.Popen(
                    ['npm', 'run', 'dev', '--', '--host', '--port', str(port)],
                    cwd=service_path,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True
                )
            else:
                # Start Python Flask service
                venv_python = service_path / 'venv' / 'bin' / 'python'
                process = subprocess.Popen(
                    [str(venv_python), '-m', 'src.main'],
                    cwd=service_path,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    env={**os.environ, 'FLASK_RUN_HOST': '0.0.0.0', 'FLASK_RUN_PORT': str(port)}
                )
            
            service['process'] = process
            self.running_processes.append(process)
            
            # Wait a moment for the service to start
            time.sleep(3)
            
            # Check if process is still running
            if process.poll() is None:
                self.log(f"{service_name} started successfully (PID: {process.pid})")
                return True
            else:
                stdout, stderr = process.communicate()
                self.log(f"Failed to start {service_name}: {stderr}", "ERROR")
                return False
                
        except Exception as e:
            self.log(f"Error starting {service_name}: {str(e)}", "ERROR")
            return False
    
    def stop_service(self, service_name: str) -> bool:
        """Stop a specific service"""
        service = self.services[service_name]
        process = service.get('process')
        
        if process and process.poll() is None:
            self.log(f"Stopping {service_name}...")
            process.terminate()
            try:
                process.wait(timeout=10)
                self.log(f"{service_name} stopped successfully")
                return True
            except subprocess.TimeoutExpired:
                self.log(f"Force killing {service_name}...")
                process.kill()
                process.wait()
                return True
        else:
            self.log(f"{service_name} is not running")
            return True
    
    def check_service_health(self, service_name: str) -> bool:
        """Check if a service is healthy"""
        service = self.services[service_name]
        port = service['port']
        endpoint = service['health_endpoint']
        
        try:
            import requests
            response = requests.get(f"http://localhost:{port}{endpoint}", timeout=5)
            return response.status_code == 200
        except:
            return False
    
    def wait_for_services(self, timeout: int = 60) -> bool:
        """Wait for all services to be healthy"""
        self.log("Waiting for services to be ready...")
        
        start_time = time.time()
        while time.time() - start_time < timeout:
            all_healthy = True
            for service_name in self.services:
                if not self.check_service_health(service_name):
                    all_healthy = False
                    break
            
            if all_healthy:
                self.log("All services are healthy")
                return True
            
            time.sleep(2)
        
        self.log("Timeout waiting for services to be ready", "ERROR")
        return False
    
    def deploy_all(self) -> bool:
        """Deploy all services"""
        self.log("Starting deployment of AI Conversational Assistant...")
        
        # Check dependencies
        if not self.check_dependencies():
            return False
        
        # Set up environments
        for service_name in self.services:
            if not self.setup_environment(service_name):
                return False
        
        # Create environment files
        if not self.create_env_files():
            return False
        
        # Start services
        for service_name in self.services:
            if not self.start_service(service_name):
                return False
        
        # Wait for services to be ready
        if not self.wait_for_services():
            return False
        
        self.log("Deployment completed successfully!")
        self.log("Services are running on the following ports:")
        for service_name, service in self.services.items():
            self.log(f"  {service_name}: http://localhost:{service['port']}")
        
        return True
    
    def stop_all(self) -> bool:
        """Stop all services"""
        self.log("Stopping all services...")
        
        for service_name in self.services:
            self.stop_service(service_name)
        
        self.log("All services stopped")
        return True
    
    def status(self) -> Dict:
        """Get status of all services"""
        status = {}
        for service_name in self.services:
            status[service_name] = {
                'running': self.check_service_health(service_name),
                'port': self.services[service_name]['port']
            }
        return status
    
    def cleanup(self):
        """Cleanup on exit"""
        self.log("Cleaning up...")
        for process in self.running_processes:
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()

def signal_handler(signum, frame):
    """Handle shutdown signals"""
    print("\nReceived shutdown signal. Cleaning up...")
    if hasattr(signal_handler, 'deployment_manager'):
        signal_handler.deployment_manager.cleanup()
    sys.exit(0)

def main():
    """Main deployment function"""
    deployment_manager = DeploymentManager()
    signal_handler.deployment_manager = deployment_manager
    
    # Set up signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    if len(sys.argv) < 2:
        print("Usage: python deploy.py [start|stop|status|test]")
        sys.exit(1)
    
    command = sys.argv[1]
    
    try:
        if command == 'start':
            success = deployment_manager.deploy_all()
            if success:
                print("\n✅ Deployment successful!")
                print("Press Ctrl+C to stop all services")
                # Keep the script running
                try:
                    while True:
                        time.sleep(1)
                except KeyboardInterrupt:
                    pass
            else:
                print("\n❌ Deployment failed!")
                sys.exit(1)
        
        elif command == 'stop':
            deployment_manager.stop_all()
            print("✅ All services stopped")
        
        elif command == 'status':
            status = deployment_manager.status()
            print("Service Status:")
            for service_name, info in status.items():
                status_text = "🟢 Running" if info['running'] else "🔴 Stopped"
                print(f"  {service_name}: {status_text} (port {info['port']})")
        
        elif command == 'test':
            # Run integration tests
            print("Running integration tests...")
            result = subprocess.run(['python3', '/home/ubuntu/integration_tests.py'])
            sys.exit(result.returncode)
        
        else:
            print(f"Unknown command: {command}")
            print("Usage: python deploy.py [start|stop|status|test]")
            sys.exit(1)
    
    except Exception as e:
        print(f"Error: {str(e)}")
        deployment_manager.cleanup()
        sys.exit(1)

if __name__ == "__main__":
    main()

