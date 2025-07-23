import os
import requests
import json
from datetime import datetime
from typing import Dict, Any, Optional

class NotificationService:
    def __init__(self):
        self.whatsapp_api_url = os.getenv('WHATSAPP_API_URL', 'http://localhost:5000/api')
        self.email_service_url = os.getenv('EMAIL_SERVICE_URL', 'http://localhost:5003/api')
        self.sms_service_url = os.getenv('SMS_SERVICE_URL', 'http://localhost:5004/api')
    
    def send_order_notification(self, order_id: str, notification_type: str, 
                              custom_message: str = '') -> Dict[str, Any]:
        """Send notification to customer about order status"""
        try:
            # Get order details (mock for now)
            order = self._get_order_details(order_id)
            if not order:
                return {
                    'success': False,
                    'message': 'Order not found'
                }
            
            # Generate notification content
            notification_content = self._generate_notification_content(
                order, notification_type, custom_message
            )
            
            # Send via multiple channels
            results = {}
            
            # Send WhatsApp notification
            if order.get('customer_phone'):
                whatsapp_result = self._send_whatsapp_notification(
                    order['customer_phone'], notification_content
                )
                results['whatsapp'] = whatsapp_result
            
            # Send email notification
            if order.get('customer_email'):
                email_result = self._send_email_notification(
                    order['customer_email'], notification_content
                )
                results['email'] = email_result
            
            # Log notification
            self._log_notification(order_id, notification_type, results)
            
            return {
                'success': True,
                'notification_type': notification_type,
                'order_id': order_id,
                'channels': results,
                'sent_at': datetime.now().isoformat()
            }
        
        except Exception as e:
            return {
                'success': False,
                'message': f'Notification failed: {str(e)}'
            }
    
    def send_refund_notification(self, order_id: str, refund_details: Dict[str, Any]) -> Dict[str, Any]:
        """Send refund notification to customer"""
        try:
            order = self._get_order_details(order_id)
            if not order:
                return {
                    'success': False,
                    'message': 'Order not found'
                }
            
            # Generate refund notification content
            content = self._generate_refund_content(order, refund_details)
            
            # Send notifications
            results = {}
            
            if order.get('customer_phone'):
                results['whatsapp'] = self._send_whatsapp_notification(
                    order['customer_phone'], content
                )
            
            if order.get('customer_email'):
                results['email'] = self._send_email_notification(
                    order['customer_email'], content
                )
            
            return {
                'success': True,
                'refund_id': refund_details.get('refund_id'),
                'channels': results,
                'sent_at': datetime.now().isoformat()
            }
        
        except Exception as e:
            return {
                'success': False,
                'message': f'Refund notification failed: {str(e)}'
            }
    
    def send_exchange_notification(self, order_id: str, exchange_details: Dict[str, Any]) -> Dict[str, Any]:
        """Send exchange notification to customer"""
        try:
            order = self._get_order_details(order_id)
            if not order:
                return {
                    'success': False,
                    'message': 'Order not found'
                }
            
            # Generate exchange notification content
            content = self._generate_exchange_content(order, exchange_details)
            
            # Send notifications
            results = {}
            
            if order.get('customer_phone'):
                results['whatsapp'] = self._send_whatsapp_notification(
                    order['customer_phone'], content
                )
            
            if order.get('customer_email'):
                results['email'] = self._send_email_notification(
                    order['customer_email'], content
                )
            
            return {
                'success': True,
                'exchange_id': exchange_details.get('exchange_id'),
                'channels': results,
                'sent_at': datetime.now().isoformat()
            }
        
        except Exception as e:
            return {
                'success': False,
                'message': f'Exchange notification failed: {str(e)}'
            }
    
    def send_shipping_update(self, order_id: str, tracking_number: str, 
                           carrier: str, estimated_delivery: str = None) -> Dict[str, Any]:
        """Send shipping update notification"""
        try:
            order = self._get_order_details(order_id)
            if not order:
                return {
                    'success': False,
                    'message': 'Order not found'
                }
            
            # Generate shipping update content
            content = self._generate_shipping_content(
                order, tracking_number, carrier, estimated_delivery
            )
            
            # Send notifications
            results = {}
            
            if order.get('customer_phone'):
                results['whatsapp'] = self._send_whatsapp_notification(
                    order['customer_phone'], content
                )
            
            if order.get('customer_email'):
                results['email'] = self._send_email_notification(
                    order['customer_email'], content
                )
            
            return {
                'success': True,
                'tracking_number': tracking_number,
                'channels': results,
                'sent_at': datetime.now().isoformat()
            }
        
        except Exception as e:
            return {
                'success': False,
                'message': f'Shipping notification failed: {str(e)}'
            }
    
    def send_promotional_message(self, customer_phone: str, promotion_details: Dict[str, Any]) -> Dict[str, Any]:
        """Send promotional message to customer"""
        try:
            content = self._generate_promotional_content(promotion_details)
            
            result = self._send_whatsapp_notification(customer_phone, content)
            
            return {
                'success': True,
                'customer_phone': customer_phone,
                'promotion_id': promotion_details.get('id'),
                'result': result,
                'sent_at': datetime.now().isoformat()
            }
        
        except Exception as e:
            return {
                'success': False,
                'message': f'Promotional message failed: {str(e)}'
            }
    
    def send_bulk_notifications(self, notifications: list) -> Dict[str, Any]:
        """Send multiple notifications in bulk"""
        try:
            results = []
            
            for notification in notifications:
                notification_type = notification.get('type')
                
                if notification_type == 'order_update':
                    result = self.send_order_notification(
                        notification['order_id'],
                        notification['update_type'],
                        notification.get('custom_message', '')
                    )
                elif notification_type == 'shipping_update':
                    result = self.send_shipping_update(
                        notification['order_id'],
                        notification['tracking_number'],
                        notification['carrier'],
                        notification.get('estimated_delivery')
                    )
                elif notification_type == 'promotional':
                    result = self.send_promotional_message(
                        notification['customer_phone'],
                        notification['promotion_details']
                    )
                else:
                    result = {
                        'success': False,
                        'message': f'Unknown notification type: {notification_type}'
                    }
                
                results.append({
                    'notification': notification,
                    'result': result
                })
            
            successful = sum(1 for r in results if r['result'].get('success'))
            
            return {
                'success': True,
                'total_notifications': len(notifications),
                'successful': successful,
                'failed': len(notifications) - successful,
                'results': results
            }
        
        except Exception as e:
            return {
                'success': False,
                'message': f'Bulk notifications failed: {str(e)}'
            }
    
    def _get_order_details(self, order_id: str) -> Optional[Dict[str, Any]]:
        """Get order details (mock implementation)"""
        # Mock order data - in production, this would fetch from Shopify
        return {
            'id': order_id,
            'order_number': f"#{order_id}",
            'customer_name': 'John Doe',
            'customer_email': 'john.doe@example.com',
            'customer_phone': '+1234567890',
            'total_price': '99.99',
            'status': 'processing',
            'items': [
                {'name': 'Product 1', 'quantity': 1, 'price': '49.99'},
                {'name': 'Product 2', 'quantity': 2, 'price': '25.00'}
            ],
            'shipping_address': {
                'address1': '123 Main St',
                'city': 'Anytown',
                'province': 'State',
                'zip': '12345',
                'country': 'US'
            }
        }
    
    def _generate_notification_content(self, order: Dict[str, Any], notification_type: str, 
                                     custom_message: str = '') -> Dict[str, Any]:
        """Generate notification content based on type"""
        order_number = order.get('order_number', order.get('id'))
        customer_name = order.get('customer_name', 'Valued Customer')
        
        templates = {
            'confirmation': {
                'subject': f'Order Confirmation - {order_number}',
                'message': f"Hi {customer_name}! Your order {order_number} has been confirmed. Total: ${order.get('total_price', '0.00')}. We'll notify you when it ships!"
            },
            'shipping': {
                'subject': f'Your Order Has Shipped - {order_number}',
                'message': f"Great news {customer_name}! Your order {order_number} has been shipped and is on its way to you. You'll receive tracking information shortly."
            },
            'delivery': {
                'subject': f'Order Delivered - {order_number}',
                'message': f"Hi {customer_name}! Your order {order_number} has been delivered. We hope you love your purchase! Please let us know if you have any questions."
            },
            'delay': {
                'subject': f'Order Update - {order_number}',
                'message': f"Hi {customer_name}, we wanted to update you that your order {order_number} is experiencing a slight delay. We apologize for any inconvenience and will keep you updated."
            }
        }
        
        template = templates.get(notification_type, {
            'subject': f'Order Update - {order_number}',
            'message': custom_message or f"Hi {customer_name}, we have an update about your order {order_number}."
        })
        
        if custom_message:
            template['message'] = custom_message
        
        return template
    
    def _generate_refund_content(self, order: Dict[str, Any], refund_details: Dict[str, Any]) -> Dict[str, Any]:
        """Generate refund notification content"""
        order_number = order.get('order_number', order.get('id'))
        customer_name = order.get('customer_name', 'Valued Customer')
        refund_amount = refund_details.get('amount', 0)
        
        return {
            'subject': f'Refund Processed - {order_number}',
            'message': f"Hi {customer_name}! Your refund of ${refund_amount} for order {order_number} has been processed. You should see the credit in your account within 3-5 business days."
        }
    
    def _generate_exchange_content(self, order: Dict[str, Any], exchange_details: Dict[str, Any]) -> Dict[str, Any]:
        """Generate exchange notification content"""
        order_number = order.get('order_number', order.get('id'))
        customer_name = order.get('customer_name', 'Valued Customer')
        exchange_id = exchange_details.get('exchange_id')
        
        return {
            'subject': f'Exchange Request Received - {order_number}',
            'message': f"Hi {customer_name}! We've received your exchange request (#{exchange_id}) for order {order_number}. Please send your return items to us, and we'll process your exchange once received."
        }
    
    def _generate_shipping_content(self, order: Dict[str, Any], tracking_number: str, 
                                 carrier: str, estimated_delivery: str = None) -> Dict[str, Any]:
        """Generate shipping notification content"""
        order_number = order.get('order_number', order.get('id'))
        customer_name = order.get('customer_name', 'Valued Customer')
        
        message = f"Hi {customer_name}! Your order {order_number} has shipped via {carrier}. Tracking number: {tracking_number}"
        
        if estimated_delivery:
            message += f". Estimated delivery: {estimated_delivery}"
        
        return {
            'subject': f'Your Order Has Shipped - {order_number}',
            'message': message
        }
    
    def _generate_promotional_content(self, promotion_details: Dict[str, Any]) -> Dict[str, Any]:
        """Generate promotional message content"""
        promo_title = promotion_details.get('title', 'Special Offer')
        promo_description = promotion_details.get('description', 'Check out our latest deals!')
        promo_code = promotion_details.get('code', '')
        
        message = f"🎉 {promo_title}! {promo_description}"
        
        if promo_code:
            message += f" Use code: {promo_code}"
        
        return {
            'subject': promo_title,
            'message': message
        }
    
    def _send_whatsapp_notification(self, phone: str, content: Dict[str, Any]) -> Dict[str, Any]:
        """Send WhatsApp notification"""
        try:
            # Mock WhatsApp API call
            payload = {
                'to': phone,
                'message': content['message']
            }
            
            # In production, this would call the actual WhatsApp API
            # response = requests.post(f"{self.whatsapp_api_url}/messages/send", json=payload)
            
            return {
                'success': True,
                'channel': 'whatsapp',
                'phone': phone,
                'message_id': f"wa_{datetime.now().strftime('%Y%m%d%H%M%S')}",
                'sent_at': datetime.now().isoformat()
            }
        
        except Exception as e:
            return {
                'success': False,
                'channel': 'whatsapp',
                'error': str(e)
            }
    
    def _send_email_notification(self, email: str, content: Dict[str, Any]) -> Dict[str, Any]:
        """Send email notification"""
        try:
            # Mock email API call
            payload = {
                'to': email,
                'subject': content['subject'],
                'body': content['message']
            }
            
            # In production, this would call an email service
            # response = requests.post(f"{self.email_service_url}/send", json=payload)
            
            return {
                'success': True,
                'channel': 'email',
                'email': email,
                'message_id': f"email_{datetime.now().strftime('%Y%m%d%H%M%S')}",
                'sent_at': datetime.now().isoformat()
            }
        
        except Exception as e:
            return {
                'success': False,
                'channel': 'email',
                'error': str(e)
            }
    
    def _send_sms_notification(self, phone: str, content: Dict[str, Any]) -> Dict[str, Any]:
        """Send SMS notification"""
        try:
            # Mock SMS API call
            payload = {
                'to': phone,
                'message': content['message']
            }
            
            # In production, this would call an SMS service
            # response = requests.post(f"{self.sms_service_url}/send", json=payload)
            
            return {
                'success': True,
                'channel': 'sms',
                'phone': phone,
                'message_id': f"sms_{datetime.now().strftime('%Y%m%d%H%M%S')}",
                'sent_at': datetime.now().isoformat()
            }
        
        except Exception as e:
            return {
                'success': False,
                'channel': 'sms',
                'error': str(e)
            }
    
    def _log_notification(self, order_id: str, notification_type: str, results: Dict[str, Any]):
        """Log notification for audit trail"""
        # In production, this would log to a database
        print(f"Notification sent: {notification_type} for order {order_id} - Results: {results}")

