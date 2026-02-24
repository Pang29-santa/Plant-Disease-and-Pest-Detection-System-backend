
from database import get_collection

async def get_next_sequence_value(sequence_name: str) -> int:
    """
    Get the next sequence value for a given sequence name.
    Useful for auto-incrementing fields like user_id.
    """
    collection = get_collection("counters")
    
    # Atomically find the document for the sequence and increment the 'sequence_value'
    # return_document=True means we get the updated document back
    from pymongo import ReturnDocument
    
    result = await collection.find_one_and_update(
        {"_id": sequence_name},
        {"$inc": {"sequence_value": 1}},
        upsert=True,  # usage: create if not exists
        return_document=ReturnDocument.AFTER
    )
    
    return result["sequence_value"]
