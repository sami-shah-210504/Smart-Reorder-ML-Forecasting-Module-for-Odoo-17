import csv

run = env['smart.forecast.run'].create({})
payload = run._build_payload(run._eligible_products(), min_weeks=1)

with open('/tmp/history.csv', 'w', newline='') as f:
    w = csv.writer(f)
    w.writerow(['product_tmpl_id', 'week', 'qty'])
    for item in payload:
        for r in item['weekly_sales']:
            w.writerow([item['product_tmpl_id'], r['week'], r['qty']])

env.cr.rollback()
print('exported %d products' % len(payload))
