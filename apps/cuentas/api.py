"""API mínima de autenticación. La web sigue usando sesiones de Django."""

from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import AnonRateThrottle
from rest_framework.views import APIView, exception_handler
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

_MENSAJES = {
    "Token is invalid or expired": "El token no es válido o ya expiró.",
    "Token is invalid": "El token no es válido o ya expiró.",
    "Given token not valid for any token type": "El token no es válido o ya expiró.",
    "Authentication credentials were not provided.": "Necesitas un token válido.",
    "Authorization header must contain two space-delimited values": "El encabezado de autorización no es válido.",
}


def _traducir(valor):
    texto = str(valor)
    if texto in _MENSAJES:
        return _MENSAJES[texto]
    if "throttled" in texto.lower():
        return "Has realizado demasiados intentos. Espera un momento e inténtalo de nuevo."
    return valor


def error_api(exc, context):
    respuesta = exception_handler(exc, context)
    if respuesta is None or not isinstance(respuesta.data, dict):
        return respuesta
    if "detail" in respuesta.data:
        respuesta.data["detail"] = _traducir(respuesta.data["detail"])
    mensajes = respuesta.data.get("messages")
    if isinstance(mensajes, list):
        for item in mensajes:
            if isinstance(item, dict) and "message" in item:
                item["message"] = _traducir(item["message"])
    return respuesta


class LimiteToken(AnonRateThrottle):
    scope = "token"


class TokenIngresoSerializer(TokenObtainPairSerializer):
    default_error_messages = {
        "no_active_account": "Correo, usuario o contraseña incorrectos.",
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["username"].error_messages["required"] = "Ingresa el correo o el usuario."
        self.fields["password"].error_messages["required"] = "Ingresa la contraseña."

    def validate(self, attrs):
        datos = super().validate(attrs)
        return {"access": datos["access"], "refresh": datos["refresh"]}


class TokenIngresoView(TokenObtainPairView):
    serializer_class = TokenIngresoSerializer
    throttle_classes = (LimiteToken,)


class TokenRenovarView(TokenRefreshView):
    throttle_classes = (LimiteToken,)


class CuentaApiView(APIView):
    permission_classes = (IsAuthenticated,)

    def get(self, request):
        usuario = request.user
        return Response(
            {
                "usuario": usuario.get_username(),
                "nombre": usuario.first_name,
                "apellido": usuario.last_name,
                "correo": usuario.email,
                "rol": usuario.rol,
            }
        )
