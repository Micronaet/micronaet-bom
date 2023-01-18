#!/usr/bin/python
# -*- coding: utf-8 -*-
##############################################################################
#
#   Copyright (C) 2010-2012 Associazione OpenERP Italia
#   (<http://www.openerp-italia.org>).
#   Copyright(c)2008-2010 SIA "KN dati".(http://kndati.lv) All Rights Reserved.
#                   General contacts <info@kndati.lv>
#
#   This program is free software: you can redistribute it and/or modify
#   it under the terms of the GNU Affero General Public License as published by
#   the Free Software Foundation, either version 3 of the License, or
#   (at your option) any later version.
#
#   This program is distributed in the hope that it will be useful,
#   but WITHOUT ANY WARRANTY; without even the implied warranty of
#   MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#   GNU General Public License for more details.
#
#   You should have received a copy of the GNU Affero General Public License
#   along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
##############################################################################
import os
import sys
import logging
import erppeek
import pickle
import xlsxwriter
from openerp.osv import fields, osv, expression, orm
from datetime import datetime
from openerp.report import report_sxw
from openerp.report.report_sxw import rml_parse
from openerp.tools.translate import _
from openerp.tools import (DEFAULT_SERVER_DATE_FORMAT,
    DEFAULT_SERVER_DATETIME_FORMAT,
    DATETIME_FORMATS_MAP,
    float_compare)


_logger = logging.getLogger(__name__)


