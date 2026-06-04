from croniter import croniter
from datetime import datetime

base = datetime(2024, 1, 1, 12, 0)
cron = croniter("*/4 * * * *", base)

print(cron.get_prev(datetime, update_current=False))
print(cron.get_current(datetime))
print(cron.get_next(datetime, update_current=False))
print()

cron = croniter("0 12 * * *", base)
print(cron.get_prev(datetime, update_current=True))
print(cron.get_prev(datetime, update_current=True))
print(cron.get_prev(datetime, update_current=True))
print(cron.get_current(datetime))
print(cron.get_next(datetime, update_current=True))
print(cron.get_next(datetime, update_current=True))
print(cron.get_next(datetime, update_current=True))
print(cron.get_next(datetime, update_current=True))
print()

cron = croniter("0 12 * * *", base)
print(cron.get_prev(datetime, update_current=False))
print(cron.get_current(datetime))
print(cron.get_next(datetime, update_current=False))
print()

cron = croniter("0 12 * * *", datetime.now())
print(cron.get_prev(datetime, update_current=False))
print(cron.get_prev(datetime, update_current=False))
print(cron.get_current(datetime))
print(cron.get_next(datetime, update_current=False))
print(cron.get_next(datetime, update_current=False))
print()

cron = croniter("0 12 * * *", datetime.now())
print(cron.get_next(datetime, update_current=True))
print(cron.get_next(datetime, update_current=True))
print()
