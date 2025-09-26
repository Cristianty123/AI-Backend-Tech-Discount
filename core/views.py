from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.contrib.auth.decorators import login_required
import json
import os
import uuid
from datetime import datetime
from core.chatbot.TechChatbot import TechChatbot
from core.chat_management.chat_manager import ChatManager
import logging

logger = logging.getLogger(__name__)

# Diccionario para almacenar instancias de chatbot por sesión
_chatbot_instances = {}


def get_chatbot_for_session(session_id):
    """Obtiene o crea una instancia de chatbot para una sesión específica"""
    if session_id not in _chatbot_instances:
        api_key = os.getenv('GROQ_API_KEY')
        if not api_key:
            raise ValueError("GROQ_API_KEY no está configurada en las variables de entorno")

        _chatbot_instances[session_id] = TechChatbot(api_key)
        logger.info(f"✅ Nuevo chatbot inicializado para sesión: {session_id}")

    return _chatbot_instances[session_id]


@csrf_exempt
@require_http_methods(["POST"])
def chatWithChatbotWithoutLogin(request):
    """
    Endpoint para chat con el chatbot sin requerir login
    """
    try:
        data = json.loads(request.body)
        user_message = data.get('message', '').strip()
        session_id = data.get('session_id')

        if not user_message:
            return JsonResponse({
                'success': False,
                'error': 'El mensaje no puede estar vacío',
                'session_id': session_id or 'none'
            }, status=400)

        if not session_id:
            session_id = str(uuid.uuid4())
            logger.info(f"🆕 Nueva sesión creada: {session_id}")

        # Obtener o crear chat para sesión anónima
        chat = ChatManager.get_or_create_chat(session_id)

        # Guardar mensaje del usuario
        ChatManager.save_message(chat, 'user', user_message)

        chatbot = get_chatbot_for_session(session_id)
        logger.info(f"💬 Mensaje recibido - Session: {session_id}")

        response = chatbot.chat(user_message)
        logger.info(f"🤖 Respuesta generada - Session: {session_id}")

        # Guardar respuesta del asistente
        ChatManager.save_message(chat, 'ai', response)

        return JsonResponse({
            'success': True,
            'response': response,
            'session_id': session_id,
            'chat_id': str(chat.id) if chat else None,
            'timestamp': datetime.now().isoformat()
        })

    except json.JSONDecodeError:
        logger.error("❌ Error parsing JSON")
        return JsonResponse({
            'success': False,
            'error': 'Formato JSON inválido'
        }, status=400)
    except Exception as e:
        logger.error(f"❌ Error en el chatbot: {str(e)}")
        return JsonResponse({
            'success': False,
            'error': 'Error interno del servidor'
        }, status=500)


@login_required
@csrf_exempt
@require_http_methods(["POST"])
def chatWithChatbotLoggedIn(request):
    """
    Endpoint para chat con el chatbot para usuarios logueados
    """
    try:
        data = json.loads(request.body)
        user_message = data.get('message', '').strip()
        chat_id = data.get('chat_id')  # Opcional: chat específico

        if not user_message:
            return JsonResponse({
                'success': False,
                'error': 'El mensaje no puede estar vacío'
            }, status=400)

        # Usar chat existente o crear uno nuevo
        if chat_id:
            try:
                from core.models import Chat
                chat = Chat.objects.get(id=chat_id, user=request.user)
            except Chat.DoesNotExist:
                return JsonResponse({
                    'success': False,
                    'error': 'Chat no encontrado'
                }, status=404)
        else:
            chat = ChatManager.get_or_create_chat(None, request.user)

        # Guardar mensaje del usuario
        ChatManager.save_message(chat, 'user', user_message)

        # Usar session_id basado en user_id para consistencia
        session_id = f"user_{request.user.id}"
        chatbot = get_chatbot_for_session(session_id)

        response = chatbot.chat(user_message)

        # Guardar respuesta del asistente
        ChatManager.save_message(chat, 'ai', response)

        return JsonResponse({
            'success': True,
            'response': response,
            'chat_id': str(chat.id) if chat else None,
            'timestamp': datetime.now().isoformat()
        })

    except Exception as e:
        logger.error(f"❌ Error en chat logueado: {str(e)}")
        return JsonResponse({
            'success': False,
            'error': 'Error interno del servidor'
        }, status=500)


