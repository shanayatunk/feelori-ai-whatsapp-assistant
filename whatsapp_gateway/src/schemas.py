# whatsapp_gateway/src/schemas.py
from marshmallow import Schema, fields, validate, ValidationError
import re

class PhoneNumberField(fields.String):
    def _validate(self, value):
        cleaned = re.sub(r'[^\d+]', '', value)
        if not re.match(r'^\+[1-9]\d{9,14}$', cleaned):
            raise ValidationError("Invalid phone number format")

class SendMessageSchema(Schema):
    message = fields.Str(required=True, validate=validate.Length(min=1, max=4096))
    phone = PhoneNumberField(required=True)