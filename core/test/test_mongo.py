from django.test import TestCase
from django.conf import settings
import pymongo
from core.mongo.MongoManager import MongoManager


class MongoDBConnectionTest(TestCase):
    """Pruebas de conexión y funcionalidad básica de MongoDB"""

    def setUp(self):
        """Configuración inicial para las pruebas - USA ATLAS POR DEFECTO"""
        # NO pases connection_string para que use Atlas por defecto
        self.mongo_manager = MongoManager(
            # Al no pasar connection_string, usará MONGODB_URI_ATLAS por defecto
            db_name=settings.MONGODB_DB_NAME
        )



    def tearDown(self):
        """Limpieza después de cada prueba"""
        if hasattr(self, 'mongo_manager'):
            self.mongo_manager.close_connection()

    def test_mongodb_connection_success(self):
        """Prueba que la conexión a MongoDB sea exitosa"""
        try:
            # Verificar que los atributos se inicializan correctamente
            self.assertIsNotNone(self.mongo_manager.client)
            self.assertIsNotNone(self.mongo_manager.db)
            self.assertIsNotNone(self.mongo_manager.products_collection)

            # Verificar que la conexión está activa
            ping_result = self.mongo_manager.client.admin.command('ping')
            self.assertEqual(ping_result['ok'], 1.0)

            print("✅ Conexión a MongoDB exitosa")

        except pymongo.errors.ServerSelectionTimeoutError:
            self.skipTest("MongoDB no está disponible para testing")
        except Exception as e:
            self.fail(f"Error inesperado en la conexión: {e}")

    def test_database_and_collection_exist(self):
        """Prueba que la base de datos y colección existan"""
        try:
            # Verificar que la base de datos existe en la lista de bases de datos
            database_names = self.mongo_manager.client.list_database_names()
            self.assertIn(self.mongo_manager.db_name, database_names)

            # Verificar que la colección existe en la base de datos
            collection_names = self.mongo_manager.db.list_collection_names()
            self.assertIn('products', collection_names)

            print("✅ Base de datos y colección verificadas")

        except pymongo.errors.ServerSelectionTimeoutError:
            self.skipTest("MongoDB no está disponible para testing")

    def test_save_and_retrieve_product(self):
        """Prueba guardar y recuperar un producto de prueba"""
        try:
            # Datos de prueba
            test_product = {
                'name': 'Producto de Prueba',
                'brand': 'Marca Test',
                'category': 'Test Category',
                'product_url': 'https://www.alkosto.com/test-product',
                'discount_percent': '20%',
                'rating': '4.5',
                'original_price': '$1.000.000',
                'original_price_num': 1000000,
                'discount_price': '$800.000',
                'discount_price_num': 800000,
                'image_url': 'https://example.com/image.jpg',
                'specifications': {'RAM': '8GB', 'Storage': '256GB'},
                'availability': 'Disponible',
                'scraping_date': '2024-01-15T10:30:00',
                'source': 'alkosto'
            }

            # Guardar producto
            saved_count = self.mongo_manager.save_products([test_product], 'Test Category')
            self.assertEqual(saved_count, 1)

            # Recuperar producto
            retrieved_product = self.mongo_manager.get_product_by_url(
                'https://www.alkosto.com/test-product'
            )

            # Verificar que los datos coinciden
            self.assertIsNotNone(retrieved_product)
            self.assertEqual(retrieved_product['name'], 'Producto de Prueba')
            self.assertEqual(retrieved_product['brand'], 'Marca Test')
            self.assertEqual(retrieved_product['discount_percent'], '20%')

            print("✅ Guardado y recuperación de producto exitoso")

            # Limpiar producto de prueba
            self.mongo_manager.products_collection.delete_one({
                'product_url': 'https://www.alkosto.com/test-product'
            })

        except pymongo.errors.ServerSelectionTimeoutError:
            self.skipTest("MongoDB no está disponible para testing")

    def test_get_categories_empty(self):
        """Prueba obtener categorías cuando la base de datos está vacía"""
        try:
            categories = self.mongo_manager.get_categories()
            # Debería ser una lista vacía o con algunas categorías si hay datos
            self.assertIsInstance(categories, list)

            print("✅ Obtención de categorías exitosa")

        except pymongo.errors.ServerSelectionTimeoutError:
            self.skipTest("MongoDB no está disponible para testing")

    def test_product_count(self):
        """Prueba contar productos"""
        try:
            count = self.mongo_manager.get_product_count()
            self.assertIsInstance(count, int)
            self.assertGreaterEqual(count, 0)

            print(f"✅ Conteo de productos: {count}")

        except pymongo.errors.ServerSelectionTimeoutError:
            self.skipTest("MongoDB no está disponible para testing")

    def test_connection_string_configuration(self):
        """Prueba que la configuración de conexión sea correcta"""
        self.assertIsNotNone(settings.MONGODB_CONNECTION_STRING)
        self.assertIsNotNone(settings.MONGODB_DB_NAME)

        # Verificar que la string de conexión tiene el formato correcto
        self.assertTrue(
            settings.MONGODB_CONNECTION_STRING.startswith('mongodb') or
            settings.MONGODB_CONNECTION_STRING.startswith('mongodb+srv')
        )

        print("✅ Configuración de conexión verificada")