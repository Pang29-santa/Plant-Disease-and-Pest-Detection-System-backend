"""
Utility Functions for Routes
ฟังก์ชันช่วยเหลือสำหรับ routes
"""

from bson import ObjectId
from datetime import datetime


def serialize_doc(doc: dict) -> dict:
    """Convert MongoDB document to serializable dict"""
    if not doc:
        return doc
    
    result = {}
    for key, value in doc.items():
        if isinstance(value, ObjectId):
            result[key] = str(value)
        elif isinstance(value, datetime):
            result[key] = value.isoformat()
        elif isinstance(value, dict):
            result[key] = serialize_doc(value)
        elif isinstance(value, list):
            result[key] = [
                serialize_doc(item) if isinstance(item, dict) else 
                str(item) if isinstance(item, ObjectId) else
                item.isoformat() if isinstance(item, datetime) else item
                for item in value
            ]
        else:
            result[key] = value
    return result
