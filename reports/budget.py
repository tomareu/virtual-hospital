from django.conf import settings
from django.db.models import F
from django.utils import timezone

from .models import DailyTokenUsage


class BudgetExhausted(Exception):
    pass


class TokenReservation:

    def __init__(self, amount):
        self.amount = amount
        self.used = 0
        self.day = None

    def __enter__(self):
        self.day = timezone.now().date()
        DailyTokenUsage.objects.get_or_create(day=self.day)
        reserved = DailyTokenUsage.objects.filter(
            day=self.day,
            tokens__lte=settings.AI_DAILY_TOKEN_BUDGET - self.amount,
        ).update(tokens=F('tokens') + self.amount)
        if not reserved:
            raise BudgetExhausted()
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        DailyTokenUsage.objects.filter(day=self.day).update(tokens=F('tokens') + self.used - self.amount)
