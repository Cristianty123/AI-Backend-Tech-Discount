from django.contrib.auth.models import User
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework_simplejwt.tokens import RefreshToken
import logging

from .serializers import UserRegisterSerializer, UserLoginSerializer

logger = logging.getLogger(__name__)


@api_view(['POST'])
@permission_classes([AllowAny])
def register(request):
    """Registro de nuevo usuario"""
    try:
        serializer = UserRegisterSerializer(data=request.data)

        if serializer.is_valid():
            user = serializer.save()

            # Generar tokens JWT
            refresh = RefreshToken.for_user(user)

            logger.info(f"✅ Nuevo usuario registrado: {user.username}")

            return Response({
                'success': True,
                'message': 'Usuario registrado exitosamente',
                'user': {
                    'id': user.id,
                    'username': user.username,
                    'email': user.email
                },
                'tokens': {
                    'refresh': str(refresh),
                    'access': str(refresh.access_token),
                }
            }, status=status.HTTP_201_CREATED)

        return Response({
            'success': False,
            'error': 'Error en los datos de registro',
            'details': serializer.errors
        }, status=status.HTTP_400_BAD_REQUEST)

    except Exception as e:
        logger.error(f"❌ Error en registro: {str(e)}")
        return Response({
            'success': False,
            'error': 'Error interno del servidor'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([AllowAny])
def login_view(request):
    """Inicio de sesión de usuario"""
    try:
        serializer = UserLoginSerializer(data=request.data)

        if serializer.is_valid():
            username = serializer.validated_data['username']
            password = serializer.validated_data['password']

            # Autenticar usuario
            user = User.objects.filter(username=username).first()

            if user and user.check_password(password):
                # Generar tokens JWT
                refresh = RefreshToken.for_user(user)

                logger.info(f"✅ Usuario logueado: {user.username}")

                return Response({
                    'success': True,
                    'message': 'Inicio de sesión exitoso',
                    'user': {
                        'id': user.id,
                        'username': user.username,
                        'email': user.email
                    },
                    'tokens': {
                        'refresh': str(refresh),
                        'access': str(refresh.access_token),
                    }
                })
            else:
                return Response({
                    'success': False,
                    'error': 'Credenciales inválidas'
                }, status=status.HTTP_401_UNAUTHORIZED)

        return Response({
            'success': False,
            'error': 'Datos inválidos',
            'details': serializer.errors
        }, status=status.HTTP_400_BAD_REQUEST)

    except Exception as e:
        logger.error(f"❌ Error en login: {str(e)}")
        return Response({
            'success': False,
            'error': 'Error interno del servidor'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def logout_view(request):
    """Cierre de sesión"""
    try:
        logger.info(f"✅ Usuario cerró sesión: {request.user.username}")

        return Response({
            'success': True,
            'message': 'Sesión cerrada exitosamente'
        })

    except Exception as e:
        logger.error(f"❌ Error en logout: {str(e)}")
        return Response({
            'success': False,
            'error': 'Error al cerrar sesión'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def user_profile(request):
    """Obtener perfil del usuario actual"""
    try:
        user = request.user
        return Response({
            'success': True,
            'user': {
                'id': user.id,
                'username': user.username,
                'email': user.email,
                'date_joined': user.date_joined.strftime('%Y-%m-%dT%H:%M:%SZ')
            }
        })

    except Exception as e:
        logger.error(f"❌ Error al obtener perfil: {str(e)}")
        return Response({
            'success': False,
            'error': 'Error al obtener perfil'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
