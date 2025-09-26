from django.utils import timezone
from ..models import Chat, Message
import logging

logger = logging.getLogger(__name__)


class ChatManager:
    @staticmethod
    def get_or_create_chat(session_id, user=None):
        """Obtiene o crea un chat basado en session_id o usuario"""
        try:
            if user and user.is_authenticated:
                # Para usuarios logueados
                chat, created = Chat.objects.get_or_create(
                    user=user,
                    defaults={'title': f"Chat {timezone.now().strftime('%Y-%m-%d %H:%M')}"}
                )
            else:
                # Para usuarios anónimos
                chat, created = Chat.objects.get_or_create(
                    session_id=session_id,
                    defaults={'title': f"Chat {timezone.now().strftime('%Y-%m-%d %H:%M')}"}
                )

            if created:
                logger.info(f"🆕 Nuevo chat creado: {chat.id}")

            return chat
        except Exception as e:
            logger.error(f"❌ Error al obtener/crear chat: {e}")
            # Fallback: crear un chat temporal en memoria si hay error de BD
            return None

    @staticmethod
    def save_message(chat, sender, content):
        """Guarda un mensaje en la base de datos"""
        try:
            if chat:  # Solo guardar si el chat existe (no es fallback)
                message = Message.objects.create(
                    chat=chat,
                    sender=sender,
                    content=content
                )
                return message
            return None
        except Exception as e:
            logger.error(f"❌ Error al guardar mensaje: {e}")
            return None

    @staticmethod
    def get_user_chats(user):
        """Obtiene todos los chats de un usuario"""
        try:
            return Chat.objects.filter(user=user).order_by('-created_at')
        except Exception as e:
            logger.error(f"❌ Error al obtener chats del usuario: {e}")
            return []

    @staticmethod
    def get_chat_messages(chat_id, user=None):
        """Obtiene mensajes de un chat específico"""
        try:
            if user:
                chat = Chat.objects.get(id=chat_id, user=user)
            else:
                chat = Chat.objects.get(id=chat_id)

            return chat.messages.all().order_by('created_at')
        except Chat.DoesNotExist:
            return []
        except Exception as e:
            logger.error(f"❌ Error al obtener mensajes: {e}")
            return []