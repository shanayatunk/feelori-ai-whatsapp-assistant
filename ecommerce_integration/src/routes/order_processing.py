from flask import Blueprint, request, jsonify
from src.services.shopify_service import ShopifyService
from src.services.order_processor import OrderProcessor
from src.services.notification_service import NotificationService

order_processing_bp = Blueprint('order_processing', __name__)
shopify_service = ShopifyService()
order_processor = OrderProcessor()
notification_service = NotificationService()

@order_processing_bp.route('/order-processing/workflow/<order_id>', methods=['POST'])
def process_order_workflow(order_id):
    """Process order through automated workflow"""
    try:
        data = request.get_json()
        action = data.get('action')  # confirm, fulfill, ship, deliver, cancel
        notes = data.get('notes', '')
        
        result = order_processor.process_workflow_action(order_id, action, notes)
        
        return jsonify({
            'success': True,
            'result': result
        }), 200
    
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@order_processing_bp.route('/order-processing/notifications/<order_id>', methods=['POST'])
def send_order_notification(order_id):
    """Send notification to customer about order status"""
    try:
        data = request.get_json()
        notification_type = data.get('type')  # confirmation, shipping, delivery, delay
        custom_message = data.get('custom_message', '')
        
        result = notification_service.send_order_notification(
            order_id, notification_type, custom_message
        )
        
        return jsonify({
            'success': True,
            'result': result
        }), 200
    
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@order_processing_bp.route('/order-processing/bulk-update', methods=['POST'])
def bulk_update_orders():
    """Bulk update multiple orders"""
    try:
        data = request.get_json()
        order_ids = data.get('order_ids', [])
        updates = data.get('updates', {})
        
        results = []
        for order_id in order_ids:
            result = order_processor.update_order(order_id, updates)
            results.append({
                'order_id': order_id,
                'success': result.get('success', False),
                'message': result.get('message', '')
            })
        
        return jsonify({
            'success': True,
            'results': results,
            'count': len(results)
        }), 200
    
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@order_processing_bp.route('/order-processing/analytics/summary', methods=['GET'])
def get_order_analytics_summary():
    """Get order analytics summary"""
    try:
        period = request.args.get('period', '30d')
        
        summary = order_processor.get_analytics_summary(period)
        
        return jsonify({
            'success': True,
            'summary': summary,
            'period': period
        }), 200
    
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@order_processing_bp.route('/order-processing/pending-actions', methods=['GET'])
def get_pending_actions():
    """Get orders that require manual action"""
    try:
        action_type = request.args.get('type')  # payment_failed, inventory_issue, shipping_delay
        limit = int(request.args.get('limit', 50))
        
        pending_orders = order_processor.get_pending_actions(action_type, limit)
        
        return jsonify({
            'success': True,
            'orders': pending_orders,
            'count': len(pending_orders)
        }), 200
    
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@order_processing_bp.route('/order-processing/refund/<order_id>', methods=['POST'])
def process_refund(order_id):
    """Process refund for an order"""
    try:
        data = request.get_json()
        amount = data.get('amount')  # Partial refund amount, None for full refund
        reason = data.get('reason', 'Customer request')
        notify_customer = data.get('notify_customer', True)
        
        result = order_processor.process_refund(order_id, amount, reason, notify_customer)
        
        return jsonify({
            'success': True,
            'result': result
        }), 200
    
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@order_processing_bp.route('/order-processing/exchange/<order_id>', methods=['POST'])
def process_exchange(order_id):
    """Process exchange for an order"""
    try:
        data = request.get_json()
        return_items = data.get('return_items', [])
        exchange_items = data.get('exchange_items', [])
        reason = data.get('reason', 'Customer request')
        
        result = order_processor.process_exchange(order_id, return_items, exchange_items, reason)
        
        return jsonify({
            'success': True,
            'result': result
        }), 200
    
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@order_processing_bp.route('/order-processing/shipping/optimize', methods=['POST'])
def optimize_shipping():
    """Optimize shipping for pending orders"""
    try:
        data = request.get_json()
        order_ids = data.get('order_ids', [])
        optimization_type = data.get('type', 'cost')  # cost, speed, eco_friendly
        
        result = order_processor.optimize_shipping(order_ids, optimization_type)
        
        return jsonify({
            'success': True,
            'result': result
        }), 200
    
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@order_processing_bp.route('/order-processing/customer/<customer_id>/history', methods=['GET'])
def get_customer_order_history(customer_id):
    """Get comprehensive order history for a customer"""
    try:
        include_analytics = request.args.get('analytics', 'false').lower() == 'true'
        limit = int(request.args.get('limit', 20))
        
        history = order_processor.get_customer_order_history(customer_id, include_analytics, limit)
        
        return jsonify({
            'success': True,
            'history': history
        }), 200
    
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@order_processing_bp.route('/order-processing/fraud-check/<order_id>', methods=['POST'])
def check_order_fraud(order_id):
    """Check order for potential fraud indicators"""
    try:
        result = order_processor.check_fraud_indicators(order_id)
        
        return jsonify({
            'success': True,
            'fraud_check': result
        }), 200
    
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@order_processing_bp.route('/order-processing/automation/rules', methods=['GET'])
def get_automation_rules():
    """Get order processing automation rules"""
    try:
        rules = order_processor.get_automation_rules()
        
        return jsonify({
            'success': True,
            'rules': rules,
            'count': len(rules)
        }), 200
    
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@order_processing_bp.route('/order-processing/automation/rules', methods=['POST'])
def create_automation_rule():
    """Create new order processing automation rule"""
    try:
        data = request.get_json()
        rule_name = data.get('name')
        conditions = data.get('conditions', [])
        actions = data.get('actions', [])
        is_active = data.get('is_active', True)
        
        result = order_processor.create_automation_rule(rule_name, conditions, actions, is_active)
        
        return jsonify({
            'success': True,
            'rule': result
        }), 201
    
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@order_processing_bp.route('/order-processing/reports/performance', methods=['GET'])
def get_performance_report():
    """Get order processing performance report"""
    try:
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')
        metrics = request.args.getlist('metrics')  # processing_time, fulfillment_rate, customer_satisfaction
        
        report = order_processor.get_performance_report(start_date, end_date, metrics)
        
        return jsonify({
            'success': True,
            'report': report
        }), 200
    
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

