# src/models/order.py

from .base import BaseModel, OrderStatus, PHONE_REGEX
from . import db
from sqlalchemy import Index
from sqlalchemy.orm import validates
from typing import Dict, Any
import logging

logger = logging.getLogger(__name__)

class Order(BaseModel):
    __tablename__ = 'orders'

    # Overriding the primary key to be an Integer as it might come from an external system
    id = db.Column(db.Integer, primary_key=True)
    order_number = db.Column(db.String(50), unique=True, nullable=False, index=True)
    customer_phone = db.Column(db.String(20), nullable=False, index=True)
    total_price = db.Column(db.Numeric(10, 2), nullable=False)
    status = db.Column(db.Enum(OrderStatus), nullable=False, default=OrderStatus.PENDING, index=True)

    __table_args__ = (
        Index('idx_order_phone_status', 'customer_phone', 'status'),
    )

    @validates('customer_phone')
    def validate_phone(self, key, phone):
        if not PHONE_REGEX.match(phone):
            raise ValueError(f"Invalid phone number format for Order: {phone}")
        return phone

    def to_dict(self) -> Dict[str, Any]:
        """Serializes the Order object to a dictionary."""
        try:
            return {
                'id': self.id,
                'order_number': self.order_number,
                'customer_phone': self.customer_phone,
                'total_price': float(self.total_price) if self.total_price is not None else 0.0,
                'status': self.status.value,
                'created_at': self.created_at.isoformat(),
                'updated_at': self.updated_at.isoformat()
            }
        except (AttributeError, TypeError) as e:
            logger.error(f"Serialization error for Order {self.id}: {e}")
            raise ValueError(f"Error serializing Order: {str(e)}")

    def __repr__(self) -> str:
        return f"<Order {self.order_number}>"