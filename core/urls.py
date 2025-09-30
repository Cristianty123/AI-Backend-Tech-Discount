from django.urls import path
from . import views

urlpatterns = [

    path('chat/nologin', views.chatWithChatbotWithoutLogin, name='chatWithChabotWithoutLogin'),

    path('chat/login', views.chatWithChatbotLoggedIn, name='chat-loggedin'),
    path('chats', views.getUserChats, name='user-chats'),
    path('chats/<uuid:chat_id>/messages/', views.getChatMessages, name='chat-messages'),

    path('api/chats/new/', views.create_new_chat, name='create-chat'),

    path('api/chats/<uuid:chat_id>/', views.delete_chat, name='delete-chat'),
]