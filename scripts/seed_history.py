import math
import random
from datetime import date, datetime, timedelta

WEEKS = 52
N_PRODUCTS = 20
random.seed(42)

Order = env['sale.order']

# Wipe previous seed data so the script can be re-run safely
old = Order.search([('client_order_ref', '=', 'SEED')])
first_run = not old
if old:
    old.write({'state': 'draft'})
    old.unlink()

partner = env['res.partner'].search([('name', '=', 'Seed Customer')], limit=1) \
    or env['res.partner'].create({'name': 'Seed Customer'})

products = env['product.template'].search(
    [('sale_ok', '=', True), ('type', '=', 'product'), ('active', '=', True)],
    order='id', limit=N_PRODUCTS)

# One demand profile per product
profiles = {
    p.id: {
        'base': random.uniform(3, 40),
        'trend': random.uniform(-0.2, 0.5),   # change over the year
        'amp': random.uniform(0, 0.4),        # seasonality strength
        'phase': random.uniform(0, 2 * math.pi),
    }
    for p in products
}


def weekly_demand(prof, t):
    mu = prof['base'] * (1 + prof['trend'] * t / WEEKS) \
        * (1 + prof['amp'] * math.sin(2 * math.pi * t / 52 + prof['phase']))
    if random.random() < 0.05:                # occasional quiet week
        return 0
    return max(0, round(random.gauss(mu, math.sqrt(max(mu, 1)))))


monday = date.today() - timedelta(days=date.today().weekday())
created = Order
for t in range(WEEKS):
    week_start = monday - timedelta(weeks=WEEKS - t)
    lines = []
    for p in products:
        qty = weekly_demand(profiles[p.id], t)
        if qty > 0:
            lines.append((0, 0, {
                'product_id': p.product_variant_id.id,
                'product_uom_qty': qty,
            }))
    if not lines:
        continue
    order_date = datetime.combine(week_start + timedelta(days=2), datetime.min.time()).replace(hour=10)
    created |= Order.create({
        'partner_id': partner.id,
        'client_order_ref': 'SEED',
        'date_order': order_date,
        'order_line': lines,
    })

created.write({'state': 'sale'})

# Initial stock: between 0 and 4 weeks of average demand (first run only)
if first_run:
    warehouse = env['stock.warehouse'].search([('company_id', '=', env.company.id)], limit=1)
    for p in products:
        qty = round(profiles[p.id]['base'] * random.uniform(0, 4))
        if qty > 0:
            env['stock.quant']._update_available_quantity(
                p.product_variant_id, warehouse.lot_stock_id, qty)

env.cr.commit()
print("Seeded %d orders for %d products" % (len(created), len(products)))