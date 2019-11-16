from frappe import _

def get_data():
	return {
		'heatmap': False,
		'heatmap_message': _('This is based on stock movement. See {0} for details')\
			.format('<a href="#query-report/Stock Ledger">' + _('Stock Ledger') + '</a>'),
		'fieldname': 'item_code',
		'non_standard_fieldnames': {
			'Stock Entry': 'custom_production_order',
			# 'Product Bundle': 'new_item_code',
			# 'BOM': 'item',
			# 'Batch': 'item'
		},
		'transactions': [
			{
				'label': _('Stock Entry'),
				'items': ['Stock Entry']
			},
		]
	}