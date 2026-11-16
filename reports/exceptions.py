from rest_framework import status
from rest_framework.exceptions import APIException


class TurnstileFailed(APIException):
    status_code = status.HTTP_403_FORBIDDEN
    default_detail = 'The human check failed. Please try again.'
    default_code = 'turnstile_failed'


class ReportBudgetExhausted(APIException):
    status_code = status.HTTP_429_TOO_MANY_REQUESTS
    default_detail = 'AI reports are resting until tomorrow.'
    default_code = 'report_budget_exhausted'


class ReportUnavailable(APIException):
    status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    default_detail = 'AI reports are unavailable right now.'
    default_code = 'report_unavailable'


class RecordIncomplete(APIException):
    status_code = status.HTTP_409_CONFLICT
    default_detail = 'Complete this consultation before downloading it.'
    default_code = 'record_incomplete'
