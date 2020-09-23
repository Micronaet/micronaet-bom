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
import sys
import logging
import openerp
import xlsxwriter
import openerp.netsvc as netsvc
import openerp.addons.decimal_precision as dp
from openerp.osv import fields, osv, expression, orm
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
from openerp import SUPERUSER_ID, api
from openerp import tools
from openerp.tools.translate import _
from openerp.tools.float_utils import float_round as round
from openerp.tools import (DEFAULT_SERVER_DATE_FORMAT,
    DEFAULT_SERVER_DATETIME_FORMAT,
    DATETIME_FORMATS_MAP,
    float_compare)


_logger = logging.getLogger(__name__)


class ComponentStatusReportWizard(orm.TransientModel):
    """ Wizard for print status
    """
    _inherit = 'component.status.report.wizard'

    # --------------------
    # Wizard button event:
    # --------------------
    # TODO check!!!!!!!!!!!!!!!!!!!
    def action_open_cmpt_report_xlsx(self, cr, uid, ids, context=None):
        """ Event for button done
        """
        if context is None:
            context = {
                'lang': 'it_IT',
                }
        mrp_pool = self.pool.get('mrp.production')
        attachment_pool = self.pool.get('ir.attachment')

        wiz_browse = self.browse(cr, uid, ids, context=context)[0]
        datas = {
            'mode': wiz_browse.mode,  # 'mode': 'component',
            'mp_mode': wiz_browse.mp_mode, # 'mp_mode': 'fabric',
            'days': wiz_browse.days,
            'first_supplier_id': wiz_browse.first_supplier_id.id or False,
            # 'negative_start': wiz_browse.negative_start,
            'type_id': False, # TODO remove ex. wiz_browse.type_id.id or
            'with_type_ids':
                [item.id for item in wiz_browse.with_type_ids],
            'without_type_ids':
                [item.id for item in wiz_browse.without_type_ids],
            'with_deadline': wiz_browse.with_deadline,
            'only_negative': wiz_browse.only_negative,
            'exclude_inventory_category':
                wiz_browse.exclude_inventory_category,
            # Report setup:
            # 'model': 'mrp.production',
            # 'active_id': False,
            # 'active_ids': [],
            # 'context': context,
            }

        filename = mrp_pool.extract_mrp_production_report_xlsx(
            cr, uid, data=datas, context=context)
        _logger.info('Extracted file in %s' % filename)

        b64 = open(filename, 'rb').read().encode('base64')
        attachment_id = attachment_pool.create(cr, uid, {
            'name': 'Stato componenti',
            'datas_fname':
                'stato_componenti_materiali_%s.xlsx' % wiz_browse.mode,
            'type': 'binary',
            'datas': b64,
            'partner_id': 1,
            'res_model': 'res.partner',
            'res_id': 1,
            }, context=context)

        return {
            'type': 'ir.actions.act_url',
            'url': '/web/binary/saveas?model=ir.attachment&field=datas&'
                'filename_field=datas_fname&id=%s' % attachment_id,
            'target': 'self',
            }


class MrpProduction(orm.Model):
    """ Model name: MrpProduction
    """

    _inherit = 'mrp.production'

    def send_component_mrp_report_scheduler(
            self, cr, uid, mode='xlsx', context=None):
        """ Generate PDF with data and send mail
        """
        _logger.info('Send report COMPONENT')
        if context is None:
            context = {
                'lang': 'it_IT',
                }

        # Prepare data selection filter (as wizard):
        datas = {
            # Report setup:
            'model': 'mrp.production',
            'active_id': False,
            'active_ids': [],
            'context': context,

            # Datas setup:
            'mode': 'component',
            'without_type_ids': [],
            'with_type_ids': [],
            'type_id': False,
            'with_deadline': False,
            'only_negative': False,  # TODO
            'line_ids': [],
            # 'mp_mode': False,  # TODO check
            # 'days': 30,
            # 'first_supplier_id': False,
            'exclude_inventory_category': True,  # Remove category not used
            }

        # ---------------------------------------------------------------------
        # Call report:
        # ---------------------------------------------------------------------
        mrp_pool = self.pool.get('mrp.production')
        now = datetime.now().strftime(DEFAULT_SERVER_DATETIME_FORMAT)
        now = now.replace('-', '_').replace(':', '.')
        if mode == 'xlsx':
            filename = mrp_pool.extract_mrp_production_report_xlsx(
                cr, uid, data=datas, context=context)
            _logger.info('Extracted file in %s' % filename)

            # Create attachment block for send after:
            result = open(filename, 'rb').read() #xlsx raw
        else: # odt
            mode = 'odt' # for extension
            # Procedure for problem in setup language in ODT report
            mrp_ids = self.search(cr, uid, [], context=context)
            if mrp_ids:
                mrp_id = mrp_ids[0]
            else:
                mrp_id = False

            try:
                result, extension = openerp.report.render_report(
                    cr, uid, [mrp_id], 'stock_status_explode_report',
                    datas, context)
            except:
                _logger.error('Error generation component report [%s]' % (
                    sys.exc_info(),))
                return False
        attachments = [('Componenti_%s.%s' % (now, mode), result)]

        # ---------------------------------------------------------------------
        # Send report:
        # ---------------------------------------------------------------------
        # Send mail with attachment:
        group_pool = self.pool.get('res.groups')
        model_pool = self.pool.get('ir.model.data')
        thread_pool = self.pool.get('mail.thread')
        group_id = model_pool.get_object_reference(
            cr, uid,
            'auto_bom_component_report',
            'group_component_report_admin',
            )[1]
        partner_ids = []
        for user in group_pool.browse(
                cr, uid, group_id, context=context).users:
            partner_ids.append(user.partner_id.id)

        thread_pool = self.pool.get('mail.thread')
        thread_pool.message_post(cr, uid, False,
            type='email',
            body='Stato componenti settimanale',
            subject='Invio automatico stato componenti: %s' % (
                datetime.now().strftime(DEFAULT_SERVER_DATE_FORMAT),
                ),
            partner_ids=[(6, 0, partner_ids)],
            attachments=attachments,
            context=context,
            )
        return True
