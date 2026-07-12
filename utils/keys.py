import hashlib
import uuid

def get_hash(query: str):
    hash = hashlib.md5(query.encode())
    return str(uuid.uuid3(namespace = uuid.NAMESPACE_OID, name = hash.hexdigest()))

def get_cache_key(query: str, chapter: str):
    hash = get_hash(query) + "_" + chapter
    return f"cache:{hash}"

def get_register_key(query: str, chapter: str):
    hash = get_hash(query) + "_" + chapter
    return f"register:{hash}"