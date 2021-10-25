# Copyright 2023 Alfredo de la Fuente - AvanzOSC
# License AGPL-3 - See http://www.gnu.org/licenses/agpl-3.0.html
from odoo import models


class StockRule(models.Model):
    _inherit = "stock.rule"

    def _prepare_mo_vals(self, product_id, product_qty, product_uom,
                         location_dest_id, name, origin, company_id, values,
                         bom):
        mo_values = super(StockRule, self)._prepare_mo_vals(
            product_id, product_qty, product_uom, location_dest_id, name,
            origin, company_id, values, bom)
        if ("move_dest_ids" in values and
            len(values.get("move_dest_ids", [])) == 1 and
                values.get("move_dest_ids")[0].sale_line_id):
            move = values.get("move_dest_ids")[0]
            if move.sale_line_id.palet_id:
                mo_values["palet_id"] = move.sale_line_id.palet_id.id
            if move.sale_line_id.palet_qty:
                mo_values["palet_qty"] = move.sale_line_id.palet_qty
        return mo_values