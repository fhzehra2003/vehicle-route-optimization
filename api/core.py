"""
API Core Module
==============
Contains views, serializers, and URLs for the Fuel Optimizer API.
"""

from django.urls import path
from django.views.decorators.csrf import csrf_exempt
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.generics import GenericAPIView


# ============================================================================
# Serializers
# ============================================================================

from rest_framework import serializers

class RouteRequestSerializer(serializers.Serializer):
    start = serializers.CharField(
        required=True,
        help_text="Starting location (e.g. 'New York, NY')"
    )
    end = serializers.CharField(
        required=True,
        help_text="Destination location (e.g. 'Chicago, IL')"
    )


# ============================================================================
# Views
# ============================================================================

class OptimizeRouteView(APIView):
    """
    Optimized Route Fuel Planning API
    """
    authentication_classes = []
    permission_classes = []

    def post(self, request):
        serializer = RouteRequestSerializer(data=request.data)

        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        start = serializer.validated_data['start']
        end = serializer.validated_data['end']

        try:
            # Import here to avoid circular imports
            from .services import get_route_coordinates, optimize_fuel_stops
            
            # Get route from OpenRouteService
            route_points = get_route_coordinates(start, end)

            # Run fuel optimization
            result = optimize_fuel_stops(start, end, route_points)

            return Response({
                "start": start,
                "end": end,
                "route_points": route_points[:100],
                "route_summary": result["route_summary"],
                "fuel_stops": result["fuel_stops"],
                "total_cost": result["total_cost"],
                "remaining_fuel_at_destination": result["remaining_fuel_at_destination"],
                "total_stops": len(result["fuel_stops"]),
                "message": "Route optimized successfully"
            }, status=status.HTTP_200_OK)

        except Exception as e:
            return Response({
                "error": str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
def test_api(request):
    return Response({"message": "API working"})


# ============================================================================
# URL Configuration
# ============================================================================

urlpatterns = [
    path('optimize-route/', OptimizeRouteView.as_view()),
    path('test/', test_api),
]
