import frappe

from erpnext.e_commerce.doctype.website_item.website_item import make_website_item


def execute():
	frappe.reload_doc("e_commerce", "doctype", "website_item")
	frappe.reload_doc("e_commerce", "doctype", "website_item_tabbed_section")
	frappe.reload_doc("e_commerce", "doctype", "website_offer")
	frappe.reload_doc("e_commerce", "doctype", "recommended_items")
	frappe.reload_doc("e_commerce", "doctype", "e_commerce_settings")
	frappe.reload_doc("stock", "doctype", "item")

	item_fields = ["item_code", "item_name", "item_group", "stock_uom", "brand", "image",
		"has_variants", "variant_of", "description", "weightage"]
	web_fields_to_map = ["route", "slideshow", "website_image_alt",
		"website_warehouse", "web_long_description", "website_content"]

	item_table_fields = frappe.db.sql("desc `tabItem`", as_dict=1)
	item_table_fields = [d.get('Field') for d in item_table_fields]

	# prepare fields to query from Item, check if the web field exists in Item master
	web_query_fields = []
	for web_field in web_fields_to_map:
		if web_field in item_table_fields:
			web_query_fields.append(web_field)
			item_fields.append(web_field)

	# check if the filter fields exist in Item master
	or_filters = {}
	for field in ["show_in_website", "show_variant_in_website"]:
		if field in item_table_fields:
			or_filters[field] = 1

	if not web_query_fields or not or_filters:
		# web fields to map are not present in Item master schema
		# most likely a fresh installation that doesnt need this patch
		return

	items = frappe.db.get_all(
		"Item",
		fields=item_fields,
		or_filters=or_filters
	)

	count = 0
	for item in items:
		if frappe.db.exists("Website Item", {"item_code": item.item_code}):
			# if website item already exists check for empty thumbnail
			web_item_doc = frappe.get_doc("Website Item", {"item_code": item.item_code})
			if web_item_doc.website_image and not web_item_doc.thumbnail:
				web_item_doc.make_thumbnail()
				web_item_doc.save()
		else:
			# else make new website item from item (publish item)
			website_item = make_website_item(item, save=False)
			website_item.ranking = item.get("weightage")
			for field in web_fields_to_map:
				website_item.update({field: item.get(field)})
			website_item.save()

			# move Website Item Group & Website Specification table to Website Item
			for doctype in ("Website Item Group", "Item Website Specification"):
				web_item, item_code = website_item.name, item.item_code
				frappe.db.sql(f"""
					Update
						`tab{doctype}`
					set
						parenttype = 'Website Item',
						parent = '{web_item}'
					where
						parenttype = 'Item'
						and parent = '{item_code}'
					""")

		count += 1
		if count % 20 == 0: # commit after every 20 items
			frappe.db.commit()