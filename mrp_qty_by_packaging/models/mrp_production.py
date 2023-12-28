# Copyright 2023 Alfredo de la Fuente - AvanzOSC
# License AGPL-3 - See http://www.gnu.org/licenses/agpl-3.0.html
from odoo import api, fields, models
from odoo.tools import float_round


class MrpProduction(models.Model):
    _inherit = "mrp.production"

    product_packaging_id = fields.Many2one(
        string="Packaging",
        comodel_name="product.packaging",
        domain="[('sales', '=', True), ('product_id','=',product_id)]",
        check_company=True,
        copy=False,
    )
    product_packaging_qty = fields.Float(string="Packaging Quantity", copy=False)

    @api.onchange("product_packaging_id")
    def _onchange_product_packaging_id(self):
        if self.product_packaging_id:
            self.product_packaging_qty = 1
            self.product_qty = self.product_packaging_id.qty
        else:
            self.product_packaging_qty = 0
            self.product_qty = 1

    @api.onchange("product_packaging_qty")
    def _onchange_product_packaging_qty(self):
        if self.product_packaging_id and self.product_packaging_qty:
            self.product_qty = (
                self.product_packaging_qty * self.product_packaging_id.qty
            )

    @api.onchange("product_qty")
    def _onchange_product_qty(self):
        if self.product_packaging_id and self.product_uom_qty:
            packaging_uom = self.product_packaging_id.product_uom_id
            packaging_uom_qty = self.product_uom_id._compute_quantity(
                self.product_qty, packaging_uom
            )
            self.product_packaging_qty = float_round(
                packaging_uom_qty / self.product_packaging_id.qty,
                precision_rounding=packaging_uom.rounding,
            )