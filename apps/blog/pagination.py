from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response
import math

class Pagination(PageNumberPagination):
    page_size = 10
    page_query_param = 'p'
    
    def get_paginated_response(self, data):
        total_items = self.page.paginator.count
        current_page = self.page.number
        per_page = self.page_size
        total_pages = math.ceil(total_items / per_page)
        
        return Response({
            'from': (current_page - 1) * per_page + 1,
            'to': min(current_page * per_page, total_items),
            'per_page': per_page,
            'current_page': current_page,
            'total_pages': total_pages,
            'total_items': total_items,
            'has_more_pages': current_page < total_pages,
            'next_page': current_page + 1 if current_page < total_pages else None,
            'prev_page': current_page - 1 if current_page > 1 else None,
            'results': data
        })