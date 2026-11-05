# Smart Reorder (Odoo 17)

An Odoo 17 module that forecasts weekly product demand from confirmed sales
history using a small ML service, and turns the forecasts into ranked reorder
suggestions for the purchasing team.

## Architecture

    Odoo module  --POST /v1/forecast-->  FastAPI service (ridge regression)
    (history, suggestions, UI, cron)  <--  weekly forecast + interval

## Setup

1. Start Odoo and Postgres:

       docker compose up -d

   Open http://localhost:8069 and create a database called `odoo_learning`
   with demo data. Install Sales, Inventory and Purchase.

2. Install the module: Apps -> Update Apps List -> Smart Reorder -> Install.

3. Seed 52 weeks of sample sales history (safe to re-run):

       docker compose exec -T odoo odoo shell -d odoo_learning \
         --db_host=db --db_user=odoo --db_password=odoo < scripts/seed_history.py

4. Start the ML service:

       cd ml_service
       python3 -m venv venv && source venv/bin/activate
       pip install -r requirements.txt
       python train.py
       uvicorn main:app --host 0.0.0.0 --port 8000

5. In Odoo: Smart Reorder -> Run Forecast.

## Usage

- Suggestions: ranked list of what to order, with stock snapshot
- Forecast Runs: audit trail of every run (manual or scheduled), with errors
- Weekly cron: runs automatically as the Administrator user
- Print: PDF summary from any completed run

## Settings

Set these under Settings -> Technical -> System Parameters:

| Key | Default | Meaning |
| --- | --- | --- |
| `smart_reorder.service_url` | `http://host.docker.internal:8000/v1/forecast` | ML service endpoint |
| `smart_reorder.lead_time_weeks` | 2 | Supplier lead time |
| `smart_reorder.safety_weeks` | 1 | Extra weeks of cover |

## Tests

    docker compose exec odoo odoo -d odoo_learning -u smart_reorder \
      --test-enable --test-tags /smart_reorder --stop-after-init \
      --db_host=db --db_user=odoo --db_password=odoo

## Known limitations

- Company-level lead time only, not per supplier
- Recursive multi-step forecasts accumulate error on longer horizons
- Products with under 8 full weeks of history are skipped
- The ML service is a single point of failure; failed runs are recorded
  and the last good forecast stays visible