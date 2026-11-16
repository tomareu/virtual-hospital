from django.contrib import admin
from .models import DailyTokenUsage, RecordReport


@admin.register(RecordReport)
class RecordReportAdmin(admin.ModelAdmin):
    list_display = ('record', 'language', 'generated_by', 'generated_at')
    list_filter = ('language', 'generated_by')
    readonly_fields = ('generated_at',)


@admin.register(DailyTokenUsage)
class DailyTokenUsageAdmin(admin.ModelAdmin):
    list_display = ('day', 'tokens')
