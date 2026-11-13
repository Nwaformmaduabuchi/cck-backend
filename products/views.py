from django.shortcuts import render
from rest_framework.viewsets import GenericViewSet, ReadOnlyModelViewSet

from .models import Product, Variant
from .serialisers import CreateStockSerializer, ProductSerializer, VariantSerializer, VariantUpdateSerializer
from rest_framework.permissions import IsAuthenticated, AllowAny
from users.authentication import CustomJWTAuthentication
from .services import create_stock, delete_variant, updated_variant
from rest_framework.response import Response
from rest_framework import status
from users.permisions import HasCompany
from django.shortcuts import get_object_or_404


# Create your views here.

class CreateStockView(GenericViewSet):
    permission_classes = [IsAuthenticated, HasCompany]
    serializer_class = CreateStockSerializer
    
    def create(self, request, *args, **kwargs):
        
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        
        products = create_stock(validated_data=serializer.validated_data, company=request.user.company)
        output_serializer = ProductSerializer(products, many=True)
        
        return Response(output_serializer.data, status=status.HTTP_201_CREATED)

class ListVariantView(ReadOnlyModelViewSet):
    permission_classes = [IsAuthenticated, HasCompany]
    serializer_class = ProductSerializer
    
    def get_queryset(self):
        return Product.objects.filter(category__company=self.request.user.company).select_related('category').prefetch_related('variants')

    def retrieve(self, request, *args, **kwargs):
        variant = get_object_or_404(
            Variant.objects.select_related("product"),
            pk=kwargs["pk"],
            product__category__company=request.user.company,
        )
        return Response(VariantSerializer(variant).data)

    def destroy(self, request, *args, **kwargs):
        variant = get_object_or_404(
            Variant.objects.select_related("product"),
            pk=kwargs["pk"],
            product__category__company=request.user.company,
        )
        delete_variant(variant=variant)
        return Response(status=status.HTTP_204_NO_CONTENT)

class UpdateVariantView(GenericViewSet):
    permission_classes = [IsAuthenticated, HasCompany]
    serializer_class =  VariantUpdateSerializer
    
    def update(self, request, *args, **kwargs):
        id = self.kwargs.get('pk')
        try:
            variant = Variant.objects.get(id=id, product__category__company=request.user.company)
        except Variant.DoesNotExist:
            return Response({"detail": "Variant not found."}, status=status.HTTP_404_NOT_FOUND)
        serializer = self.get_serializer(
            variant,
            data=request.data,
            partial=True
        )
        serializer.is_valid(raise_exception=True)
        updated_variant(data=serializer.validated_data, instance=variant)        
        return Response({"detail": "Variant updated successfully."}, status=status.HTTP_200_OK)

    def partial_update(self, request, *args, **kwargs):
        return self.update(request, *args, **kwargs)

        
        
        
    
        
