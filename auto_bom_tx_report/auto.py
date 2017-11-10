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
    ''' Wizard for print status
    '''
    _inherit = 'component.status.report.wizard'

    # --------------------
    # Wizard button event:
    # --------------------
    def action_open_report_xlsx(self, cr, uid, ids, context=None):
        ''' Event for button done
        '''
        if context is None: 
            context = {
                'lang': 'it_IT',
                }
        mrp_pool = self.pool.get('mrp.production')     
        attachment_pool = self.pool.get('ir.attachment')
        
        wiz_browse = self.browse(cr, uid, ids, context=context)[0]        
        datas = {
            'mode': wiz_browse.mode, #'mode': 'component', 
            'mp_mode': wiz_browse.mp_mode, # 'mp_mode': 'fabric', 
            'days': wiz_browse.days,
            'first_supplier_id': wiz_browse.first_supplier_id.id or False,
            #'negative_start': wiz_browse.negative_start,
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
            #'model': 'mrp.production',
            #'active_id': False,
            #'active_ids': [],
            #'context': context,
            }

        filename = mrp_pool.extract_mrp_production_report_xlsx(
            cr, uid, data=datas, context=context)
        _logger.info('Extracted file in %s' % filename)

        b64 = open(filename, 'rb').read().encode('base64')
        attachment_id = attachment_pool.create(cr, uid, {
            'name': 'Stato materiali',
            'datas_fname': 'stato_materiali_%s.xlsx' % wiz_browse.mode,
            'type': 'binary',
            'datas': b64,
            'partner_id': 1,
            'res_model': 'res.partner',
            'res_id': 1,
            }, context=context)

        return {
            'type' : 'ir.actions.act_url',
            'url': '/web/binary/saveas?model=ir.attachment&field=datas&'
                'filename_field=datas_fname&id=%s' % attachment_id,
            'target': 'self',
            }

