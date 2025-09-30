import os
import json
import pickle
import numpy as np
import faiss
from sentence_transformers import SentenceTransformer
from typing import List, Dict, Tuple, Optional
import logging
import re
from datetime import datetime
from core.mongo.MongoManager import MongoManager

logger = logging.getLogger(__name__)


class EmbeddingManager:
    """Maneja la creación y búsqueda de embeddings para productos"""

    def __init__(self, model_name: str = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"):
        self.model_name = model_name
        self.model = None
        self.index = None
        self.product_metadata = []
        self.embeddings_path = "data/embeddings/"

        # Crear directorio si no existe
        os.makedirs(self.embeddings_path, exist_ok=True)

        self.index_file = os.path.join(self.embeddings_path, "product_index.faiss")
        self.metadata_file = os.path.join(self.embeddings_path, "product_metadata.json")
        self.embeddings_file = os.path.join(self.embeddings_path, "product_embeddings.pkl")

        # Mapa de categorías mejorado y completo
        self.category_map = {
            'celulares/smartphones': 'Smartphones',
            'smartphones': 'Smartphones',
            'celulares': 'Smartphones',
            'computadores-tablet/computadores-portatiles': 'Portátiles',
            'portatiles': 'Portátiles',
            'laptops': 'Portátiles',
            'computadores-tablet/computadores-escritorio-all-in-one': 'Computadores de Escritorio',
            'computadores_escritorio': 'Computadores de Escritorio',
            'desktops': 'Computadores de Escritorio',
            'computadores-tablet/tabletas-ipads': 'Tablets',
            'tabletas': 'Tablets',
            'tablets': 'Tablets',
            'accesorios-electronica': 'Accesorios Electrónicos',
            'accesorios_electronicos': 'Accesorios Electrónicos',
            'computadores-tablet/monitores': 'Monitores',
            'monitores': 'Monitores',
            'computadores-tablet/proyectores-videobeam': 'Proyectores',
            'proyectores': 'Proyectores',
            'tv/smart-tv': 'Televisores',
            'televisores': 'Televisores',
            'tvs': 'Televisores',
            'complementos-tv': 'Complementos TV',
            'complementos_tv': 'Complementos TV',
            'accesorios-electronica/accesorios-tv-video': 'Accesorios TV',
            'videojuegos/consolas': 'Consolas',
            'consolas': 'Consolas',
            'videojuegos/accesorios-videojuegos': 'Accesorios Videojuegos',
            'audio / audifonos': 'Audífonos',
            'audifonos': 'Audífonos',
            'audífonos': 'Audífonos',
            'headphones': 'Audífonos',
            'casa-inteligente-domotica': 'Casa Inteligente',
            'casa_inteligente': 'Casa Inteligente',
            'smart home': 'Casa Inteligente'
        }

        # Términos de stopwords para excluir de las búsquedas
        self.stopwords = {'busca', 'un', 'una', 'el', 'la', 'los', 'las', 'de', 'en', 'y', 'con', 'para'}

        self._load_model()
        self._load_or_create_index()

    def _save_index_to_mongodb(self):
        """Guarda el índice FAISS en MongoDB"""
        try:
            if self.index is None:
                logger.warning("⚠️ No hay índice para guardar")
                return False

            # Serializar índice FAISS
            index_bytes = faiss.serialize_index(self.index)

            # Guardar en MongoDB - index_bytes YA es bytes, no necesita conversión
            mongo = MongoManager()
            result = mongo.save_faiss_index({
                'index_data': index_bytes,  # Esto ya es bytes de faiss.serialize_index
                'dimension': self.index.d,
                'total_products': self.index.ntotal,
                'created_at': datetime.now()
            })

            if result:
                logger.info("✅ Índice FAISS guardado en MongoDB")
                return True
            else:
                logger.error("❌ No se pudo guardar el índice en MongoDB")
                return False

        except Exception as e:
            logger.error(f"❌ Error guardando índice en MongoDB: {e}")
            return False

    def _load_index_from_mongodb(self):
        """Carga el índice FAISS desde MongoDB"""
        try:
            mongo = MongoManager()
            index_data = mongo.get_faiss_index()

            if index_data and 'index_data' in index_data:
                # index_data['index_data'] ya debería ser bytes listo para faiss.deserialize_index
                self.index = faiss.deserialize_index(index_data['index_data'])

                # Cargar metadata también
                self.product_metadata = mongo.get_embeddings_metadata()

                logger.info(f"✅ Índice FAISS cargado desde MongoDB: {self.index.ntotal} productos")
                return True
            return False
        except Exception as e:
            logger.error(f"❌ Error cargando índice desde MongoDB: {e}")
            return False

    def _save_metadata_to_mongodb(self):
        """Guarda la metadata en MongoDB"""
        try:
            mongo = MongoManager()
            result = mongo.save_embeddings_metadata(self.product_metadata)
            if result:
                logger.info("✅ Metadata guardada en MongoDB")
                return True
            else:
                logger.error("❌ No se pudo guardar metadata en MongoDB")
                return False
        except Exception as e:
            logger.error(f"❌ Error guardando metadata en MongoDB: {e}")
            return False

    def _load_model(self):
        """Carga el modelo de sentence transformers"""
        try:
            logger.info(f"Cargando modelo {self.model_name}...")
            self.model = SentenceTransformer(self.model_name)
            logger.info("✅ Modelo de embeddings cargado correctamente")
        except Exception as e:
            logger.error(f"❌ Error cargando modelo: {e}")
            # Fallback a modelo más pequeño si el principal falla
            self.model = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")
            logger.info("✅ Modelo fallback cargado correctamente")

    def _normalize_category(self, category: str) -> str:
        """Normaliza las categorías para consistencia"""
        if not category:
            return "Sin categoría"

        category_lower = category.lower().strip()
        return self.category_map.get(category_lower, category)

    def _clean_text(self, text: str) -> str:
        """Limpia y normaliza el texto para embeddings"""
        if not text:
            return ""

        # Remover caracteres especiales y múltiples espacios
        text = re.sub(r'[^\w\s|:.-]', ' ', text)
        text = re.sub(r'\s+', ' ', text)
        return text.strip()

    def _is_main_product_category(self, category: str) -> bool:
        """Determina si una categoría es de producto principal (no accesorio)"""
        main_categories = {
            'smartphones', 'portátiles', 'computadores de escritorio', 'tablets',
            'televisores', 'monitores', 'proyectores', 'consolas', 'audífonos'
        }
        return category.lower() in main_categories

    def _create_product_text(self, product: Dict) -> str:
        """Crea texto completo optimizado para embeddings con priorización"""
        try:
            # Información básica con énfasis en nombre y marca
            name = product.get('name', '')
            brand = product.get('brand', 'Sin marca')
            original_category = product.get('category', '')
            category = self._normalize_category(original_category)

            # Precios
            price = product.get('discount_price_num', product.get('original_price_num', 0))
            discount = product.get('discount_percent', '0%')

            # Texto estructurado con prioridad para productos principales
            text_parts = []

            # Énfasis en nombre (repetido para mayor peso)
            text_parts.append(f"Producto: {name}")

            # Para portátiles, enfatizar que son portátiles
            if 'portátil' in category.lower() or 'portatil' in name.lower():
                text_parts.append("Tipo: Computador Portátil Laptop Notebook")
                text_parts.append("Es portátil: sí")
            # Para All-in-One, clarificar que NO son portátiles
            elif 'escritorio' in category.lower() or 'all in one' in name.lower():
                text_parts.append("Tipo: Computador de Escritorio All-in-One")
                text_parts.append("Es portátil: no")

            # Información clave
            text_parts.append(f"Nombre: {name}")
            text_parts.append(f"Marca: {brand}")
            text_parts.append(f"Categoría: {category}")

            # Solo incluir precio si es producto principal
            if self._is_main_product_category(category):
                text_parts.append(f"Precio: {price:.0f} pesos")
                if discount not in ['0%', '0', 'Sin descuento']:
                    text_parts.append(f"Descuento: {discount}")

            text_parts.append(f"Tienda: {product.get('source', 'alkosto')}")

            # Especificaciones clave con prioridad
            specs = product.get('specifications', {})

            # Priorizar especificaciones técnicas para productos principales
            important_specs = [
                'procesador', 'processor', 'cpu', 'ram', 'memoria', 'almacenamiento',
                'storage', 'disco', 'pantalla', 'screen', 'display', 'batería', 'battery',
                'cámara', 'camera', 'color', 'modelo', 'model', 'tamaño', 'size',
                'resolución', 'resolution', 'capacidad', 'capacity', 'sistema operativo',
                'os', 'android', 'ios', 'windows', 'pulgadas', 'pulgada', 'inch'
            ]

            for key, value in specs.items():
                key_lower = key.lower()
                if any(important in key_lower for important in important_specs):
                    text_parts.append(f"Especificación: {key}: {value}")

            # Para productos principales, incluir todas las especificaciones
            if self._is_main_product_category(category) and len(specs) <= 15:
                for key, value in specs.items():
                    if f"{key}: {value}" not in " | ".join(text_parts):
                        text_parts.append(f"Detalle: {key}: {value}")

            text = " | ".join(text_parts)
            return self._clean_text(text)

        except Exception as e:
            logger.error(f"Error creando texto para producto: {e}")
            return product.get('name', 'Producto sin nombre')

    def create_embeddings_from_db(self, batch_size: int = 50) -> bool:
        """Crea embeddings para todos los productos en la base de datos"""
        try:
            logger.info("🔄 Iniciando creación de embeddings...")

            # Obtener productos de MongoDB - CON MEJOR MANEJO DE ERRORES
            try:
                mongo = MongoManager()
                products = mongo.get_all_products()

                if not products:
                    logger.warning("⚠️ No hay productos en la base de datos")
                    return False

            except Exception as mongo_error:
                logger.error(f"❌ Error obteniendo productos de MongoDB: {mongo_error}")
                logger.warning("🔄 Continuando con datos locales existentes...")

                # Verificar si ya tenemos datos locales
                if os.path.exists(self.metadata_file) and os.path.exists(self.index_file):
                    logger.info("📂 Usando embeddings locales existentes")
                    return True  # Considerar éxito porque tenemos datos locales
                else:
                    logger.error("❌ No hay datos locales disponibles")
                    return False

            logger.info(f"📦 Procesando {len(products)} productos...")

            # Crear textos para embedding
            product_texts = []
            metadata = []

            for product in products:
                text = self._create_product_text(product)
                product_texts.append(text)

                # Guardar metadata importante
                metadata.append({
                    'id': str(product.get('_id')),
                    'name': product.get('name', ''),
                    'brand': product.get('brand', ''),
                    'category': self._normalize_category(product.get('category', '')),
                    'price': product.get('discount_price_num', product.get('original_price_num', 0)),
                    'discount_percent': product.get('discount_percent', '0%'),
                    'product_url': product.get('product_url', ''),
                    'image_url': product.get('image_url', ''),
                    'availability': product.get('availability', 'Disponible'),
                    'specifications': product.get('specifications', {}),
                    'source': product.get('source', 'alkosto'),
                    'is_main_product': self._is_main_product_category(
                        self._normalize_category(product.get('category', ''))
                    )
                })

            # Crear embeddings en lotes más pequeños para mejor manejo
            all_embeddings = []
            for i in range(0, len(product_texts), batch_size):
                batch = product_texts[i:i + batch_size]
                logger.info(f"Procesando lote {i // batch_size + 1}/{(len(product_texts) - 1) // batch_size + 1}")

                batch_embeddings = self.model.encode(
                    batch,
                    show_progress_bar=True,
                    convert_to_numpy=True,
                    normalize_embeddings=True
                )
                all_embeddings.append(batch_embeddings)

            # Concatenar todos los embeddings
            embeddings = np.vstack(all_embeddings)

            # Crear índice FAISS con métrica de similitud coseno
            dimension = embeddings.shape[1]
            self.index = faiss.IndexFlatIP(dimension)

            # Los embeddings ya están normalizados
            self.index.add(embeddings)

            # Guardar índice y metadata LOCALMENTE
            faiss.write_index(self.index, self.index_file)

            with open(self.metadata_file, 'w', encoding='utf-8') as f:
                json.dump(metadata, f, ensure_ascii=False, indent=2)

            with open(self.embeddings_file, 'wb') as f:
                pickle.dump(embeddings, f)

            self.product_metadata = metadata

            # GUARDAR EN MONGODB TAMBIÉN - CON MANEJO DE ERROR
            try:
                self._save_index_to_mongodb()
                self._save_metadata_to_mongodb()
            except Exception as save_error:
                logger.warning(f"⚠️ No se pudo guardar en MongoDB: {save_error}")
                logger.info("💾 Datos guardados localmente solamente")

            logger.info(f"✅ Embeddings creados correctamente: {embeddings.shape}")
            logger.info(f"💾 Índice guardado localmente")

            return True

        except Exception as e:
            logger.error(f"❌ Error creando embeddings: {e}")
            import traceback
            traceback.print_exc()
            return False

    def _load_or_create_index(self):
        """Carga el índice desde MongoDB o archivos locales"""
        try:
            # PRIMERO intentar cargar desde MongoDB
            try:
                if self._load_index_from_mongodb():
                    logger.info(f"✅ Sistema cargado desde MongoDB: {self.index.ntotal} productos")
                    return
            except Exception as mongo_error:
                logger.warning(f"⚠️ No se pudo cargar desde MongoDB: {mongo_error}")

            # SEGUNDO: intentar cargar desde archivos locales
            if (os.path.exists(self.index_file) and
                    os.path.exists(self.metadata_file) and
                    os.path.getsize(self.index_file) > 0):

                logger.info("📂 Cargando índice local...")
                self.index = faiss.read_index(self.index_file)

                with open(self.metadata_file, 'r', encoding='utf-8') as f:
                    self.product_metadata = json.load(f)

                logger.info(f"✅ Índice local cargado: {self.index.ntotal} productos")

                # Intentar guardar en MongoDB para el futuro (pero no fallar si no puede)
                try:
                    self._save_index_to_mongodb()
                    self._save_metadata_to_mongodb()
                except Exception:
                    logger.warning("⚠️ No se pudo sincronizar con MongoDB")

            else:
                logger.info("⚠️ No se encontró índice. Use create_embeddings_from_db() para crearlo")

        except Exception as e:
            logger.error(f"❌ Error cargando índice: {e}")
            self.index = None
            self.product_metadata = []

    def _clean_query(self, query: str) -> str:
        """Limpia y mejora la consulta"""
        # Remover stopwords
        words = query.lower().split()
        cleaned_words = [word for word in words if word not in self.stopwords]
        cleaned_query = ' '.join(cleaned_words)

        # Expansión de términos para mejores resultados
        query_expansions = {
            'victus': 'hp victus gaming laptop computador portátil',
            'portatil': 'portátil laptop computador notebook es portátil sí',
            'portátil': 'portátil laptop computador notebook es portátil sí',
            'portatiles': 'portátiles laptops computadores notebooks es portátil sí',
            'portátiles': 'portátiles laptops computadores notebooks es portátil sí',
            'laptop': 'portátil laptop computador notebook es portátil sí',
            'computador': 'computador pc ordenador',
            'celular': 'celular smartphone móvil teléfono',
            'smartphone': 'smartphone celular móvil',
            'tablet': 'tablet ipad',
            'tv': 'televisor tv smart television',
            'televisor': 'televisor tv smart television',
            'audifonos': 'audífonos headphones auriculares',
            'gamer': 'gamer gaming juegos',
            'categoria': 'categoría tipo'
        }

        expanded_query = cleaned_query
        for term, expansion in query_expansions.items():
            if term in cleaned_query:
                expanded_query += " " + expansion

        # Para búsquedas de categoría específica, enfatizar el tipo
        if any(word in cleaned_query for word in ['categoria', 'categoría', 'tipo']):
            if 'portatil' in cleaned_query or 'portátil' in cleaned_query:
                expanded_query += " es portátil sí no all-in-one no escritorio"

        return expanded_query.strip()

    def search_products(self, query: str, top_k: int = 10, threshold: float = 0.4) -> List[Dict]:
        """Busca productos similares a la consulta con mejoras"""
        try:
            if self.index is None or not self.product_metadata:
                logger.error("❌ Índice no cargado. Ejecute create_embeddings_from_db() primero")
                return []

            # Limpiar y mejorar la consulta
            cleaned_query = self._clean_query(query)

            # Para búsquedas específicas de portátiles, ajustar el threshold
            adjusted_threshold = threshold
            if any(word in query.lower() for word in ['portatil', 'portátil', 'laptop', 'notebook']):
                adjusted_threshold = max(threshold, 0.45)  # Threshold más alto para portátiles

            # Crear embedding de la consulta
            query_embedding = self.model.encode([cleaned_query], normalize_embeddings=True)

            # Buscar más resultados para luego filtrar
            scores, indices = self.index.search(query_embedding, min(top_k * 3, self.index.ntotal))

            results = []
            seen_products = set()
            main_products = []
            accessory_products = []

            for score, idx in zip(scores[0], indices[0]):
                if idx >= len(self.product_metadata) or idx < 0 or score < adjusted_threshold:
                    continue

                product = self.product_metadata[idx].copy()
                product['similarity_score'] = float(score)

                # Evitar duplicados por nombre similar
                product_name = product['name'].lower()
                if product_name in seen_products:
                    continue

                seen_products.add(product_name)

                # Para búsquedas de portátiles, penalizar All-in-One
                if any(word in query.lower() for word in ['portatil', 'portátil', 'laptop', 'notebook']):
                    category = product.get('category', '').lower()
                    if 'escritorio' in category or 'all-in-one' in product_name:
                        # Reducir score para All-in-One en búsquedas de portátiles
                        product['similarity_score'] *= 0.7

                # Separar productos principales de accesorios
                if product.get('is_main_product', False):
                    main_products.append(product)
                else:
                    accessory_products.append(product)

            # Priorizar productos principales
            results = main_products[:top_k]

            # Si no hay suficientes productos principales, agregar accesorios
            if len(results) < top_k:
                results.extend(accessory_products[:top_k - len(results)])

            # Ordenar por score descendente
            results.sort(key=lambda x: x['similarity_score'], reverse=True)

            logger.info(f"🔍 Encontrados {len(results)} productos para: '{query}'")
            return results

        except Exception as e:
            logger.error(f"❌ Error en búsqueda: {e}")
            import traceback
            traceback.print_exc()
            return []

    def search_by_filters(self, query: str = None, category: str = None,
                          min_price: float = None, max_price: float = None,
                          brand: str = None, with_discount: bool = False,
                          top_k: int = 10, threshold: float = 0.4) -> List[Dict]:
        """Búsqueda avanzada con filtros y embeddings combinados"""
        try:
            if query:
                # Búsqueda semántica primero
                semantic_results = self.search_products(query, top_k * 2, threshold)
            else:
                # Sin query, usar todos los productos
                semantic_results = [{'id': i, **meta} for i, meta in enumerate(self.product_metadata)]
                semantic_results = semantic_results[:top_k * 3]

            filtered_results = []

            for product in semantic_results:
                # Aplicar filtros
                if category and category.lower() not in product.get('category', '').lower():
                    continue

                if brand and brand.lower() not in product.get('brand', '').lower():
                    continue

                price = product.get('price', 0)
                if min_price is not None and price < min_price:
                    continue
                if max_price is not None and price > max_price:
                    continue

                if with_discount and product.get('discount_percent', '0%') in ['0%', '0', 'Sin descuento']:
                    continue

                filtered_results.append(product)

                if len(filtered_results) >= top_k:
                    break

            return filtered_results

        except Exception as e:
            logger.error(f"❌ Error en búsqueda avanzada: {e}")
            return []

    def get_stats(self) -> Dict:
        """Obtiene estadísticas del índice"""
        if not self.product_metadata:
            return {}

        categories = {}
        brands = {}
        price_ranges = {"0-100k": 0, "100k-500k": 0, "500k-1M": 0, "1M-2M": 0, "2M+": 0}
        with_discount = 0

        for product in self.product_metadata:
            # Contar categorías
            cat = product['category']
            categories[cat] = categories.get(cat, 0) + 1

            # Contar marcas
            brand = product['brand']
            if brand:  # Solo contar si tiene marca
                brands[brand] = brands.get(brand, 0) + 1

            # Rangos de precio
            price = product['price']
            if price < 100000:
                price_ranges["0-100k"] += 1
            elif price < 500000:
                price_ranges["100k-500k"] += 1
            elif price < 1000000:
                price_ranges["500k-1M"] += 1
            elif price < 2000000:
                price_ranges["1M-2M"] += 1
            else:
                price_ranges["2M+"] += 1

            # Productos con descuento
            discount = product.get('discount_percent', '0%')
            if discount not in ['0%', '0', 'Sin descuento']:
                with_discount += 1

        return {
            'total_products': len(self.product_metadata),
            'categories': dict(sorted(categories.items(), key=lambda x: x[1], reverse=True)[:10]),
            'top_brands': dict(sorted(brands.items(), key=lambda x: x[1], reverse=True)[:10]),
            'price_ranges': price_ranges,
            'products_with_discount': with_discount,
            'discount_percentage': f"{(with_discount / len(self.product_metadata) * 100):.1f}%" if self.product_metadata else "0%"
        }

    def get_all_products_from_index(self) -> List[Dict]:
        """Obtiene todos los productos del índice (sin búsqueda)"""
        try:
            if not self.product_metadata:
                logger.warning("No hay metadata de productos disponible")
                return []
            return self.product_metadata.copy()  # Devolver copia para no modificar el original
        except Exception as e:
            logger.error(f"Error obteniendo todos los productos: {e}")
            return []