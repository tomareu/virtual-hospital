from rest_framework import status
from rest_framework.exceptions import APIException


class RecordAlreadyComplete(APIException):
    status_code = status.HTTP_409_CONFLICT
    default_detail = 'This consultation is already complete.'
    default_code = 'record_already_complete'
