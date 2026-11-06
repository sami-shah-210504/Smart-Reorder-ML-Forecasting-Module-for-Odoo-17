names = ['Alpha Supplies', 'Beta Wholesale', 'Gamma Trading']
partners = []
for n in names:
    partners.append(
        env['res.partner'].search([('name', '=', n)], limit=1)
        or env['res.partner'].create({'name': n, 'supplier_rank': 1}))

products = env['product.template'].search(
    [('sale_ok', '=', True), ('type', '=', 'product'), ('active', '=', True)],
    order='id', limit=20)

added = 0
for i, p in enumerate(products):
    if p.seller_ids:
        continue
    env['product.supplierinfo'].create({
        'partner_id': partners[i % 3].id,
        'product_tmpl_id': p.id,
        'price': max(p.standard_price, 1.0),
        'min_qty': 0,
        'delay': 7,
    })
    added += 1

env.cr.commit()
print('Added vendors to %d products' % added)
