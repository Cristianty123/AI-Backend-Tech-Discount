from django.utils import timezone
from ..models import Chat, Message
import logging

logger = logging.getLogger(__name__)


class ChatManager:
    @staticmethod
    def delete_chat(chat_id, user=None):
        """Eliminar un chat y sus mensajes"""
        try:
            if user and user.is_authenticated:
                # Verificar que el chat pertenece al usuario antes de eliminar
                chat = Chat.objects.filter(id=chat_id, user=user).first()
                if chat:
                    chat.delete()
                    logger.info(f"🗑️ Chat eliminado: {chat_id} para usuario: {user.username}")
                    return True
                else:
                    logger.warning(f"⚠️ Chat no encontrado o no pertenece al usuario: {chat_id}")
                    return False
            else:
                raise ValueError("Se requiere usuario autenticado")

        except Exception as e:
            logger.error(f"❌ Error al eliminar chat: {e}")
            return False

    @staticmethod
    def get_or_create_empty_chat(user=None):
        """Obtiene el último chat vacío o crea uno nuevo si no existe"""
        try:
            if user and user.is_authenticated:
                # Buscar el último chat del usuario que no tenga mensajes
                empty_chat = Chat.objects.filter(
                    user=user,
                    messages__isnull=True
                ).order_by('-created_at').first()

                if empty_chat:
                    logger.info(f"🔄 Reutilizando chat vacío: {empty_chat.id}")
                    return empty_chat, False  # False = no fue creado nuevo

                # Si no hay chat vacío, crear uno nuevo
                chat = Chat.objects.create(
                    user=user,
                    title=f"Chat {timezone.now().strftime('%Y-%m-%d %H:%M')}"
                )
                logger.info(f"🆕 Nuevo chat creado: {chat.id}")
                return chat, True  # True = fue creado nuevo
            else:
                raise ValueError("Se requiere usuario autenticado")

        except Exception as e:
            logger.error(f"❌ Error al obtener/crear chat vacío: {e}")
            return None, False

    @staticmethod
    def create_new_chat(user=None, session_id=None):
        """Crear un nuevo chat vacío"""
        try:
            chat_data = {'title': f"Chat {timezone.now().strftime('%Y-%m-%d %H:%M')}"}

            if user and user.is_authenticated:
                chat_data['user'] = user
            elif session_id:
                chat_data['session_id'] = session_id
            else:
                raise ValueError("Se requiere user o session_id")

            chat = Chat.objects.create(**chat_data)
            logger.info(f"🆕 Nuevo chat creado: {chat.id}")
            return chat

        except Exception as e:
            logger.error(f"❌ Error al crear nuevo chat: {e}")
            return None

    @staticmethod
    def get_or_create_chat(session_id, user=None):
        """Obtiene o crea un chat basado en session_id o usuario"""
        try:
            if user and user.is_authenticated:
                chat, created = Chat.objects.get_or_create(
                    user=user,
                    defaults={'title': f"Chat {timezone.now().strftime('%Y-%m-%d %H:%M')}"}
                )
            else:
                chat, created = Chat.objects.get_or_create(
                    session_id=session_id,
                    defaults={'title': f"Chat {timezone.now().strftime('%Y-%m-%d %H:%M')}"}
                )

            if created:
                logger.info(f"🆕 Nuevo chat creado: {chat.id}")

            return chat
        except Exception as e:
            logger.error(f"❌ Error al obtener/crear chat: {e}")
            return None

    @staticmethod
    def save_message(chat, sender, content):
        """Guarda un mensaje en la base de datos"""
        try:
            if chat:
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