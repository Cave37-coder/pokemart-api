from django.core.management.base import BaseCommand

from orders import prep_time


class Command(BaseCommand):
    help = "Recalculate the order preparation time shown on the landing and checkout pages (run daily)."

    def handle(self, *args, **opts):
        est = prep_time.refresh()
        self.stdout.write(self.style.SUCCESS(
            f"Prep time {est.low_days}-{est.high_days} days "
            f"(source={est.source}, finished orders={est.sample_size}, "
            f"median={est.median_days}, p80={est.p80_days}, "
            f"open={est.open_orders}, oldest open={est.oldest_open_days}d)"))