class MrpProduction(orm.Model):
    """ Model name: MrpProduction
    """
    
    _inherit = 'mrp.production'
    
    def extract_mrp_production_report_xlsx(
            self, cr, uid, data=None, context=None):
        ''' Extract data from report and put in excel mode
        '''
        # ---------------------------------------------------------------------
        # Utility:
        # ---------------------------------------------------------------------
        def write_xls_mrp_line(WS, row, line):
            ''' Write line in excel file
            '''
            col = 0
            for record in line:
                if len(record) == 2: # Normal text, format
                    WS.write(row, col, *record)
                else: # Rich format
                    WS.write_rich_string(row, col, *record)
                col += 1
            return True

        def get_xls_format(mode=False, WB=None):  
            ''' Database for format cells
                first call is with mode not present and WB pased
                next call with only mode
            '''
            if not mode or not self.xls_format_db:
                self.xls_format_db = {
                'title' : WB.add_format({
                    'bold': True, 
                    'font_name': 'Courier 10 pitch', # 'Arial'
                    'font_size': 11,
                    'align': 'left',
                    }),
                'header': WB.add_format({
                    'bold': True, 
                    'font_color': 'black',
                    'font_name': 'Courier 10 pitch', # 'Arial'
                    'font_size': 9,
                    'align': 'center',
                    'valign': 'vcenter',
                    'bg_color': '#cfcfcf', # gray
                    'border': 1,
                    #'text_wrap': True,
                    }),
                'text': WB.add_format({
                    'font_color': 'black',
                    'font_name': 'Courier 10 pitch',
                    'font_size': 9,
                    'align': 'left',
                    'border': 1,
                    }),
                'text_center': WB.add_format({
                    'font_color': 'black',
                    'font_name': 'Courier 10 pitch',
                    'font_size': 9,
                    'align': 'center',
                    'border': 1,
                    }),
                    
                # -------------------------------------------------------------
                # With text color:
                # -------------------------------------------------------------
                'bg_red': WB.add_format({
                    'bold': True, 
                    'font_color': 'black',
                    'bg_color': '#ff420e',
                    'font_name': 'Courier 10 pitch',
                    'font_size': 9,
                    'align': 'left',
                    'border': 1,
                    }),
                'bg_green': WB.add_format({
                    'bold': True, 
                    'font_color': 'black',
                    'bg_color': '#99cc66',
                    'font_name': 'Courier 10 pitch',
                    'font_size': 9,
                    'align': 'left',
                    'border': 1,
                    }),
                'bg_order': WB.add_format({
                    'bold': True, 
                    'font_color': 'black',
                    'bg_color': '#cc9900',
                    'font_name': 'Courier 10 pitch',
                    'font_size': 9,
                    'align': 'right',
                    'border': 1,
                    'num_format': num_format,
                    }),

                # -------------------------------------------------------------
                # With text color:
                # -------------------------------------------------------------
                'text_black': WB.add_format({
                    'font_color': 'black',
                    'font_name': 'Courier 10 pitch',
                    'font_size': 9,
                    'align': 'left',
                    'border': 1,
                    'text_wrap': True
                    }),
                'text_blue': WB.add_format({
                    'font_color': 'blue',
                    'font_name': 'Courier 10 pitch',
                    'font_size': 9,
                    'align': 'left',
                    'border': 1,
                    'text_wrap': True
                    }),
                'text_red': WB.add_format({
                    'font_color': '#ff420e',
                    'font_name': 'Courier 10 pitch',
                    'font_size': 9,
                    'align': 'left',
                    'border': 1,
                    'text_wrap': True
                    }),
                'text_green': WB.add_format({
                    'font_color': '#328238', ##99cc66
                    'font_name': 'Courier 10 pitch',
                    'font_size': 9,
                    'align': 'left',
                    'border': 1,
                    'text_wrap': True
                    }),

                'text_grey': WB.add_format({
                    'font_color': '#eeeeee',
                    'font_name': 'Courier 10 pitch',
                    'font_size': 9,
                    'align': 'left',
                    'border': 1,
                    }),                
                'text_wrap': WB.add_format({
                    'font_color': 'black',
                    'font_name': 'Courier 10 pitch',
                    'font_size': 9,
                    'align': 'left',
                    'border': 1,
                    'text_wrap': True,
                    }),

                'text_bg_yellow': WB.add_format({
                    'bold': True, 
                    'font_color': 'black',
                    'bg_color': '#ffff99',
                    'font_name': 'Courier 10 pitch',
                    'font_size': 9,
                    'align': 'left',
                    'border': 1,
                    }),
                    
                'number': WB.add_format({
                    'font_name': 'Courier 10 pitch',
                    'font_size': 9,
                    'align': 'right',
                    'border': 1,
                    'num_format': num_format,
                    }),
                'number_blue': WB.add_format({
                    'font_color': 'blue',
                    'font_name': 'Courier 10 pitch',
                    'font_size': 9,
                    'align': 'right',
                    'border': 1,
                    'num_format': num_format,
                    }),
                'text_total': WB.add_format({
                    'bold': True, 
                    'font_color': 'black',
                    'font_name': 'Courier 10 pitch',
                    'font_size': 9,
                    'align': 'left',
                    'bg_color': '#DDDDDD',
                    'border': 1,
                    #'text_wrap': True,
                    }),
                'number_total': WB.add_format({
                    'bold': True, 
                    'font_name': 'Courier 10 pitch',
                    'font_size': 9,
                    'align': 'right',
                    'bg_color': '#DDDDDD',
                    'border': 1,
                    'num_format': num_format,
                    }),
                }
            return self.xls_format_db.get(mode, False)
            
        def write_xls_block_line(WS, row, line):
            ''' Write line block for fabric, return new row position
            '''
            # Extract element from line_
            (inv, tcar, tscar, mm, oc, of, sal, o, category, hw, hw_total) = \
                line
            
            # Jump pipes:
            if category == 'Pipes':    
                return row # same row
                
            # -----------------------------------------------------------------
            #                            ROW 0
            # -----------------------------------------------------------------
            # Merge cell:
            WS.merge_range(row, 0, row, 10, '')
            WS.merge_range(row, 11, row, 15, '')

            if sal[11] < 0:
                format_text = get_xls_format('bg_red')
            else:
                format_text = get_xls_format('bg_green')
            
            line0 = [
                ('%s - %s (forn. abit.: %s)' % (
                    o.name,
                    o.colour,
                    o.first_supplier_id.name if o.first_supplier_id else '',
                    ), format_text),
                ('', format_text),
                ('', format_text),
                ('', format_text),
                ('', format_text),
                ('', format_text),
                ('', format_text),
                ('', format_text),
                ('', format_text),
                ('', format_text),
                ('', format_text),
                (category, format_text),
                ('', format_text),
                ('', format_text),
                ]        
            write_xls_mrp_line(WS, row, line0)
            row += 1
            
            # -----------------------------------------------------------------
            #                            ROW 1
            # -----------------------------------------------------------------
            format_header = get_xls_format('header')
            format_number = get_xls_format('number')
            
            # Merge cell:            
            WS.merge_range(row, 0, row, 1, '')
            
            # Create row data:
            line1 = [
                ('%s' % o.default_code, format_header),
                ('', format_header),
                ('Set.', format_header),
                ('Ott.', format_header),
                ('Nov.', format_header),
                ('Dic.', format_header),
                ('Gen.', format_header),
                ('Feb.', format_header),
                ('Mar.', format_header),
                ('Apr.', format_header),
                ('Mag.', format_header),
                ('Giu.', format_header),
                ('Lug.', format_header),
                ('Ago.', format_header),
                ('LEADTIME', format_header),
                ('LOTTO', format_header),
                ]
            write_xls_mrp_line(WS, row, line1)
            row += 1
                
            # -----------------------------------------------------------------
            #                            ROW 2
            # -----------------------------------------------------------------
            format_text = get_xls_format('text')
            
            # Create row data:
            line2 = [
                ('Inv. %s: %s' % (
                    o.mx_start_date or '', inv), format_text),
                ('MM', get_xls_format('text_center')),
                (mm[0], format_number),
                (mm[1], format_number),
                (mm[2], format_number),
                (mm[3], format_number),
                (mm[4], format_number),
                (mm[5], format_number),
                (mm[6], format_number),
                (mm[7], format_number),
                (mm[8], format_number),
                (mm[9], format_number),
                (mm[10], format_number),
                (mm[11], format_number),
                ('', format_header),
                ('', format_header),
                ]
            write_xls_mrp_line(WS, row, line2)
            row += 1
            
            # -----------------------------------------------------------------
            #                            ROW 3
            # -----------------------------------------------------------------
            line3 = [
                ('Tot. Scar.: %s' % tscar, format_text),
                ('OC', get_xls_format('text_center')),
                (oc[0], format_number),
                (oc[1], format_number),
                (oc[2], format_number),
                (oc[3], format_number),
                (oc[4], format_number),
                (oc[5], format_number),
                (oc[6], format_number),
                (oc[7], format_number),
                (oc[8], format_number),
                (oc[9], format_number),
                (oc[10], format_number),
                (oc[11], format_number),
                ('', format_header),
                ('', format_header),
                ]
            write_xls_mrp_line(WS, row, line3)
            row += 1

            # -----------------------------------------------------------------
            #                            ROW 4
            # -----------------------------------------------------------------
            line4 = [
                ('Tot. Car.: %s' % tcar, format_text),
                ('OF', get_xls_format('text_center')),
                (of[0], format_number),
                (of[1], format_number),
                (of[2], format_number),
                (of[3], format_number),
                (of[4], format_number),
                (of[5], format_number),
                (of[6], format_number),
                (of[7], format_number),
                (of[8], format_number),
                (of[9], format_number),
                (of[10], format_number),
                (of[11], format_number),
                ('', format_header),
                ('', format_header),
                ]
            write_xls_mrp_line(WS, row, line4)
            row += 1
                            
            # -----------------------------------------------------------------
            #                            ROW 5
            # -----------------------------------------------------------------
            line5 = [
                ('Mag.: %s' % o.mx_net_mrp_qty, get_xls_format(
                    'text_bg_yellow')),
                ('SAL', get_xls_format('text_center')),
                (sal[0], format_number),
                (sal[1], format_number),
                (sal[2], format_number),
                (sal[3], format_number),
                (sal[4], format_number),
                (sal[5], format_number),
                (sal[6], format_number),
                (sal[7], format_number),
                (sal[8], format_number),
                (sal[9], format_number),
                (sal[10], format_number),
                (sal[11], format_number),
                ('', format_header),
                ('', format_header),
                ]
            write_xls_mrp_line(WS, row, line5)
            row += 1

            # -----------------------------------------------------------------
            #                            Order block
            # -----------------------------------------------------------------
            
            format_order = get_xls_format('bg_order')
            lineOrd = [
                ('Ordinare:', format_order),
                (o.uom_id.name or '?', get_xls_format('text_center')),
                ]
            # Order only from now to the end of block:    
            for i in range(1, 13):
                if i >= self.current_day_cell:
                    lineOrd.append(('',  format_order))
                else:    
                    lineOrd.append(('', format_text))
            # Extra data (leadtime and order lot):        
            lineOrd.append((o.leadtime or 0, format_number))
            lineOrd.append((o.purchase_lot_block or 0, format_number))
                
            write_xls_mrp_line(WS, row, lineOrd)
            row += 1
            
            # -----------------------------------------------------------------
            #                            ROW Halfwork
            # -----------------------------------------------------------------
            if hw:
                # Merge cell:
                WS.merge_range(row, 0, row, 12, '')

                # Create row data:
                line6 = [
                    [], # rich text format
                    ('', format_text),
                    ('', format_text),
                    ('', format_text),
                    ('', format_text),
                    ('', format_text),
                    ('', format_text),
                    ('', format_text),
                    ('', format_text),
                    ('', format_text),
                    ('', format_text),
                    ('', format_text),
                    ('', format_text),
                    (int(hw_total[0]), get_xls_format('number_blue')),
                    ]                        
                for hw_code, hw_status in hw.iteritems():
                    if hw_status[1] <= hw_status[0]: # black
                        line6[0].append(get_xls_format('text')) 
                    else: # red
                        line6[0].append(get_xls_format('text_red'))
                    line6[0].append('%s OC:%s' % (
                        hw_code,
                        int(hw_status[1]),
                        ))
                        
                    # Green:
                    line6[0].append(get_xls_format('text_green'))
                    line6[0].append(' M.:%s' % int(hw_status[0]))
                    line6[0].append(get_xls_format('text_black'))
                    line6[0].append('>>>')
                    line6[0].append(get_xls_format('text_blue'))
                    line6[0].append('%s ' % int(hw_status[2]))
                    #line6[0].append(get_xls_format('text_wrap'))
                    
                line6[0].append(get_xls_format('text_grey'))
                write_xls_mrp_line(WS, row, line6)
                row += 1
                
            # -----------------------------------------------------------------
            #                          EXTRA ROW
            # -----------------------------------------------------------------
            row += 1
            return row
        
        filename = '/tmp/extract_fabric_report.xlsx'        
        _logger.info('Start create file %s' % filename)
        WB = xlsxwriter.Workbook(filename)
        WS = WB.add_worksheet(_('Fabric'))

        # Format columns width:
        WS.set_column('A:A', 19)
        WS.set_column('B:B', 3)
        WS.set_column('C:N', 8)
        
        # Current month cell:
        convert_month = {
            1: 5, 2: 6, 3: 7, 4: 8, 5:9, 6: 10, 7: 11, 8: 12,
            9: 1, 10: 2, 11: 3, 12: 4,            
            }
        self.current_day_cell = convert_month[datetime.now().month]
        
        # Format for cell:            
        num_format = '#,##0'
        
        # ---------------------------------------------------------------------
        #                     EXPORT EXCEL REPORT
        # ---------------------------------------------------------------------
        # Generate format database:
        get_xls_format(mode=False, WB=WB)
        
        # Generate data report:
        res = self.get_explode_report_object(
            cr, uid, data=data, context=context)
        
        # Loop all record to write:
        row = 0
        for line in res:
            row = write_xls_block_line(WS, row, line)
        WB.close()
        _logger.info('End creation file %s' % filename)
        return filename
        
    def send_fabric_mrp_report_scheduler(
            self, cr, uid, mode='odt', context=None):
        ''' Generate PDF with data and send mail
        '''
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
            'mp_mode': 'fabric', 
            'only_negative': False, # TODO
            'without_type_ids': [], 
            'mode': 'component', 
            'type_id': False,
            'with_deadline': False, 
            'days': 30, 
            'first_supplier_id': False, 
            'with_type_ids': []
            }

        # ---------------------------------------------------------------------
        # Report in ODT mode:
        # ---------------------------------------------------------------------
        if mode == 'odt':                
            report_name = 'stock_status_explode_report'
    
            # -----------------------------------------------------------------
            # Call report:            
            # -----------------------------------------------------------------
            # Procedure for problem in setup language in ODT report
            mrp_ids = self.search(cr, uid, [], context=context)
            if mrp_ids:
                mrp_id = mrp_ids[0]
            else:
                mrp_id = False
                    
            try:
                result, extension = openerp.report.render_report(
                    cr, uid, [mrp_id], report_name, datas, context)
            except:
                _logger.error('Error generation TX report [%s]' % (
                    sys.exc_info(),))
                return False            
            attachments = [('Completo.odt', result)]
        elif mode == 'xlsx':
            filename = self.extract_mrp_production_report_xlsx(
                cr, uid, data=datas, context=context)                

            # Create attachment block for send after:    
            xlsx_raw = open(filename, 'rb').read()
            attachments = [('Stato_tessuti.xlsx', xlsx_raw)]            
        else:
            _logger.error('Only odt or xlsx mode for this report!')
            return False
                
        # ---------------------------------------------------------------------
        # Send report:
        # ---------------------------------------------------------------------
        # Send mail with attachment:
        group_pool = self.pool.get('res.groups')
        model_pool = self.pool.get('ir.model.data')
        thread_pool = self.pool.get('mail.thread')
        group_id = model_pool.get_object_reference(
            cr, uid, 'textilene_status', 'group_textilene_admin')[1]    
        partner_ids = []
        for user in group_pool.browse(
                cr, uid, group_id, context=context).users:
            partner_ids.append(user.partner_id.id)
            
        thread_pool = self.pool.get('mail.thread')
        thread_pool.message_post(cr, uid, False, 
            type='email', 
            body='Stato tessuti settimanale', 
            subject='Invio automatico stato tessuto: %s' % (
                datetime.now().strftime(DEFAULT_SERVER_DATE_FORMAT),
                ),
            partner_ids=[(6, 0, partner_ids)],
            attachments=attachments, 
            context=context,
            )
        return True
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