@login_required
@require_http_methods(["GET"])
def getUserChats(request):
    """Obtener todos los chats del usuario"""
    try:
        chats = ChatManager.get_user_chats(request.user)

        chat_list = []
        for chat in chats:
            last_message = chat.messages.last()
            chat_list.append({
                'id': str(chat.id),
                'title': chat.title,
                'created_at': chat.created_at.isoformat(),
                'last_message': last_message.content if last_message else '',
                'message_count': chat.messages.count()
            })

        return JsonResponse({
            'success': True,
            'chats': chat_list
        })
    except Exception as e:
        logger.error(f"❌ Error al obtener chats: {str(e)}")
        return JsonResponse({
            'success': False,
            'error': 'Error al obtener chats'
        }, status=500)


@login_required
@require_http_methods(["GET"])
def getChatMessages(request, chat_id):
    """Obtener mensajes de un chat específico"""
    try:
        messages = ChatManager.get_chat_messages(chat_id, request.user)

        message_list = []
        for message in messages:
            message_list.append({
                'id': str(message.id),
                'sender': message.sender,
                'content': message.content,
                'timestamp': message.created_at.isoformat()
            })

        return JsonResponse({
            'success': True,
            'messages': message_list
        })

    except Exception as e:
        logger.error(f"❌ Error al obtener mensajes: {str(e)}")
        return JsonResponse({
            'success': False,
            'error': 'Chat no encontrado'
        }, status=404)

@csrf_exempt
@require_http_methods(["POST"])
def searchProducts(request):
    """
    Endpoint separado para búsqueda específica de productos
    """
    try:
        data = json.loads(request.body)
        search_query = data.get('query', '').strip()
        session_id = data.get('session_id')
        top_k = data.get('limit', 5)  # Número máximo de resultados

        if not search_query:
            return JsonResponse({
                'success': False,
                'error': 'La consulta de búsqueda no puede estar vacía'
            }, status=400)

        # Usar la misma sesión o crear una nueva
        if not session_id:
            session_id = str(uuid.uuid4())

        chatbot = get_chatbot_for_session(session_id)

        logger.info(f"🔍 Búsqueda de productos - Query: '{search_query}'")

        # Buscar productos usando el embedding manager
        products = chatbot.embedding_manager.search_products(search_query, top_k=top_k)

        # Formatear resultados
        formatted_products = []
        for product in products:
            formatted_products.append({
                'id': product.get('id'),
                'name': product.get('name', 'Producto sin nombre'),
                'brand': product.get('brand', 'Sin marca'),
                'category': product.get('category', 'Sin categoría'),
                'price': product.get('price', 0),
                'discount_percent': product.get('discount_percent', '0%'),
                'image_url': product.get('image_url'),
                'product_url': product.get('product_url'),
                'similarity_score': product.get('similarity_score', 0),
                'specifications': product.get('specifications', {})
            })

        return JsonResponse({
            'success': True,
            'products': formatted_products,
            'total_results': len(products),
            'session_id': session_id,
            'query': search_query,
            'timestamp': datetime.now().isoformat()
        })

    except Exception as e:
        logger.error(f"❌ Error en búsqueda de productos: {str(e)}")
        return JsonResponse({
            'success': False,
            'error': 'Error al buscar productos'
        }, status=500)


@csrf_exempt
@require_http_methods(["POST"])
def clearChatHistory(request):
    """
    Endpoint para limpiar el historial de chat de una sesión
    """
    try:
        data = json.loads(request.body)
        session_id = data.get('session_id')

        if not session_id:
            return JsonResponse({
                'success': False,
                'error': 'Session ID es requerido'
            }, status=400)

        if session_id in _chatbot_instances:
            _chatbot_instances[session_id].clear_history()
            logger.info(f"🧹 Historial limpiado para sesión: {session_id}")

        return JsonResponse({
            'success': True,
            'message': 'Historial de conversación limpiado',
            'session_id': session_id
        })

    except Exception as e:
        logger.error(f"❌ Error al limpiar historial: {str(e)}")
        return JsonResponse({
            'success': False,
            'error': 'Error al limpiar el historial'
        }, status=500)