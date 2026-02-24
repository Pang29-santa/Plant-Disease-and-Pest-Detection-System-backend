import os
import logging
import ssl
from datetime import datetime
from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv

import certifi

load_dotenv()

# Setup logger for database
logger = logging.getLogger(__name__)

MONGODB_URI = os.getenv("MONGODB_URI", "mongodb://127.0.0.1:27017")
DATABASE_NAME = os.getenv("DATABASE_NAME", "mydb")

# Helper function to mask password in URI for logging
def mask_uri(uri: str) -> str:
    """Hide password in MongoDB URI for safe logging"""
    try:
        if "@" in uri:
            # mongodb+srv://user:pass@host -> mongodb+srv://user:****@host
            parts = uri.split("@")
            auth_part = parts[0].split(":")
            if len(auth_part) >= 3:
                return f"{auth_part[0]}:{auth_part[1]}:****@{parts[1]}"
        return uri
    except:
        return "mongodb://****:****@****"

class Database:
    client: AsyncIOMotorClient = None
    database = None
    is_connected: bool = False
    connection_time: datetime = None
    collections_count: int = 0

    @classmethod
    def get_connection_info(cls) -> dict:
        """Get current connection status"""
        return {
            "connected": cls.is_connected,
            "database": DATABASE_NAME,
            "uri": mask_uri(MONGODB_URI),
            "connected_at": cls.connection_time.isoformat() if cls.connection_time else None,
            "collections_count": cls.collections_count
        }

from utils.exceptions import DatabaseException

db = Database()

def get_mongo_options() -> dict:
    """สร้าง Configuration สำหรับ MongoDB Client"""
    options = {
        'serverSelectionTimeoutMS': 10000,
        'connectTimeoutMS': 20000,
        'socketTimeoutMS': 20000,
        'retryWrites': True,
    }
    
    # ถ้าเป็น Atlas (mongodb+srv) ให้บังคับใช้ SSL และ Certifi
    if 'mongodb+srv' in MONGODB_URI:
        options.update({
            'tls': True,
            'tlsCAFile': certifi.where()
        })
    return options

async def connect_db():
    """Connect to MongoDB with detailed logging"""
    try:
        logger.info("=" * 60)
        logger.info("🔄 [DB] Initializing MongoDB Connection...")
        logger.info(f"   Database Name: {DATABASE_NAME}")
        logger.info(f"   URI: {mask_uri(MONGODB_URI)}")
        
        client_options = get_mongo_options()
        db.client = AsyncIOMotorClient(MONGODB_URI, **client_options)
        db.database = db.client[DATABASE_NAME]
        
        # Verify connection by pinging
        await db.client.admin.command('ping')
        
        db.is_connected = True
        db.connection_time = datetime.now()
        
        # Get collections info
        collections = await db.database.list_collection_names()
        db.collections_count = len(collections)
        
        # Log success
        logger.info("✅ [DB] Connected successfully!")
        logger.info(f"   Connected at: {db.connection_time.strftime('%Y-%m-%d %H:%M:%S')}")
        logger.info(f"   Total Collections: {db.collections_count}")
        
        # Log each collection with document count
        if collections:
            logger.info("📁 Collections:")
            for coll_name in sorted(collections):
                try:
                    count = await db.database[coll_name].count_documents({})
                    logger.info(f"   ✅ {coll_name}: {count} docs")
                except Exception as e:
                    logger.warning(f"   ⚠️  {coll_name}: (error: {e})")
        
        logger.info("=" * 60)
        
    except Exception as e:
        db.is_connected = False
        logger.error("=" * 60)
        logger.error(f"❌ [DB] Connection Failed: {str(e)}")
        logger.error("=" * 60)
        # ส่งต่อ error ไปยัง Global Exception Handler ของ FastAPI
        raise DatabaseException("ไม่สามารถเชื่อมต่อฐานข้อมูลได้", details=str(e))

async def close_db():
    """Close MongoDB connection with logging"""
    if db.client:
        db.client.close()
        db.is_connected = False
        duration = "N/A"
        if db.connection_time:
            duration = str(datetime.now() - db.connection_time).split('.')[0]
        logger.info(f"⏹️  [DB] Disconnected (Duration: {duration})")

def get_collection(collection_name: str):
    """Get MongoDB collection with logging"""
    if not db.is_connected:
        logger.warning(f"⚠️  [DB] Accessing '{collection_name}' but not connected!")
    else:
        logger.debug(f"📂 [DB] Accessing: {collection_name}")
    return db.database[collection_name]

async def check_connection_health() -> dict:
    """Check database connection health"""
    try:
        if not db.client:
            return {"status": "disconnected", "error": "No client initialized"}
        
        # Ping server
        await db.client.admin.command('ping')
        
        # Get server info
        server_info = await db.client.server_info()
        
        return {
            "status": "healthy",
            "database": DATABASE_NAME,
            "mongodb_version": server_info.get("version", "unknown"),
            "uptime": str(datetime.now() - db.connection_time).split('.')[0] if db.connection_time else "unknown"
        }
    except Exception as e:
        return {
            "status": "unhealthy",
            "error": str(e)
        }
