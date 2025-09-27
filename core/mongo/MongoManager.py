# core/mongo/MongoManager.py
import pymongo
from pymongo import MongoClient, UpdateOne
from datetime import datetime, timedelta
import logging
from typing import List, Optional
from bson import ObjectId

# Importar los schemas Pydantic
from .Schemas import ProductBase, ProductResponse, ProductUpdate

# Configurar logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class MongoManager:
    def _init_(self, connection_string: str = None, db_name: str = "alkosto_db"):
        """
        Inicializa el manager de MongoDB

        Args:
            connection_string: String de conexión a MongoDB
            db_name: Nombre de la base de datos
        """

        atlas_connection_string = "mongodb+srv://grupoTyrrel:mordemi123_@mongocluster-upb.ui6lmw6.mongodb.net/?retryWrites=true&w=majority&appName=mongocluster-upb"

        self.connection_string = connection_string or atlas_connection_string  # Modifica esta línea
        self.db_name = db_name
        self.client = None
        self.db = None
        self.products_collection = None

        self.connect()

    def connect(self):
        """Establece conexión con MongoDB"""
        try:
            self.client = MongoClient(
                self.connection_string,
                serverSelectionTimeoutMS=5000,
                connectTimeoutMS=5000,
                socketTimeoutMS=5000
            )

            # Verificar conexión
            self.client.admin.command('ping')
            logger.info("✅ Conexión exitosa a MongoDB")

            self.db = self.client[self.db_name]
            self.products_collection = self.db['products']

            # Crear índices para optimizar búsquedas
            self._create_indexes()

        except pymongo.errors.ServerSelectionTimeoutError:
            logger.error("❌ No se pudo conectar a MongoDB")
            raise
        except Exception as e:
            logger.error(f"❌ Error de conexión: {e}")
            raise

    def _create_indexes(self):
        """Crea índices para optimizar las consultas"""
        indexes = [
            [("name", pymongo.TEXT)],  # Índice de texto para búsquedas
            [("category", 1)],  # Índice por categoría
            [("brand", 1)],  # Índice por marca
            [("discount_percent", -1)],  # Índice por descuento (descendente)
            [("scraping_date", -1)],  # Índice por fecha de scraping
            [("product_url", 1)],  # Índice único para URLs
        ]

        for index in indexes:
            try:
                self.products_collection.create_index(index)
            except Exception as e:
                logger.warning(f"⚠️ Error creando índice: {e}")

    def save_products(self, products: List[ProductBase], category: str = None) -> int:
        """
        Guarda productos validados con Pydantic en MongoDB

        Args:
            products: Lista de objetos ProductBase
            category: Categoría de los productos (opcional)
        """
        if not products:
            logger.warning("⚠️ No hay productos para guardar")
            return 0

        try:
            operations = []

            for product in products:
                # Convertir el modelo Pydantic a dict
                product_dict = product.dict()
                product_dict['last_updated'] = datetime.now()

                # Sobrescribir categoría si se proporciona
                if category:
                    product_dict['category'] = category

                # Crear operación de upsert
                operation = UpdateOne(
                    {'product_url': product_dict['product_url']},
                    {'$set': product_dict},
                    upsert=True
                )
                operations.append(operation)

            # Ejecutar operaciones en lote
            if operations:
                result = self.products_collection.bulk_write(operations)
                total = result.upserted_count + result.modified_count
                logger.info(
                    f"💾 Guardados: {result.upserted_count} nuevos, Actualizados: {result.modified_count} productos")
                return total

            return 0

        except Exception as e:
            logger.error(f"❌ Error guardando productos: {e}")
            return 0

    def get_product_by_url(self, product_url: str) -> Optional[ProductResponse]:
        """Obtiene un producto por su URL (devuelve objeto ProductResponse)"""
        try:
            product_data = self.products_collection.find_one({'product_url': product_url})
            if product_data:
                return ProductResponse(**product_data)
            return None
        except Exception as e:
            logger.error(f"❌ Error obteniendo producto: {e}")
            return None

    def get_products_by_category(self, category: str, limit: int = 100) -> List[ProductResponse]:
        """Obtiene productos por categoría (devuelve lista de ProductResponse)"""
        try:
            products_data = list(self.products_collection.find(
                {'category': category}
            ).sort('scraping_date', -1).limit(limit))

            return [ProductResponse(**product) for product in products_data]
        except Exception as e:
            logger.error(f"❌ Error obteniendo productos por categoría: {e}")
            return []

    def get_products_with_discount(self, min_discount: float = 10, limit: int = 50) -> List[ProductResponse]:
        """Obtiene productos con descuento mínimo"""
        try:
            products_data = list(self.products_collection.find({
                'discount_percent': {'$ne': "0%"},
                'discount_price_num': {'$gt': 0},
                'original_price_num': {'$gt': 0},
                '$expr': {
                    '$gte': [
                        {'$subtract': ['$original_price_num', '$discount_price_num']},
                        min_discount
                    ]
                }
            }).sort('discount_percent', -1).limit(limit))

            return [ProductResponse(**product) for product in products_data]
        except Exception as e:
            logger.error(f"❌ Error obteniendo productos con descuento: {e}")
            return []

    def search_products(self, search_term: str, limit: int = 50) -> List[ProductResponse]:
        """Busca productos por texto"""
        try:
            products_data = list(self.products_collection.find(
                {'$text': {'$search': search_term}},
                {'score': {'$meta': 'textScore'}}
            ).sort([('score', {'$meta': 'textScore'})]).limit(limit))

            return [ProductResponse(**product) for product in products_data]
        except Exception as e:
            logger.error(f"❌ Error buscando productos: {e}")
            return []

    def get_product_count(self) -> int:
        """Obtiene el número total de productos"""
        try:
            return self.products_collection.count_documents({})
        except Exception as e:
            logger.error(f"❌ Error contando productos: {e}")
            return 0

    def get_categories(self) -> List[str]:
        """Obtiene lista de categorías únicas"""
        try:
            return self.products_collection.distinct('category')
        except Exception as e:
            logger.error(f"❌ Error obteniendo categorías: {e}")
            return []

    def update_product(self, product_url: str, update_data: ProductUpdate) -> bool:
        """Actualiza un producto específico"""
        try:
            update_dict = update_data.dict(exclude_unset=True)
            update_dict['last_updated'] = datetime.now()

            result = self.products_collection.update_one(
                {'product_url': product_url},
                {'$set': update_dict}
            )

            return result.modified_count > 0
        except Exception as e:
            logger.error(f"❌ Error actualizando producto: {e}")
            return False

    def delete_old_products(self, days_old: int = 30) -> int:
        """Elimina productos más viejos que X días"""
        try:
            cutoff_date = datetime.now() - timedelta(days=days_old)
            result = self.products_collection.delete_many({
                'scraping_date': {'$lt': cutoff_date.isoformat()}
            })
            logger.info(f"🗑️ Eliminados {result.deleted_count} productos viejos")
            return result.deleted_count
        except Exception as e:
            logger.error(f"❌ Error eliminando productos viejos: {e}")
            return 0

    def close_connection(self):
        """Cierra la conexión con MongoDB"""
        if self.client:
            self.client.close()
            logger.info("🔌 Conexión a MongoDB cerrada")

    def __enter__(self):
        """Para usar con context manager"""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Cierra conexión al salir del context manager"""
        self.close_connection()

    def get_all_products(self, limit=10000):
        """Obtiene todos los productos de la base de datos"""
        try:
            return list(self.products_collection.find({}).limit(limit))
        except Exception as e:
            logger.error(f"❌ Error obteniendo todos los productos: {e}")
            return []

    def search_products_by_spec(self, spec_key, spec_value, limit=10):
        """Busca productos por especificación específica"""
        try:
            query = {f"specifications.{spec_key}": {"$regex": spec_value, "$options": "i"}}
            products = list(self.products_collection.find(query).limit(limit))
            return [ProductResponse(**p) for p in products]
        except Exception as e:
            logger.error(f"❌ Error buscando por especificación: {e}")
            return []

    def search_products_by_price_range(self, min_price, max_price, limit=10):
        """Busca productos por rango de precio"""
        try:
            query = {
                "discount_price_num": {"$gte": min_price, "$lte": max_price}
            }
            products = list(self.products_collection.find(query).limit(limit))
            return [ProductResponse(**p) for p in products]
        except Exception as e:
            logger.error(f"❌ Error buscando por precio: {e}")
            return []