# Debugging: No Available Time Slots Issue

## Problem Summary
After configuring business hours with multiple time ranges per day, the appointment creation modal shows "Sin disponibilidad" (no availability) for all dates and times.

## Root Cause Analysis
The issue is likely NOT with the slot generation logic itself (which has been verified to work correctly). The issue is most likely in one of these areas:

1. **Data not being stored** - Business hours aren't being saved to the database
2. **Data not being retrieved** - Query doesn't find the saved business hours
3. **Tenant context mismatch** - Data saved with different tenant_id than what's being queried
4. **Migration not applied** - Migration 004 wasn't run, so the old unique constraint prevents multiple ranges

## Added Logging & Debugging

I've added comprehensive logging to the backend. To debug:

### Step 1: Start the Backend with Debug Logging

Set environment variables and run:
```bash
export LOG_LEVEL=DEBUG
python -m uvicorn src.main:app --reload --log-level debug
```

### Step 2: Monitor These Log Messages

The following log points have been added (search for these in the logs):

#### In SetBusinessHoursUseCase (saving hours):
```
upsert_many: Received X business hour records
upsert_many: Grouped into X day groups
upsert_many: Processing business_id=..., day_of_week=X with Y ranges
upsert_many: Deleted Z existing records for day X
upsert_many: Sorted items: [(open, close, is_closed), ...]
upsert_many: Inserting day X seq Y: HH:MM-HH:MM, is_closed=...
```

#### In BusinessHourRepository.get_by_business_and_day (retrieving hours):
```
get_by_business_and_day: business_id=..., day_of_week=X, tenant_id=...
get_by_business_and_day: Found X records
  - HH:MM-HH:MM, is_closed=...
```

#### In GetAvailableSlotsUseCase (slot generation):
```
Service found: ..., duration: 30 minutes
Looking for business hours for business_id=..., day_of_week=0, date=...
Found X business hour records
  - day 0: HH:MM-HH:MM, is_closed=...
Found X open ranges
Using timezone: UTC
Generating slots for ... with 30 minutes duration:
  Range: HH:MM-HH:MM -> ...
    Generated Y slots for this range
Total available slots: Z
```

### Step 3: Test the Flow

1. Configure business hours via the Settings page:
   - Set Monday: 09:00-12:00 and 14:00-18:00
   - Click Save

2. Check the logs for `upsert_many` messages:
   - Should show "Received 2 business hour records"
   - Should show "Inserting day 0 seq 1" and "Inserting day 0 seq 2"

3. Open the calendar and click "Nueva Cita" (New Appointment)

4. Select a service and date (e.g., next Monday)

5. Check the logs for `get_by_business_and_day` and slot generation messages:
   - Should show the retrieved hours
   - Should show the generated slots

## Common Issues & Solutions

### Issue 1: Logs don't show `upsert_many`

**Indicates**: The save request isn't reaching the backend, or there's an error before the repository is called.

**Debug steps**:
- Check if the "Horarios guardados correctamente" toast appears
- Check browser network tab to see if the PUT request to `/api/v1/businesses/{id}/hours` succeeds
- Check if there are any validation errors in the request body

### Issue 2: Logs show `upsert_many` but 0 deleted records

**Indicates**: Data was stored before, but migration 004 didn't run, or the unique constraint is preventing updates.

**Debug steps**:
- Check if migration 004 ran: `alembic history`
- If not, run migrations: `alembic upgrade head`
- Check PostgreSQL for conflicting records

### Issue 3: Logs show business hours retrieved but `Found 0 records`

**Indicates**: The query isn't matching the stored data. Possible causes:
- Tenant ID mismatch
- Day of week format mismatch
- Business ID doesn't match

**Debug steps**:
- Compare the business_id and tenant_id in logs between save and retrieve
- Check if they match exactly
- Check PostgreSQL directly:
  ```sql
  SELECT * FROM business_hours WHERE business_id = '...';
  ```

### Issue 4: Logs show hours retrieved but `Found 0 open ranges`

**Indicates**: All retrieved hours have `is_closed=true`.

**Debug steps**:
- Check the logs - what does `is_closed` show?
- If `is_closed=true`, the hours were stored incorrectly
- Check if there was an error during save that was silently ignored

### Issue 5: Logs show open ranges but `Total available slots: 0`

**Indicates**: Timezone or slot generation logic issue.

**Debug steps**:
- Check the timezone handling
- Verify the business timezone is set correctly
- Check if the ranges are being parsed correctly

## Manual Database Check

If you need to inspect the database directly:

```bash
# Connect to PostgreSQL
psql -h localhost -U postgres -d agente_citas_dev

# Check business hours
SELECT id, business_id, tenant_id, day_of_week, "sequence", open_at, close_at, is_closed
FROM business_hours
ORDER BY business_id, day_of_week, "sequence";

# Check if migration was applied
SELECT version FROM alembic_version ORDER BY version DESC LIMIT 5;
```

## What the Fix Should Look Like

Once the issue is identified, here are what the logs should look like for a successful flow:

### 1. Saving business hours (Monday 09:00-12:00 and 14:00-18:00):
```
upsert_many: Received 2 business hour records
upsert_many: Grouped into 1 day groups
upsert_many: Processing business_id=abc-123, day_of_week=0 with 2 ranges
upsert_many: Deleted 0 existing records for day 0
upsert_many: Sorted items: [(09:00, 12:00, False), (14:00, 18:00, False)]
upsert_many: Inserting day 0 seq 1: 09:00-12:00, is_closed=False
upsert_many: Inserting day 0 seq 2: 14:00-18:00, is_closed=False
upsert_many: Flush complete
```

### 2. Retrieving hours for Monday (day_of_week=0):
```
get_by_business_and_day: business_id=abc-123, day_of_week=0, tenant_id=xyz-789
get_by_business_and_day: Found 2 records
  - 09:00-12:00, is_closed=False
  - 14:00-18:00, is_closed=False
```

### 3. Generating slots:
```
Service found: 30 minutes
Found 2 business hour records
  - day 0: 09:00-12:00, is_closed=False
  - day 0: 14:00-18:00, is_closed=False
Found 2 open ranges
  Range: 09:00-12:00 -> 2026-05-19T09:00:00+00:00-2026-05-19T12:00:00+00:00
    Generated 11 slots for this range
  Range: 14:00-18:00 -> 2026-05-19T14:00:00+00:00-2026-05-19T18:00:00+00:00
    Generated 15 slots for this range
Total available slots: 26
```

## Next Steps

1. Run the backend with debug logging
2. Perform the configuration and appointment creation flow
3. Share the relevant log messages
4. Based on the logs, we can identify exactly where the issue is
