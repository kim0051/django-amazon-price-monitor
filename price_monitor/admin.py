from django.contrib import admin
from django.utils.translation import ugettext_lazy

from price_monitor.models import (
    Price,
    Product,
    Subscription,
)


class PriceAdmin(admin.ModelAdmin):
    list_display = ('date_seen', 'value', 'currency', )


class ProductAdmin(admin.ModelAdmin):
    list_display = ('asin', 'title', 'status', 'date_updated', 'date_last_synced', )

    actions = ['reset_to_created', ]

    def reset_to_created(self, request, queryset):
        queryset.update(status=0)
    reset_to_created.short_description = ugettext_lazy('Reset to status "Created".')


class SubscriptionAdmin(admin.ModelAdmin):
    list_display = ('product', 'price_limit', 'owner')


admin.site.register(Price, PriceAdmin)
admin.site.register(Product, ProductAdmin)
admin.site.register(Subscription, SubscriptionAdmin)