class MrpProduction(orm.Model):
    """ Model name: MrpProduction
    """
    _inherit = 'mrp.production'

    # Utility:
    def _get_all_product_in_bom(
            self, cr, uid, data=None,
            exclude_inventory_ids=None, context=None):
        """ Search product in bom line with particular category:
        """
        # TODO Write a parameter for print only in scheduled launch
        domain = [
            ('bom_id.bom_category', 'in', ('dynamic', 'half', 'parent')),
            ]

        # Remove product in excluded category:
        if exclude_inventory_ids is not None:
            domain.append((
                'bom_id.product_id.inventory_category_id', 'not in',
                exclude_inventory_ids))

        if data is not None:
            first_supplier_id = data.get('first_supplier_id')
            if first_supplier_id:
                domain.append(
                    ('product_id.recent_supplier_id', '=', first_supplier_id),
                    )
                # TODO use also manual supplier?
                # domain.extend([
                #    '|',
                #    ('product_id.recent_supplier_id', '=', first_supplier_id),
                #    ('product_id.first_supplier_id', '=', first_supplier_id),
                #    ])

        line_pool = self.pool.get('mrp.bom.line')
        line_ids = line_pool.search(cr, uid, domain, context=context)
        res = []
        for item in line_pool.browse(cr, uid, line_ids, context=context):
            if item.product_id.id not in res:
                res.append(item.product_id.id)
        return res

    # Moved here utility for call externally:
    def get_explode_report_object(self, cr, uid, data=None, context=None):
        """ Search all product elements
            data:
                mode: use (product), semi product, component for choose row
                elements

                # todo:
                period: period type week, month
                period: number of period for columns, max 12
        """

        def get_date():
            """ Get filter selected
            """
            return datetime.now().strftime(DEFAULT_SERVER_DATE_FORMAT)

        # ---------------------------------------------------------------------
        # Utility function embedded:
        # ---------------------------------------------------------------------
        def add_x_item(y_axis, item, category, purchase=None, mode='line'):
            """ Add new item to record
                y_axis: list of records
                item: bom browse obj
                mode:
                    'line' = item > sale order line
                    'product' = item > product
            """
            if mode == 'line':
                product = item.product_id
            else:  # 'product'
                product = item
            if purchase is None:
                purchase = {}

            default_code = product.default_code or ''
            if default_code in y_axis:
                return  # yet present (for component check)

            y_axis[default_code] = [  # half-worked of component
                # Reset counter for this product
                # 04/01/2017: change inventory with new
                product.mx_start_qty,
                # product.inventory_start + product.inventory_delta,
                # inv+delta

                0.0,  # t. car.
                0.0,  # t. scar.
                [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],  # MM  (+ extra per.)
                [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],  # OC  (+ extra per.)
                [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],  # OF  (+ extra per.)
                [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],  # SAL (+ extra per.)
                product,  # product or half-worked
                category,
                {},  # (HW that contain fabric) > fabric mode report
                # XXX No more used, not deleted for extra position:
                [0.0],  # Total for mt fabrics (fabric report)
                purchase.get(product.id, ''),
                product.inventory_category_id.name or '',
                ]
            return

        def get_position_season(date):
            """ Return position in array for correct season month:
            """
            if not date:
                _logger.error('Date not found')
                return False
            month = int(date[5:7])
            if month >= 9:  # september = 0
                return month - 9
            # january = 4
            return month + 3

        def write_xls_line(mode, line):
            """ Write line in correct WS with mode selection
            """
            row = self.counter[mode]

            col = 0
            for item in line:
                self.WS[mode].write(row, col, item)
                col += 1

            self.counter[mode] += 1  # row update
            return

        def write_xls_line_list(mode, line):
            """ Write line every item in new row
            """
            row = self.counter[mode]

            col = 0
            for item in line:
                self.WS[mode].write(row, col, item)
                self.counter[mode] += 1  # row update
            return

        def has_mandatory_placeholder(default_code, product_id):
            """ Check if the product: default_code has a component that is
                mandatory (placeholder set and rule if present)
            """
            if not product_id.bom_placeholder:
                return False
            if product_id.bom_placeholder_rule:
                return eval(product_id.bom_placeholder_rule)
            return True  # Mandatory if not rule

        def update_hw_data_line(data, product, remain, mt, hw_purchased):
            """ Update data line for remain hw line
                data: xls line list (record for component)
                product: browse of current half worked
                remain: OC remain to deliver / produce
                mt: q. from BOM
                hw_purchased: purchesed available hw
            """
            hw_fabric = data[9]
            # No more used (calculated during report):
            # total = data[10] # list of one element (save total mt usable)
            hw_code = product.default_code
            if hw_code not in hw_fabric:
                # -------------------------------------------------------------
                # Create empty record with fixed data:
                # -------------------------------------------------------------
                # Available = purchased + stock - locked
                available_qty = (
                    hw_purchased.get(hw_code, 0.0) + product.mx_net_mrp_qty -
                    product.mx_mrp_b_locked)
                hw_fabric[hw_code] = [
                    # 0. Stock - MRP - assigned (Before was: mx_net_qty)
                    available_qty if available_qty else 0.0,
                    0.0,  # 1. OC remain HW
                    0.0,  # 2. Stock Component (mt  of fabric)
                    # mt, # 3. Mt. from BOM
                    ]
            current = hw_fabric[hw_code]  # readability
            current[1] += remain  # OC total
            # XXX better once when end totalization remain

            # Test: OC >= Stock:
            if current[1] >= current[0]:  # Use all stock (OC >= stock)
                current[2] = current[0] * mt  # All stock raw material
            else:  # use all OC (extra stock not usable)
                current[2] = current[1] * mt  # All ordered raw material
                # total[0] += stock_mt
            return True

        # ---------------------------------------------------------------------
        # Start procedure:
        # ---------------------------------------------------------------------
        if context is None:
            context = {}

        if data is None:
            data = {}

        # Add status for calc. HW only (filter)?
        user_pool = self.pool.get('res.users')
        previous_status = user_pool.set_no_inventory_status(
            cr, uid, value=False, context=context)

        # Read wizard parameters:
        mode = data.get('mode', 'halfwork')
        mp_mode = data.get('mp_mode', False)
        first_supplier_id = data.get('first_supplier_id', False)
        with_type_ids = data.get('with_type_ids', [])
        without_type_ids = data.get('without_type_ids', [])
        only_negative = data.get('only_negative', False)
        exclude_inventory_category = data.get(
            'exclude_inventory_category', False)

        # ---------------------------------------------------------------------
        # Exclude marked "no report" inventory category:
        # ---------------------------------------------------------------------
        if exclude_inventory_category:
            # TODO load exclude category:
            inventory_pool = self.pool.get(
                'product.product.inventory.category')
            exclude_inventory_ids = inventory_pool.search(cr, uid, [
                ('not_in_report', '=', True),
                ], context=context)
            _logger.warning('Excluded [%s] inventory category' % (
                exclude_inventory_ids, ))
        else:
            exclude_inventory_ids = []

        # Add inventory check block:
        for_inventory_delta = data.get('for_inventory_delta', False)
        inventory_delta = {}

        # Add HW line part for purchased:
        hw_purchased = {}

        # ---------------------------------------------------------------------
        # XLS Log file:
        # ---------------------------------------------------------------------
        now = '%s' % datetime.now()
        xls_log = '/home/administrator/photo/log/report_explode_%s_%s.xlsx' % (
            mode,
            now.replace('/', '_').replace(':', '.'),
            )
        # Save in context if if will be used after:
        context['component_logfile'] = xls_log

        _logger.warning('Log file: %s' % xls_log)
        WB = xlsxwriter.Workbook(xls_log)

        # Work Sheet:
        self.WS = {
            'move': WB.add_worksheet('Movimenti'),
            'extra': WB.add_worksheet('Extra'),
            'purchase': WB.add_worksheet('Semilavorati acquistati'),
            'selection': WB.add_worksheet('Selezione'),
            }

        # Row counters:
        self.counter = {
            'move': 0,
            'extra': 0,
            'purchase': 0,
            'selection': 0,
            }

        # A. Write Header line:
        write_xls_line('move', (
            'Blocco', 'Stato', 'Documento', 'Origine', 'Data', 'Posizione',
            'Prodotto', 'Mat. prima', 'Calcolo', 'MM', 'OC', 'OF',
            'Note', 'Categoria'
            ))
        # B. no extra page header
        # C. Write extra part for HW purchased:
        write_xls_line('purchase', (
            'Codice', 'Q', 'Rif.',
            ))
        # D. Selezione documentale
        write_xls_line('selection', (
            'Modo', 'Riferimento',
            ))

        # pool used:
        company_pool = self.pool.get('res.company')  # for utility
        product_pool = self.pool.get('product.product')
        pick_pool = self.pool.get('stock.picking')
        sale_pool = self.pool.get('sale.order')
        move_pool = self.pool.get('stock.move')
        mrp_pool = self.pool.get('mrp.production')

        # Load Y axis for report (half-work or component):
        y_axis = {}
        category_fabric = _('Fabric')

        # Get purchase information:
        _logger.info('Start get purchase information (date)')
        purchase_db = move_pool._get_purchase_product_last_date(
            cr, uid, context=context)

        # ADD all fabrics in axis before all check:
        if mp_mode == 'fabric':  # fabric
            fabric_list = (
                'T3D', 'TES', 'TEX', 'TGT', 'TIO', 'TJO', 'TSK', 'TSQ', 'TWH',
                'TWL', 'TWM', 'TXM', 'TXI', 'TXR',
                )
            # Log selection:
            write_xls_line('selection', ['Codici tessuto'])
            write_xls_line_list('selection', fabric_list)

            # todo add also not_in_report check!!!  and not_in_report='f'
            query = '''
                SELECT id from product_product
                WHERE substring(default_code, 1, 3) IN ('%s');
                ''' % "','".join(fabric_list)

            cr.execute(query)
            fabric_ids = [item[0] for item in cr.fetchall()]
            fabrics = product_pool.browse(
                    cr, uid, fabric_ids, context=context)

            # Log selection:
            write_xls_line('selection', ['Elenco tessuti'])
            write_xls_line_list('selection', [f.default_code for f in fabrics])

            for fabric in fabrics:
                add_x_item(
                    y_axis, fabric, category_fabric,
                    purchase_db, mode='product',
                    )

        # Get product BOM dynamic lines (from active order):
        product_data = sale_pool.get_component_in_product_order_open(
            cr, uid, context=context)
        product_proxy = product_data['product']

        # TODO manage all product for particular category?
        # SO: filter product in category instead of ordered product

        # Maybe removed:
        inventory_pos = get_position_season(get_date())  # for inventory mgmt.
        for product in product_proxy:  # XXX Product ordered for now
            for item in product.dynamic_bom_line_ids:  # XXX All Semi-worked:
                # todo Remove log:

                # Remove placeholder elements:
                if item.product_id.bom_placeholder or \
                        item.product_id.bom_alternative:
                    _logger.warning('Placeholder product jumped: %s' %
                                    item.product_id.default_code)
                    continue

                # -------------------------------------------------------------
                # Filter:
                # -------------------------------------------------------------
                # NOTE: Filter category always in hw not component!
                if with_type_ids and \
                        item.category_id.type_id.id not in with_type_ids:
                    continue  # Jump not in category selected
                if without_type_ids and \
                        item.category_id.type_id.id in without_type_ids:
                    continue  # Jump not in category selected
                if exclude_inventory_ids and \
                        item.product_id.inventory_category_id.id\
                        in exclude_inventory_ids:
                    _logger.warning('Product category not in report')
                    continue  # Jump BOM element in excluded category

                # in half-work use only hw component:
                half_bom_ids = item.product_id.half_bom_ids
                if mode == 'halfwork' and half_bom_ids:  # hw with component
                    # 10/01/2018 change first with recent
                    if first_supplier_id and first_supplier_id != \
                                item.product_id.recent_supplier_id.id:
                        continue  # Jump not supplier present

                    category = item.category_id.type_id.name if \
                        item.category_id and item.category_id.type_id else \
                        _('No category')
                    add_x_item(y_axis, item, category, purchase_db)
                elif mode == 'component' and not half_bom_ids:  # comp. in BOM
                    # 10/01/2018 restore supplier filter on recent_supplier_id
                    if first_supplier_id and first_supplier_id != \
                                item.product_id.recent_supplier_id.id:
                        continue  # Jump not supplier present

                    if mp_mode == 'fabric' and item.product_id.id not in \
                            fabric_ids:  # jump not fabric
                        continue
                    category = item.category_id.type_id.name if \
                        item.category_id and item.category_id.type_id else \
                        _('No category')
                    # todo write category as component mode (pipe / fabric)
                    add_x_item(y_axis, item, category, purchase_db)
                elif mode == 'component':  # >>> component HW and component BOM
                    # TODO log half-component with empty list
                    # relative_type = 'half'
                    for component in half_bom_ids:
                        # 10/01/2018 supplier filter on recent_supplier_id
                        if first_supplier_id and first_supplier_id != \
                                    item.product_id.recent_supplier_id.id:
                            continue  # Jump not supplier present

                        if mp_mode == 'fabric' and component.product_id.id \
                                not in fabric_ids:
                            continue

                        if exclude_inventory_ids and \
                                component.product_id.inventory_category_id.id \
                                in exclude_inventory_ids:
                            continue  # Jump BOM element in excluded category

                        # Create ad hoc category:
                        if component.product_id.is_pipe:
                            category = _('Pipes')
                        else:
                            category = _('Fabric (or extra)')
                        add_x_item(y_axis, component, category, purchase_db)
                else:
                    # no above cases
                    continue

        write_xls_line('extra', ('Component / Halfworked selected:', ))
        for code in y_axis.keys():
            write_xls_line('extra', (code, ))

        # =====================================================================
        # Get parameters for search:
        # =====================================================================
        company_ids = company_pool.search(cr, uid, [])
        company_proxy = company_pool.browse(cr, uid, company_ids)[0]

        # Exclude partner list:
        exclude_partner_ids = []

        # Append also this company partner for inventory that need to be excl.
        # todo check if is correct the remove of company:
        exclude_partner_ids.append(company_proxy.partner_id.id)

        # From date:
        # Period range for documents
        month = datetime.now().month
        year = datetime.now().year
        if month >= 9:
            # Not work!:
            # period_from = '2021-09-01'  # todo when no inventory
            period_from = '%s-09-01' % year  # todo when inventory
            period_to = '%s-08-31' % (year + 1)
        else:
            period_from = '%s-09-01' % (year - 1)  # for OC and OF
            period_to = '%s-08-31' % year

        write_xls_line('extra', (
            'Exclude partner list: %s' % (exclude_partner_ids, ),
            ))

        # =====================================================================
        # 1. LOAD PICKING (CUSTOMER ORDER AND PICK IN)
        # =====================================================================
        block = 'OF, BF, CL, CL prod., CL lav., CL inv.'
        # Keep exclude_partner_ids for CL production exclusion?
        # XXX Note: first for creation of new elements if not present in OC

        in_picking_type_ids = []

        # Use textilene company page:
        for item in company_proxy.stock_report_tx_load_in_ids:
            in_picking_type_ids.append(item.id)

        pick_ids = pick_pool.search(cr, uid, [
            ('picking_type_id', 'in', in_picking_type_ids),
            ('partner_id', 'not in', exclude_partner_ids),
            # check data date (old method
            # ('date', '>=', from_date), # XXX correct for virtual?
            # ('date', '<=', to_date),
            # todo state filter
            ])
        load_picks = pick_pool.browse(cr, uid, pick_ids, context=context)

        # Log selection:
        write_xls_line('selection', ['Documenti Carico'])
        write_xls_line_list('selection', [p.name for p in load_picks])

        for pick in load_picks:
            pos = get_position_season(pick.date)  # for done cols  (min_date?)
            for line in pick.move_lines:
                default_code = line.product_id.default_code
                qty = line.product_uom_qty
                date_expected = line.date_expected

                # -------------------------------------------------------------
                # HW bought part (use this loop) >> use for material check
                # -------------------------------------------------------------
                if (line.product_id.ordered_hw and line.state == 'assigned'
                        and period_from < date_expected < period_to):
                    if default_code in hw_purchased:
                        hw_purchased[default_code] += qty
                    else:
                        hw_purchased[default_code] = qty
                    write_xls_line('purchase', (
                        default_code, qty,
                        '%s (%s) il %s' % (
                            pick.name, pick.origin, date_expected),
                    ))

                # Use only product present in y_axis:
                if default_code not in y_axis:
                    write_xls_line('move', (
                        block, 'NOT USED', pick.name, pick.origin, pick.date,
                        pos, '',  # product_code
                        default_code, '', 0, 0, 0,
                        'OF / BF WARNING CODE NOT IN SELECTED LIST (X)',
                        ''
                        ))
                    continue

                # -------------------------------------------------------------
                #          OF document
                # -------------------------------------------------------------
                # Order not current delivered:
                if line.state == 'assigned':  # virtual
                    # USE deadline data in the period:
                    if date_expected > period_to or \
                            date_expected < period_from:  # extra range
                        write_xls_line('move', (
                            block, 'NOT USED', pick.name, pick.origin,
                            date_expected, '',  # POS
                            '',  # product_code
                            default_code, '', 0, 0, 0,
                            'OF date expected extra range!: Q.: %s' % qty,
                            ''
                            ))
                        continue

                    pos = get_position_season(date_expected)
                    y_axis[default_code][5][pos] += qty  # OF block
                    write_xls_line('move', (
                        block, 'USED', pick.name, pick.origin,
                        date_expected, pos, '',  # product_code
                        default_code, '', 0, 0, qty, 'OF',
                        ''
                        ))
                    continue

                # -------------------------------------------------------------
                #                         BF document
                # -------------------------------------------------------------
                # Order delivered so picking in movement
                elif line.state == 'done':
                    date = pick.date or pick.date_done or pick.min_date
                    # 28 gen. 2017 data is now first, after is the last!
                    pos = get_position_season(date)

                    # USE order data:
                    # Change for jump year 04/01/2017 (for year change 1/1)
                    # if date > period_to or date < period_from:  # extra range
                    # XXX no more mm_from use with period: [01/09-31/08]
                    # Extra range:
                    if (date < period_from) or (date > period_to):
                        write_xls_line('move', (
                            block, 'NOT USED', pick.name, pick.origin,
                            date, pos, '',  # product_code
                            default_code, '', 0, 0, 0,
                            'BF date doc extra range!!: Q.: %s' % qty,
                            ''
                            ))
                        continue

                    y_axis[default_code][3][pos] += qty  # MM block
                    y_axis[default_code][1] += qty  # TCAR
                    write_xls_line('move', (
                        block, 'USED', pick.name, pick.origin, date,
                        pos, '',  # product_code
                        default_code, '', qty,  # +MM
                        0, 0, 'BF ADD IN TCAR',
                        ''
                        ))
                    continue

        # =====================================================================
        # UNLOAD PICKING (CUSTOMER ORDER PICK OUT) DIRECT SALE OF COMPONENT
        # =====================================================================
        # TODO manage inventory_id > stock.inventory for manual correction
        block = 'BC PICK OUT'  # Direct sale of half-processed
        # XXX Note: no unload MM during BC (only production)

        out_picking_type_ids = []
        for item in company_proxy.stock_report_tx_load_out_ids:
            out_picking_type_ids.append(item.id)

        pick_ids = pick_pool.search(cr, uid, [
            ('picking_type_id', 'in', out_picking_type_ids),
            ('partner_id', 'not in', exclude_partner_ids),  # current company

            # Only in period # TODO remove if check extra data
            # XXX OLD: 04/01/2017 Changed for clean before 1/1
            # XXX no more use with period: [01/09-31/08]
            ('date', '>=', period_from),  # XXX 01/09
            ('date', '<=', period_to),
            ])
        unload_picks = pick_pool.browse(cr, uid, pick_ids)

        # Log selection:
        write_xls_line('selection', ['Documenti Scarico'])
        write_xls_line_list('selection', [p.name for p in unload_picks])

        for pick in unload_picks:
            pos = get_position_season(pick.date)  # cols  (min_date?)
            # todo no check for period range
            for line in pick.move_lines:
                product_code = line.product_id.default_code
                product = line.product_id
                if line.state != 'done':
                    write_xls_line('move', (
                        block, 'NOT USED', pick.name, pick.origin, pick.date,
                        pos, product_code, '', '', 0, 0, 0,
                        'BC MOVE State not in done (jumped)',
                        ''
                        ))
                    continue

                # check direct sale:
                if product_code in y_axis:  # Component direct:
                    qty = line.product_uom_qty  # for direct sale
                    y_axis[product_code][3][pos] -= qty  # MM block
                    y_axis[product_code][2] -= qty  # T. SCAR.
                    write_xls_line('move', (
                        block, 'USED', pick.name, pick.origin,
                        pick.date, pos, '', product_code,  # Prod is MP
                        '', -qty,  # MM
                        0, 0,
                        'BC MOVE Direct sale of component (ADD IN TSCAR)',
                        ''
                        ))
                    continue

        # =====================================================================
        #                 CUSTOMER ORDER TO PRODUCE (NOT DELIVERED)
        # =====================================================================
        block = 'OC (not delivered)'
        # XXX Note: used only for manage OC remain:
        #    OC - B if B > Del.
        #    OC - Del if B < Del.

        order_ids = company_pool.mrp_domain_sale_order_line(
            cr, uid, context=context)
        orders = sale_pool.browse(cr, uid, order_ids, context=context)

        # Log selection:
        write_xls_line('selection', ['Documenti Ordine'])
        write_xls_line_list('selection', [oc.name for oc in orders])

        for order in orders:
            # Search in order line:
            for line in order.order_line:
                # FC order no deadline (use date)
                # datetime.now().strftime(DEFAULT_SERVER_DATE_FORMAT))
                product = line.product_id  # readability
                product_code = line.product_id.default_code
                date = line.date_deadline or order.date_order
                pos = get_position_season(date)

                # OC exclude no parcels product:
                if product.exclude_parcels:
                    write_xls_line('move', (
                        block, 'NOT USED', order.name, '', date, pos, '',
                        product_code,  # Direct component
                        '', 0,  # +MM
                        0,  # XXX keep 0 (-OC)
                        0, 'OC NO PARCELS PRODUCT',
                        ''
                        ))
                    continue

                (remain, not_delivered) = \
                    company_pool.mrp_order_line_to_produce_assigned(line)
                # company_pool.mrp_order_line_to_produce(line)

                # --------------------------------
                # OC direct half-work or component:
                # --------------------------------
                # Explode HW subcomponent for report 2
                if mode != 'halfwork':  # only for component
                    for comp in product.half_bom_ids:
                        comp_code = comp.product_id.default_code
                        if comp_code not in y_axis:  # OC out item (no prod.):
                            # TODO log component not used
                            continue

                        comp_remain = remain * comp.product_qty
                        y_axis[comp_code][4][pos] -= comp_remain  # OC
                        write_xls_line('move', (
                            block, 'USED', order.name, '', date, pos,
                            product_code,  # Code
                            comp_code,  # component
                            '', 0,  # +MM
                            comp_remain,  # -OC
                            0, 'OC DIRECT SALE HW SO COMPONENT UNLOAD',
                            comp.category_id.name if comp.category_id else \
                            'NO CATEGORY',
                            ))

                        # Add extra part for keep HW in fabric report:
                        # Update extra line for fabric HW use:
                        # 19 feb 2019 use also for component:
                        # if mp_mode == 'fabric':
                        update_hw_data_line(
                            y_axis[comp_code],
                            product, remain, comp.product_qty,
                            hw_purchased)
                        # go ahead for download component

                # Direct sale hw or component:
                if product_code in y_axis:  # HW or component direct:
                    y_axis[product_code][4][pos] -= remain  # OC block
                    write_xls_line('move', (
                        block, 'USED', order.name, '', date, pos, '',  # code
                        product_code,  # Direct component
                        '', 0,  # +MM
                        remain,  # -OC
                        0, 'OC DIRECT SALE HALFWORK OR COMPONENT',
                        ''
                        ))
                    continue

                # No bom for this product:
                if not len(product.dynamic_bom_line_ids):
                    write_xls_line('move', (
                        block, 'NOT USED', order.name, '', date, pos,
                        product_code, '',  # Original product
                        '', 0,  # +MM
                        0,  # -OC
                        0, 'OC PRODUCT WITHOUT BOM, Q.: %s' % remain,
                        ''
                        ))
                    continue

                # TODO error for negative?
                if remain <= 0:
                    write_xls_line('move', (
                        block, 'NOT USED', order.name, '', date, pos,
                        product_code, '',  # MP
                        '', 0,  # +MM
                        0, 0, 'OC ALL DELIVERED OR NEGATIVE DELIVER',
                        ''
                        ))
                    continue

                # USE order data:
                # Note: Remain period_from instead of mm_from exclude extra
                # period order always 1/9
                if date < period_from or date > period_to:  # extra range
                    write_xls_line('move', (
                        block, 'NOT USED', order.name, '', date, pos,
                        product_code, '',  # MP
                        '', 0,  # +MM
                        0, 0, 'OC EXTRA RANGE, qty: %s' % remain,
                        ''
                        ))
                    continue

                # ------------------------------------
                # OC Half-worked or Component explode:
                # ------------------------------------
                for item in product.dynamic_bom_line_ids:
                    item_code = item.product_id.default_code
                    item_remain = remain * item.product_qty

                    half_bom_ids = item.product_id.half_bom_ids
                    if mode == 'halfwork' and half_bom_ids:  # hw with comp.
                        if item_code in y_axis:  # OC out item (no prod.):
                            y_axis[item_code][4][pos] -= item_remain  # OC blk
                            write_xls_line('move', (
                                block, 'USED', order.name, '', date, pos,
                                product_code,  # code
                                item_code,  # MP
                                '', 0,  # +MM
                                item_remain,  # -OC
                                0, 'OC HALFWORKED REMAIN (HW)',
                                item.category_id.name if item.category_id \
                                    else 'NO CATEGORY',
                                ))
                        # else: TODO log not used

                    elif mode == 'component' and not half_bom_ids:  # cmpt BOM
                        if item_code in y_axis:  # OC out item (no prod.):
                            y_axis[item_code][4][pos] -= item_remain  # OC blk
                            write_xls_line('move', (
                                block, 'USED', order.name, '', date, pos,
                                product_code,  # code
                                item_code,  # MP
                                '', 0,  # +MM
                                item_remain,  # -OC
                                0, 'OC HALFWORKED REMAIN (HW-0)',
                                item.category_id.name if item.category_id \
                                    else 'NO CATEGORY',
                                ))

                    elif mode == 'component':
                        for comp in item.product_id.half_bom_ids:
                            comp_code = comp.product_id.default_code
                            comp_remain = item_remain * comp.product_qty

                            # OC out item (no prod.):
                            if comp_code not in y_axis:
                                write_xls_line('move', (
                                    block, 'NOT USED', order.name, '', date,
                                    pos, item_code,  # Code
                                    comp_code,  # component
                                    '', 0,  # +MM
                                    comp_remain,  # -OC
                                    0, 'COMPONENT NOT IN FILTER X LIST (CMPT)',
                                    comp.category_id.name if comp.category_id\
                                    else 'NO CATEGORY',
                                    ))
                                continue

                            y_axis[comp_code][4][pos] -= comp_remain  # OC
                            write_xls_line('move', (
                                block, 'USED', order.name, '', date, pos,
                                item_code,  # Code
                                comp_code,  # component
                                '', 0,  # +MM
                                comp_remain,  # -OC
                                0, 'OC COMPONENT REMAIN',
                                comp.category_id.name if comp.category_id
                                else 'NO CATEGORY',
                                ))

                            # Update extra line for fabric HW use:
                            # 19 feb 2019 use also for component:
                            # if mp_mode == 'fabric':
                            update_hw_data_line(
                                y_axis[comp_code],
                                item.product_id,  # HW reference
                                item_remain,  # HW remain
                                comp.product_qty,  # Component remain
                                hw_purchased,  # Purchased HW
                                )
                        continue  # needed?
                    else:
                        continue  # no case jump

        # =====================================================================
        #                  UNLOAD FOR PRODUCTION MRP ORDER
        # =====================================================================
        block = 'MRP (unload component prod.)'
        # XXX Note: used only for manage OC remain:

        # if mode == 'halfwork':  # only half explode MRP (comp > lavoration)
        mrp_ids = mrp_pool.search(cr, uid, [
            # State filter:
            ('state', '!=', 'cancel'),  # TODO correct? for unload element?

            # Period filter:
            # XXX OLD: 04/01/2017 MRP from 1/9 or 1/1 depend on change year
            # XXX no more use with period: [01/09-31/08]
            ('date_planned', '>=', period_from),  # 1/9 or 1/1
            ('date_planned', '<=', period_to),

            # No customer exclude filter
            ])
        mrps = mrp_pool.browse(cr, uid, mrp_ids, context=context)

        # Log selection:
        write_xls_line('selection', ['Documenti MRP'])
        write_xls_line_list('selection', [m.name for m in mrps])

        for order in mrps:
            date = order.date_planned

            # Search in order line:
            for line in order.order_line_ids:
                product = line.product_id  # readability
                product_code = line.product_id.default_code
                pos = get_position_season(date)
                qty = line.product_uom_maked_sync_qty

                # XXX No direct production (use job. CL / CL for this):

                if not len(product.dynamic_bom_line_ids):  # no bom
                    write_xls_line('move', (
                        block, 'NOT USED', order.name, '', date, pos,
                        product_code, '',  # Original product
                        '', 0,  # +MM
                        0,  # -OC
                        0, 'MRP PRODUCT WITHOUT BOM, Q.: %s' % qty,
                        '',
                        ))
                    continue

                # --------------------
                # Search in component:
                # --------------------
                for comp in product.dynamic_bom_line_ids:
                    comp_code = comp.product_id.default_code
                    comp_qty = qty * comp.product_qty

                    # Check placehoder:
                    if has_mandatory_placeholder(
                            product_code, comp.product_id):  # bom_alternative?
                        write_xls_line('move', (
                            block, 'NOT USED', order.name, '', date,
                            pos, product_code,
                            comp_code,  # MP
                            '', -comp_qty,
                            0, 0, 'MRP PRESENTE UN [DA ASSEGNARE]',
                            comp.category_id.name if comp.category_id\
                                 else 'NO CATEGORY',
                            ))
                        continue

                    if comp_code in y_axis:  # OC out component (no prod.):
                        y_axis[comp_code][3][pos] -= comp_qty  # MM block
                        y_axis[comp_code][2] -= comp_qty  # TSCAR for MRP
                        write_xls_line('move', (
                            block, 'USED', order.name, '', date, pos,
                            product_code,
                            comp_code,  # MP
                            '', -comp_qty,  # -MM
                            0, 0, 'MRP COMPONENT UNLOAD (ADD in TSCAR)',
                            comp.category_id.name if comp.category_id else \
                            'NO CATEGORY',
                            ))
                        continue
                    else:
                        write_xls_line('move', (
                            block, 'NOT USED', order.name, '', date, pos,
                            product_code,
                            comp_code,  # MP
                            '', -comp_qty,  # -MM
                            0, 0, 'MRP COMPONENT NOT IN LIST',
                            comp.category_id.name if comp.category_id \
                            else 'NO CATEGORY',
                            ))
                        continue

        # ---------------------------------------------------------------------
        # Prepare data for report:
        # ---------------------------------------------------------------------
        res = []
        self.jumped = []

        # Fabric has different sort block:
        if mp_mode == 'fabric':
            _logger.info('Set sort for fabric')
            order_mode = lambda code: (
                y_axis[code][8],
                code[0:3],
                code[6:12],
                code[3:6],
                )
        else:
            _logger.info('Set sort for all')
            order_mode = lambda code: (
                y_axis[code][12],
                code,
                )

        write_xls_line('extra', ('Remove lines:', ))

        if mp_mode == 'fabric':
            all_component_ids = []  # not need in fabric report!
        else:  # component
            # Search all product with inventory category used:
            all_component_ids = self._get_all_product_in_bom(
                cr, uid,
                data=data,
                exclude_inventory_ids=exclude_inventory_ids,
                context=context)

            # Remove the one with stock:
            for product in product_pool.browse(
                    cr, uid, all_component_ids, context=context):
                if product.mx_net_mrp_qty <= 0.0:
                    continue
                category = ''  # XXX no more used?
                add_x_item(
                    y_axis, product, category, purchase_db, 'product')

                # Remove component for check:
                if product.id in all_component_ids:
                    all_component_ids.remove(product.id)

        for key in sorted(y_axis, key=order_mode):
            # -----------------------------------------------------------------
            # Normal report block:
            # -----------------------------------------------------------------
            current = y_axis[key]  # readability:
            product = current[7]

            total = 0.0  # INV 0.0

            # XXX NOTE: INV now is 31/12 next put Sept. (old information)
            # inv_pos = 3 # December # TODO never use this!!!
            inv_pos = 0  # September (always append here inventory)
            jumped = False
            negative = False  # Check if there's negative SAL

            for i in range(0, 12):
                # if i == inv_pos:
                #    current[3][i] += round(current[0], 0) # add inv.
                current[3][i] = int(round(current[3][i], 0))
                current[4][i] = int(round(current[4][i], 0))
                current[5][i] = int(round(current[5][i], 0))

                # Empty block test:
                if not(any(current[3]) or any(current[4]) or
                        any(current[5]) or current[0] > 0.0):
                    # _logger.warning('Jumped: %s %s %s' % current
                    self.jumped.append(current[7])  # product proxy
                    jumped = True
                    # XXX Maybe optimize: Repeat loop for nothing?
                    continue

                if i == inv_pos:
                    # TODO remove from T. CAR inventory!!!
                    # current[1] -= round(current[0], 0) # T. CAR
                    total += round(current[0], 0)  # Add inv.

                total += round(
                    current[3][i] + current[4][i] + current[5][i], 0)
                current[6][i] = int(total)
                if only_negative and current[6][i] < 0.0:
                    negative = True

            # -----------------------------------------------------------------
            # Inventory management block:
            # -----------------------------------------------------------------
            # XXX maybe remove:
            if for_inventory_delta and \
                    product.default_code not in inventory_delta:
                inventory_delta[product.default_code] = (
                    product.inventory_start,  # 0. INV
                    sum(current[4][0: inventory_pos + 1]),  # 1. Current OC
                    sum(current[5][0: inventory_pos + 1]),  # 2. Current OF
                    current[6][inventory_pos],  # 3. Current SAL
                    product.inventory_delta,  # 4. Delta
                    )

            # Append progress totals:
            if jumped:
                write_xls_line('extra', (product.default_code, ))
            else:
                if only_negative:
                    if negative:
                        res.append(current)
                else:
                    res.append(current)

        # Restore previous state:
        user_pool.set_no_inventory_status(
            cr, uid, value=previous_status, context=context)

        # A. Case: Inventory data:
        if for_inventory_delta:
            return inventory_delta

        # B. Case: Component, Fabric textilene
        return res, all_component_ids


class Parser(report_sxw.rml_parse):
    counters = {}
    headers = {}

    def __init__(self, cr, uid, name, context):
        super(Parser, self).__init__(cr, uid, name, context)
        self.localcontext.update({
            'get_object': self.get_object,
            'get_jumped': self.get_jumped,
            'get_filter': self.get_filter,
            'get_date': self.get_date,
            })

    def get_jumped(self, ):
        """ Get filter selected
        """
        return self.jumped

    def get_date(self, ):
        """ Get filter selected
        """
        return datetime.now().strftime(DEFAULT_SERVER_DATE_FORMAT)

    def get_filter(self, data):
        """ Get filter selected
        """
        data = data or {}
        return data.get('partner_name', '')

    def get_object(self, data):
        """ Search all product elements
            data:
                mode: use (product), half-work, component for choose row
                elements

                # TODO:
                period: period type week, month
                period: number of period for columns, max 12
        """
        # Readability:
        cr = self.cr
        uid = self.uid
        context = {}
        mrp_pool = self.pool.get('mrp.production')

        res, all_component_ids = mrp_pool.get_explode_report_object(
            cr, uid, data=data, context=context)
        return res
