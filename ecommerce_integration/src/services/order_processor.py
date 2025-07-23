import os
import requests
import json
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from src.services.shopify_service import ShopifyService
from src.services.notification_service import NotificationService

class OrderProcessor:
    def __init__(self):
        self.shopify_service = ShopifyService()
        self.notification_service = NotificationService()
        self.automation_rules = []
        self._load_automation_rules()
    
    def process_workflow_action(self, order_id: str, action: str, notes: str = '') -> Dict[str, Any]:
        """Process order through automated workflow"""
        try:
            # Get order details
            order = self.shopify_service.get_order(order_id)
            if not order:
                return {
                    'success': False,
                    'message': 'Order not found'
                }
            
            result = {}
            
            if action == 'confirm':
                result = self._confirm_order(order, notes)
            elif action == 'fulfill':
                result = self._fulfill_order(order, notes)
            elif action == 'ship':
                result = self._ship_order(order, notes)
            elif action == 'deliver':
                result = self._mark_delivered(order, notes)
            elif action == 'cancel':
                result = self._cancel_order(order, notes)
            else:
                return {
                    'success': False,
                    'message': f'Unknown action: {action}'
                }
            
            # Log workflow action
            self._log_workflow_action(order_id, action, result, notes)
            
            return result
        
        except Exception as e:
            return {
                'success': False,
                'message': f'Workflow processing failed: {str(e)}'
            }
    
    def update_order(self, order_id: str, updates: Dict[str, Any]) -> Dict[str, Any]:
        """Update order with specified changes"""
        try:
            # Mock order update - in production, this would call Shopify API
            updated_fields = []
            
            for field, value in updates.items():
                if field in ['notes', 'tags', 'shipping_address', 'billing_address']:
                    updated_fields.append(field)
            
            return {
                'success': True,
                'message': f'Updated fields: {", ".join(updated_fields)}',
                'updated_fields': updated_fields,
                'updated_at': datetime.now().isoformat()
            }
        
        except Exception as e:
            return {
                'success': False,
                'message': f'Order update failed: {str(e)}'
            }
    
    def get_analytics_summary(self, period: str = '30d') -> Dict[str, Any]:
        """Get order analytics summary"""
        try:
            # Mock analytics data - in production, this would query actual order data
            days = int(period.replace('d', ''))
            
            # Generate mock metrics
            total_orders = 150 + (days * 2)
            completed_orders = int(total_orders * 0.85)
            pending_orders = int(total_orders * 0.10)
            cancelled_orders = int(total_orders * 0.05)
            
            total_revenue = total_orders * 75.50  # Average order value
            
            summary = {
                'period': period,
                'total_orders': total_orders,
                'completed_orders': completed_orders,
                'pending_orders': pending_orders,
                'cancelled_orders': cancelled_orders,
                'total_revenue': round(total_revenue, 2),
                'average_order_value': round(total_revenue / total_orders, 2),
                'completion_rate': round((completed_orders / total_orders) * 100, 1),
                'cancellation_rate': round((cancelled_orders / total_orders) * 100, 1),
                'processing_metrics': {
                    'average_processing_time': '2.5 hours',
                    'average_fulfillment_time': '1.2 days',
                    'average_shipping_time': '3.5 days'
                },
                'top_issues': [
                    {'issue': 'Payment failed', 'count': 8},
                    {'issue': 'Inventory shortage', 'count': 5},
                    {'issue': 'Shipping delay', 'count': 3}
                ]
            }
            
            return summary
        
        except Exception as e:
            return {
                'error': f'Analytics summary failed: {str(e)}'
            }
    
    def get_pending_actions(self, action_type: str = None, limit: int = 50) -> List[Dict[str, Any]]:
        """Get orders that require manual action"""
        try:
            # Mock pending actions - in production, this would query actual order data
            pending_orders = []
            
            action_types = ['payment_failed', 'inventory_issue', 'shipping_delay', 'customer_inquiry']
            if action_type:
                action_types = [action_type]
            
            for i in range(min(limit, 20)):  # Mock up to 20 pending actions
                order_id = f"ORD{1000 + i}"
                action = action_types[i % len(action_types)]
                
                pending_orders.append({
                    'order_id': order_id,
                    'order_number': f"#{order_id}",
                    'action_type': action,
                    'priority': 'high' if action == 'payment_failed' else 'medium',
                    'customer_name': f"Customer {i + 1}",
                    'customer_email': f"customer{i + 1}@example.com",
                    'order_total': round(50 + (i * 10), 2),
                    'created_at': (datetime.now() - timedelta(hours=i)).isoformat(),
                    'description': self._get_action_description(action),
                    'suggested_actions': self._get_suggested_actions(action)
                })
            
            return pending_orders
        
        except Exception as e:
            print(f"Error getting pending actions: {str(e)}")
            return []
    
    def process_refund(self, order_id: str, amount: float = None, reason: str = 'Customer request',
                      notify_customer: bool = True) -> Dict[str, Any]:
        """Process refund for an order"""
        try:
            # Get order details
            order = self.shopify_service.get_order(order_id)
            if not order:
                return {
                    'success': False,
                    'message': 'Order not found'
                }
            
            order_total = float(order.get('total_price', 0))
            refund_amount = amount if amount is not None else order_total
            
            # Validate refund amount
            if refund_amount > order_total:
                return {
                    'success': False,
                    'message': 'Refund amount cannot exceed order total'
                }
            
            # Mock refund processing
            refund_id = f"REF{datetime.now().strftime('%Y%m%d%H%M%S')}"
            
            refund_result = {
                'success': True,
                'refund_id': refund_id,
                'order_id': order_id,
                'amount': refund_amount,
                'reason': reason,
                'processed_at': datetime.now().isoformat(),
                'is_partial': refund_amount < order_total
            }
            
            # Send notification if requested
            if notify_customer:
                self.notification_service.send_refund_notification(order_id, refund_result)
            
            return refund_result
        
        except Exception as e:
            return {
                'success': False,
                'message': f'Refund processing failed: {str(e)}'
            }
    
    def process_exchange(self, order_id: str, return_items: List[Dict[str, Any]], 
                        exchange_items: List[Dict[str, Any]], reason: str = 'Customer request') -> Dict[str, Any]:
        """Process exchange for an order"""
        try:
            # Mock exchange processing
            exchange_id = f"EXC{datetime.now().strftime('%Y%m%d%H%M%S')}"
            
            # Calculate exchange value difference
            return_value = sum(item.get('price', 0) * item.get('quantity', 1) for item in return_items)
            exchange_value = sum(item.get('price', 0) * item.get('quantity', 1) for item in exchange_items)
            value_difference = exchange_value - return_value
            
            exchange_result = {
                'success': True,
                'exchange_id': exchange_id,
                'order_id': order_id,
                'return_items': return_items,
                'exchange_items': exchange_items,
                'return_value': return_value,
                'exchange_value': exchange_value,
                'value_difference': value_difference,
                'reason': reason,
                'processed_at': datetime.now().isoformat(),
                'status': 'pending_return_receipt'
            }
            
            # Send notification
            self.notification_service.send_exchange_notification(order_id, exchange_result)
            
            return exchange_result
        
        except Exception as e:
            return {
                'success': False,
                'message': f'Exchange processing failed: {str(e)}'
            }
    
    def optimize_shipping(self, order_ids: List[str], optimization_type: str = 'cost') -> Dict[str, Any]:
        """Optimize shipping for pending orders"""
        try:
            optimization_results = []
            
            for order_id in order_ids:
                # Mock shipping optimization
                if optimization_type == 'cost':
                    optimized_carrier = 'Standard Shipping'
                    savings = 5.99
                elif optimization_type == 'speed':
                    optimized_carrier = 'Express Shipping'
                    savings = 0  # Faster but more expensive
                else:  # eco_friendly
                    optimized_carrier = 'Eco Shipping'
                    savings = 2.50
                
                optimization_results.append({
                    'order_id': order_id,
                    'original_carrier': 'Default Shipping',
                    'optimized_carrier': optimized_carrier,
                    'savings': savings,
                    'optimization_type': optimization_type
                })
            
            total_savings = sum(result['savings'] for result in optimization_results)
            
            return {
                'success': True,
                'optimization_type': optimization_type,
                'orders_optimized': len(optimization_results),
                'total_savings': round(total_savings, 2),
                'results': optimization_results
            }
        
        except Exception as e:
            return {
                'success': False,
                'message': f'Shipping optimization failed: {str(e)}'
            }
    
    def get_customer_order_history(self, customer_id: str, include_analytics: bool = False, 
                                 limit: int = 20) -> Dict[str, Any]:
        """Get comprehensive order history for a customer"""
        try:
            # Mock customer order history
            orders = []
            total_spent = 0
            
            for i in range(min(limit, 10)):  # Mock up to 10 orders
                order_value = 50 + (i * 15)
                total_spent += order_value
                
                orders.append({
                    'order_id': f"ORD{2000 + i}",
                    'order_number': f"#{2000 + i}",
                    'order_date': (datetime.now() - timedelta(days=i * 30)).isoformat(),
                    'status': 'completed' if i > 0 else 'processing',
                    'total': order_value,
                    'items_count': 2 + (i % 3),
                    'shipping_method': 'Standard Shipping'
                })
            
            history = {
                'customer_id': customer_id,
                'orders': orders,
                'order_count': len(orders),
                'total_spent': total_spent,
                'average_order_value': round(total_spent / len(orders), 2) if orders else 0
            }
            
            if include_analytics:
                history['analytics'] = {
                    'first_order_date': orders[-1]['order_date'] if orders else None,
                    'last_order_date': orders[0]['order_date'] if orders else None,
                    'favorite_categories': ['Electronics', 'Clothing'],
                    'preferred_shipping': 'Standard Shipping',
                    'return_rate': 5.2,  # Percentage
                    'customer_lifetime_value': total_spent * 1.2  # Projected CLV
                }
            
            return history
        
        except Exception as e:
            return {
                'error': f'Customer history retrieval failed: {str(e)}'
            }
    
    def check_fraud_indicators(self, order_id: str) -> Dict[str, Any]:
        """Check order for potential fraud indicators"""
        try:
            # Mock fraud check - in production, this would use fraud detection services
            fraud_score = 0.0
            indicators = []
            
            # Mock fraud indicators
            risk_factors = [
                {'factor': 'High-value order', 'weight': 0.2, 'detected': False},
                {'factor': 'New customer', 'weight': 0.1, 'detected': True},
                {'factor': 'Shipping/billing mismatch', 'weight': 0.3, 'detected': False},
                {'factor': 'Multiple payment attempts', 'weight': 0.4, 'detected': False},
                {'factor': 'Suspicious IP location', 'weight': 0.3, 'detected': False}
            ]
            
            for factor in risk_factors:
                if factor['detected']:
                    fraud_score += factor['weight']
                    indicators.append(factor['factor'])
            
            risk_level = 'low'
            if fraud_score > 0.7:
                risk_level = 'high'
            elif fraud_score > 0.3:
                risk_level = 'medium'
            
            return {
                'order_id': order_id,
                'fraud_score': round(fraud_score, 2),
                'risk_level': risk_level,
                'indicators': indicators,
                'recommendation': self._get_fraud_recommendation(risk_level),
                'checked_at': datetime.now().isoformat()
            }
        
        except Exception as e:
            return {
                'error': f'Fraud check failed: {str(e)}'
            }
    
    def get_automation_rules(self) -> List[Dict[str, Any]]:
        """Get order processing automation rules"""
        return self.automation_rules
    
    def create_automation_rule(self, rule_name: str, conditions: List[Dict[str, Any]], 
                             actions: List[Dict[str, Any]], is_active: bool = True) -> Dict[str, Any]:
        """Create new order processing automation rule"""
        try:
            rule = {
                'id': f"rule_{len(self.automation_rules) + 1}",
                'name': rule_name,
                'conditions': conditions,
                'actions': actions,
                'is_active': is_active,
                'created_at': datetime.now().isoformat(),
                'triggered_count': 0
            }
            
            self.automation_rules.append(rule)
            
            return rule
        
        except Exception as e:
            return {
                'error': f'Rule creation failed: {str(e)}'
            }
    
    def get_performance_report(self, start_date: str = None, end_date: str = None, 
                             metrics: List[str] = None) -> Dict[str, Any]:
        """Get order processing performance report"""
        try:
            # Mock performance report
            if not metrics:
                metrics = ['processing_time', 'fulfillment_rate', 'customer_satisfaction']
            
            report = {
                'period': {
                    'start_date': start_date or (datetime.now() - timedelta(days=30)).isoformat(),
                    'end_date': end_date or datetime.now().isoformat()
                },
                'metrics': {}
            }
            
            if 'processing_time' in metrics:
                report['metrics']['processing_time'] = {
                    'average_hours': 2.3,
                    'median_hours': 1.8,
                    'target_hours': 2.0,
                    'performance': 'above_target'
                }
            
            if 'fulfillment_rate' in metrics:
                report['metrics']['fulfillment_rate'] = {
                    'percentage': 94.2,
                    'target_percentage': 95.0,
                    'performance': 'below_target'
                }
            
            if 'customer_satisfaction' in metrics:
                report['metrics']['customer_satisfaction'] = {
                    'score': 4.6,
                    'target_score': 4.5,
                    'performance': 'above_target',
                    'response_rate': 78.3
                }
            
            return report
        
        except Exception as e:
            return {
                'error': f'Performance report failed: {str(e)}'
            }
    
    def _confirm_order(self, order: Dict[str, Any], notes: str) -> Dict[str, Any]:
        """Confirm an order"""
        return {
            'success': True,
            'message': 'Order confirmed successfully',
            'action': 'confirm',
            'notes': notes,
            'timestamp': datetime.now().isoformat()
        }
    
    def _fulfill_order(self, order: Dict[str, Any], notes: str) -> Dict[str, Any]:
        """Fulfill an order"""
        return {
            'success': True,
            'message': 'Order fulfilled successfully',
            'action': 'fulfill',
            'notes': notes,
            'timestamp': datetime.now().isoformat()
        }
    
    def _ship_order(self, order: Dict[str, Any], notes: str) -> Dict[str, Any]:
        """Ship an order"""
        tracking_number = f"TRK{datetime.now().strftime('%Y%m%d%H%M%S')}"
        return {
            'success': True,
            'message': 'Order shipped successfully',
            'action': 'ship',
            'tracking_number': tracking_number,
            'notes': notes,
            'timestamp': datetime.now().isoformat()
        }
    
    def _mark_delivered(self, order: Dict[str, Any], notes: str) -> Dict[str, Any]:
        """Mark order as delivered"""
        return {
            'success': True,
            'message': 'Order marked as delivered',
            'action': 'deliver',
            'notes': notes,
            'timestamp': datetime.now().isoformat()
        }
    
    def _cancel_order(self, order: Dict[str, Any], notes: str) -> Dict[str, Any]:
        """Cancel an order"""
        return {
            'success': True,
            'message': 'Order cancelled successfully',
            'action': 'cancel',
            'notes': notes,
            'timestamp': datetime.now().isoformat()
        }
    
    def _log_workflow_action(self, order_id: str, action: str, result: Dict[str, Any], notes: str):
        """Log workflow action for audit trail"""
        # In production, this would log to a database or file
        print(f"Workflow Action: {action} on order {order_id} - {result.get('message', '')}")
    
    def _get_action_description(self, action_type: str) -> str:
        """Get description for action type"""
        descriptions = {
            'payment_failed': 'Payment processing failed, requires manual review',
            'inventory_issue': 'Insufficient inventory for order fulfillment',
            'shipping_delay': 'Shipping carrier reported delivery delay',
            'customer_inquiry': 'Customer has submitted an inquiry about this order'
        }
        return descriptions.get(action_type, 'Manual action required')
    
    def _get_suggested_actions(self, action_type: str) -> List[str]:
        """Get suggested actions for action type"""
        suggestions = {
            'payment_failed': ['Retry payment', 'Contact customer', 'Cancel order'],
            'inventory_issue': ['Backorder item', 'Suggest alternative', 'Partial fulfillment'],
            'shipping_delay': ['Notify customer', 'Upgrade shipping', 'Offer compensation'],
            'customer_inquiry': ['Respond to inquiry', 'Escalate to manager', 'Schedule callback']
        }
        return suggestions.get(action_type, ['Review manually'])
    
    def _get_fraud_recommendation(self, risk_level: str) -> str:
        """Get recommendation based on fraud risk level"""
        recommendations = {
            'low': 'Process order normally',
            'medium': 'Manual review recommended',
            'high': 'Hold order for verification'
        }
        return recommendations.get(risk_level, 'Manual review required')
    
    def _load_automation_rules(self):
        """Load default automation rules"""
        self.automation_rules = [
            {
                'id': 'rule_1',
                'name': 'Auto-confirm low-risk orders',
                'conditions': [
                    {'field': 'fraud_score', 'operator': 'less_than', 'value': 0.3},
                    {'field': 'payment_status', 'operator': 'equals', 'value': 'paid'}
                ],
                'actions': [
                    {'type': 'confirm_order'},
                    {'type': 'send_confirmation_email'}
                ],
                'is_active': True,
                'created_at': datetime.now().isoformat(),
                'triggered_count': 0
            },
            {
                'id': 'rule_2',
                'name': 'Hold high-value orders',
                'conditions': [
                    {'field': 'order_total', 'operator': 'greater_than', 'value': 500}
                ],
                'actions': [
                    {'type': 'hold_for_review'},
                    {'type': 'notify_manager'}
                ],
                'is_active': True,
                'created_at': datetime.now().isoformat(),
                'triggered_count': 0
            }
        ]

