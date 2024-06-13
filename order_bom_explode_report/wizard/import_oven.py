# -*- coding: utf-8 -*-
###############################################################################
#
#    Copyright (C) 2001-2014 Micronaet SRL (<http://www.micronaet.it>).
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU Affero General Public License as published
#    by the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU Affero General Public License for more details.
#
#    You should have received a copy of the GNU Affero General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
###############################################################################
import os
import pdb
import sys
import logging
import xlrd
import base64
from openerp.osv import fields, osv, expression, orm
from datetime import datetime, timedelta
from openerp.tools.translate import _
from openerp.tools import (DEFAULT_SERVER_DATE_FORMAT,
    DEFAULT_SERVER_DATETIME_FORMAT,
    DATETIME_FORMATS_MAP,
    float_compare)

_logger = logging.getLogger(__name__)


class IndustriaImportOvenReportXlsx(orm.TransientModel):
    """ Model name: IndustriaImportOvenReportXlsx
    """
    _name = 'industria.import.oven.report.xlsx'

    def action_get_oven_report(self, cr, uid, ids, context=None):
        """ Generate report
        """
        mrp_pool = self.pool.get('mrp.production')
        return mrp_pool.get_oven_report(cr, uid, context=context)

    def get_oven_report_all(self, cr, uid, ids, context=None):
        """ Generate Oven report all lines
        """
        mrp_pool = self.pool.get('mrp.production')

        if context is None:
            context = {}
        ctx = context.copy()
        ctx['force_print_all'] = True
        return mrp_pool.get_oven_report(cr, uid, context=ctx)

    def action_import_with_update(self, cr, uid, ids, context=None):
        """ Event for button done force update lead lot
        """
        if context is None:
            context = {}

        # Pool used:
        bom_pool = self.pool.get('mrp.bom')
        job_pool = self.pool.get('industria.job')
        oven_pool = self.pool.get('mrp.production.oven.selected')

        # ---------------------------------------------------------------------
        # Save file passed:
        # ---------------------------------------------------------------------
        wizard = self.browse(cr, uid, ids, context=context)[0]
        if not wizard.file:
            raise osv.except_osv(
                _('No file:'),
                _('Please pass a XLSX file for import order'),
                )
        b64_file = base64.decodestring(wizard.file)

        # Save in temp:
        now = datetime.now()
        now_text = now.strftime(DEFAULT_SERVER_DATETIME_FORMAT).replace(
            ':', '_').replace('-', '_')
        filename = '/tmp/oven_%s.xlsx' % now_text
        f = open(filename, 'wb')
        f.write(b64_file)
        f.close()

        # ---------------------------------------------------------------------
        # Parameters:
        # ---------------------------------------------------------------------
        row_start = 1

        # ---------------------------------------------------------------------
        # Load force name (for web publish)
        # ---------------------------------------------------------------------
        try:
            wb = xlrd.open_workbook(filename)
        except:
            raise osv.except_osv(
                _('Error XLSX'),
                _('Cannot read XLS file: %s' % filename),
                )

        # ---------------------------------------------------------------------
        # Loop on all pages:
        # ---------------------------------------------------------------------
        pdb.set_trace()
        error = ''
        negative_data = {}
        if wizard.mode == 'negative':
            for ws_name in wb.sheet_names():
                color = ws_name
                ws = wb.sheet_by_name(ws_name)
                _logger.warning('Read page: %s' % ws_name)

                error = ''
                for row in range(row_start, ws.nrows):
                    try:
                        bom_id = int(ws.cell(row, 0).value)
                    except:
                        _logger.error('Not line %s' % row)
                        continue
                    try:
                        bom = bom_pool.browse(cr, uid, bom_id, context=context)
                    except:
                        error += 'Color %s BOM ID %s: Not preset BOM ID' % (
                            color, bom_id)
                    key = color, bom_id

                    # Read data:
                    bom_id = int(ws.cell(row, 0).value)
                    try:
                        quantity = int(ws.cell(row, 4).value)

                        # Collect data for job if negative:
                        if quantity < 0:
                            if color not in negative_data:
                                negative_data[color] = {}
                            if bom_id not in negative_data[color]:
                                negative_data[color][bom_id] = 0.0
                            negative_data[color][bom_id] -= quantity

                    except:
                        _logger.error('Page %s - Row %s: Not a number' % (
                            color, row))

            # -----------------------------------------------------------------
            # Generate Job and confirm:
            # -----------------------------------------------------------------
            if now.month < 9:
                year_1 = now.year
                year_2 = year_1 - 1
            else:
                year_2 = now.year
                year_1 = year_2 + 1

            ctx = context.copy()
            created_at = '%s-09-01' % year_1  # Create start of season
            ctx['force_header'] = {
                'created_at': created_at,
                'state': 'COMPLETED',
                }
            pdb.set_trace()
            for color in negative_data:
                # Create pending lined for this color:
                for bom_id in negative_data[color]:
                    quantity = negative_data[color][bom_id]
                    if quantity > 0:
                        oven_pool.create(cr, uid, {
                            'total': quantity,
                            'bom_id': bom_id,
                            'color_code': color,
                        }, context=context)
                _logger.info('Generate Job for pending lines: %s' % created_at)
                oven_pool.generate_oven_job_all(cr, uid, [], context=ctx)

        # if error:
        _logger.info('Imported: %s' % filename)
        return True

    _columns = {
        'file': fields.binary('XLSX file', filters=None),
        'mode': fields.selection([
            ('negative', 'Parifica negativi'),
            ('job', 'Crea Job'),
            ], 'Mode'),
        'error': fields.text('Errore'),
        }

    _defaults = {
       'mode': lambda *x: 'job',
       }
