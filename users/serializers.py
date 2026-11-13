from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from .models import Company, User

class CompanySerializer(serializers.ModelSerializer):
    class Meta:
        model = Company
        fields = [
            "id",
            "name",
            "email",
            "phone",
            "location",
            "logo",
            "created_at",
        ]

class LoginSerializer(TokenObtainPairSerializer):
    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)
        token["admin"] = "cck"
        return token
    
    def validate(self, attrs):
        data = super().validate(attrs)
        data["has_company"] = self.user.has_company
        return data
    
class UserSerializer(serializers.ModelSerializer):
    name = serializers.CharField(write_only=True, required=False, allow_blank=False)
    full_name = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = User
        fields = [
            "id",
            "email",
            "password",
            "has_company",
            "first_name",
            "last_name",
            "name",
            "full_name",
                ]
        read_only_fields = ["id", "has_company", "first_name", "last_name"]
        extra_kwargs = {"password": {"write_only": True}}

    def validate(self, attrs):
        name = attrs.pop("name", "").split()
        if name:
            attrs["first_name"] = name[0]
            attrs["last_name"] = " ".join(name[1:])
        return attrs

    def get_full_name(self, user):
        return user.get_full_name()

class UserDataSerializer (serializers.Serializer):
    user = UserSerializer()
    company = CompanySerializer()
