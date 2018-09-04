# Copyright 2018 Mikel Arregi Etxaniz - AvanzOSC
# License AGPL-3 - See http://www.gnu.org/licenses/agpl-3.0.html
from odoo import api, fields, models, exceptions, _
from odoo.addons import decimal_precision as dp


class MrpProductionProductLine(models.Model):
    _name = 'mrp.production.product.line'
    _description = 'Production Scheduled Product'

    name = fields.Char(string='Name', required=True)
    product_id = fields.Many2one(
        comodel_name='product.product', string='Product', required=True)
    product_qty = fields.Float(
        string='Product Quantity',
        digits=dp.get_precision('Product Unit of Measure'), required=True)
    product_uom_id = fields.Many2one(
        comodel_name='product.uom', string='Unit of Measure', required=True)
    production_id = fields.Many2one(
        comodel_name='mrp.production', string='Production Order')
    bom_line_id = fields.Many2one(
        comodel_name='mrp.bom.line', string='Bom Line')


class MrpProduction(models.Model):
    _inherit = 'mrp.production'

    product_line_ids = fields.One2many(
        comodel_name='mrp.production.product.line',
        inverse_name='production_id', string='Scheduled goods')
    state = fields.Selection(selection_add=[('draft', 'Draft')],
                             default='draft')
    active = fields.Boolean(string='Active', default=False)

    def _generate_raw_moves(self):
        self.ensure_one()
        moves = self.env['stock.move']
        for line in self.product_line_ids:
            bom_line = line.bom_line_id
            quantity = line.product_qty
            if self.routing_id:
                routing = self.routing_id
            else:
                routing = self.bom_id.routing_id
            if routing and routing.location_id:
                source_location = routing.location_id
            else:
                source_location = self.location_src_id
            original_quantity = self.product_qty - self.qty_produced
            data = {
                'sequence': bom_line.sequence,
                'name': self.name,
                'date': self.date_planned_start,
                'date_expected': self.date_planned_start,
                'bom_line_id': bom_line.id,
                'product_id': line.product_id.id,
                'product_uom_qty': quantity,
                'product_uom': line.product_uom_id.id,
                'location_id': source_location.id,
                'location_dest_id':
                    self.product_id.property_stock_production.id,
                'raw_material_production_id': self.id,
                'company_id': self.company_id.id,
                'operation_id': bom_line.operation_id.id,
                'price_unit': line.product_id.standard_price,
                'procure_method': 'make_to_stock',
                'origin': self.name,
                'warehouse_id': source_location.get_warehouse().id,
                'group_id': self.procurement_group_id.id,
                'propagate': self.propagate,
                'unit_factor': quantity / original_quantity,
                'production_product_line_id': line.id,
            }
            moves += moves.create(data)
        return moves

    @api.multi
    def _generate_moves(self):
        """Avoid draft moves generation of draft state mo"""
        productions = self if self.env.context.get('generate_moves') else \
            self.filtered(lambda x: x.state != "draft")
        for production in productions:
            production._generate_finished_moves()
            production._generate_raw_moves()

    @api.multi
    def button_confirm(self):
        products = self.product_line_ids.mapped('product_id.id')
        if not all(products):
            raise exceptions.Warning(
                _('Not all scheduled products has a product'))
        orders_to_confirm = self.filtered(lambda order: order.state == 'draft')
        orders_to_confirm.write({'state': 'confirmed', 'active': 'True'})
        return self.with_context(generate_moves=True)._generate_moves()

    @api.multi
    def _action_compute_lines(self):
        """ Compute product_lines from BoM structure
        @return: product_lines
        """
        results = []
        prod_line_obj = self.env['mrp.production.product.line']
        for production in self:
            # unlink product_lines
            production.product_line_ids.sudo().unlink()
            res = production._prepare_lines()
            results = res  # product_lines
            # reset product_lines in production order
            for line in results:
                line_data = line[1]
                bom_line = line[0]
                product = bom_line.product_id
                prod_line = {
                    'name': product.name or bom_line.product_tmpl_id.name,
                    'product_id': product.id,
                    'product_qty': line_data['qty'],
                    'bom_line_id': bom_line.id,
                    'product_uom_id': bom_line.product_uom_id.id,
                    'production_id': production.id,
                }
                prod_line_obj.create(prod_line)
        return results

    @api.multi
    def _prepare_lines(self):
        # search BoM structure and route
        bom_obj = self.env['mrp.bom']
        bom_point = self.bom_id
        if not bom_point:
            bom_point = bom_obj._bom_find(product=self.product_id)
            if bom_point:
                routing_id = bom_point.routing_id.id or False
                self.write({
                    'bom_id': bom_point.id,
                    'routing_id': routing_id,
                })

        if not bom_point:
            raise exceptions.MissingError(
                _("Cannot find a bill of material for this product."))

        # get components from BoM structure
        factor = self.product_uom_id._compute_quantity(
            self.product_qty, bom_point.product_uom_id)
        boms_done, lines_done = bom_point.explode(
            self.product_id, factor / bom_point.product_qty)
        return lines_done

    @api.multi
    def action_compute(self):
        """ Computes bills of material of a product.
        @param properties: List containing dictionaries of properties.
        @return: No. of products.
        """
        return len(self._action_compute_lines())
