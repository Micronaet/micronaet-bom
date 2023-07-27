# -*- coding: utf-8 -*-
###############################################################################
#
# ODOO (ex OpenERP)
# Open Source Management Solution
# Copyright (C) 2001-2015 Micronaet S.r.l. (<http://www.micronaet.it>)
# Developer: Nicola Riolini @thebrush (<https://it.linkedin.com/in/thebrush>)
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as
# published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.
# See the GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program. If not, see <http://www.gnu.org/licenses/>.
#
###############################################################################
import os
import sys
import erppeek
import ConfigParser
import excel_export

ExcelWriter = excel_export.excelwriter.ExcelWriter

temp = {
    'TUKEPRO': 0.08,
    'TUBSED431': 0.1312,
    'TUB132': 0.1448,
    'DI229': 0.2032,
    'GA602': 0.312,
    'GP602': 0.3152,
    'DIGPB602': 0.3193,
    'AP119': 0.3328,
    'DIG640': 0.3472,
    'GA136': 0.372,
    'GA431': 0.372,
    'GP136': 0.3784,
    'GAKEPRO': 0.4008,
    'GC136': 0.476,
    'GP055': 0.4929,
    'GA055': 0.5115,
    'GP132': 0.5568,
    'G2332': 0.9944,
    'G1332': 1.0288,
    'GB127FR': 1.1672,
    'GA127FR': 1.2464,
    'GA119': 1.264,
    'AN119': 1.436,
    }


wf_lavoration = {
    'AN023': 0.2,
    'AN028': 0.2,
    'AN031': 0.25,
    'AN123': 0.2,
    'AN128': 0.1,
    'AN131': 0.1,
    'AS145': 0.1,
    'BA301': 0.1,
    'BARSED148': 0.1,
    'BR810': 0.1,
    'BRA035B': 0.1,
    'DADGODR12,6-148': 0.1,
    'DI037': 0.1,
    'DI037-038': 0.1,
    'DI045': 0.1,
    'DI070': 0.1,
    'DIS014': 0.1,
    'DIS024': 0.1,
    'DIS030': 0.1,
    'DIS129': 0.1,
    'DIS145': 0.1,
    'DIST029': 0.1,
    'DIST130': 0.1,
    'DS037': 0.1,
    'G1330': 0.2,
    'G1331': 0.2,
    'G2330': 0.2,
    'G2331': 0.2,
    'GA022': 0.2,
    'GA023': 0.2,
    'GA024': 0.2,
    'GA025': 0.2,
    'GA026': 0.2,
    'GA027': 0.2,
    'GA029': 0.2,
    'GA030': 0.2,
    'GA031': 0.2,
    'GA035': 0.2,
    'GA036': 0.2,
    'GA037': 0.2,
    'GA041': 0.2,
    'GA045': 0.2,
    'GA048': 0.2,
    'GA081': 0.2,
    'GA123': 0.2,
    'GA127': 0.2,
    'GA129': 0.2,
    'GA130': 0.2,
    'GA131': 0.2,
    'GA132': 0.2,
    'GA135': 0.1,
    'GA145': 0.2,
    'GA148': 0.2,
    'GA162': 0.1,
    'GA163': 0.1,
    'GA229': 0.2,
    'GA421': 0.1,
    'GA800': 0.1,
    'GA810': 0.1,
    'GA831': 0.2,
    'GAG420': 0.2,
    'GAMANT050': 0.1,
    'GAMCENT050': 0.2,
    'GAMPOST050': 0.2,
    'GAPP025': 0.2,
    'GB026': 0.15,
    'GB027': 0.15,
    'GB031': 0.15,
    'GB127': 0.15,
    'GB131': 0.15,
    'GB135': 0.15,
    'GC035': 0.1,
    'GC036': 0.1,
    'GC037': 0.1,
    'GC135': 0.1,
    'GC421': 0.1,
    'GCG420': 0.1,
    'GD322': 0.2,
    'GFERARIA': 0.1,
    'GP021': 0.1,
    'GP024': 0.1,
    'GP025': 0.1,
    'GP029': 0.1,
    'GP030': 0.1,
    'GP035': 0.1,
    'GP036': 0.1,
    'GP037': 0.1,
    'GP041': 0.1,
    'GP045': 0.1,
    'GP048': 0.1,
    'GP081': 0.1,
    'GP129': 0.2,
    'GP130': 0.2,
    'GP145': 0.2,
    'GP147': 0.2,
    'GP148': 0.2,
    'GP148B': 0.2,
    'GP229': 0.2,
    'GP322': 0.2,
    'GP421': 0.1,
    'GP810': 0.2,
    'GPG420': 0.1,
    'IN005': 0.1,
    'IN205': 0.2,
    'L600': 0.1,
    'L620': 0.1,
    'LA070': 0.2,
    'P1330': 0.1, #
    'P2330': 0.1, #
    'PAR034': 0.1,
    'PAR050': 0.1,
    'PAR421': 0.1,
    'PI810': 0.1,
    'PIA15X4GEST': 0.1, #
    'PIA15X4GINT': 0.1, #
    'PIPR081': 0.1,
    'PR029': 0.1,
    'PR030': 0.1,
    'PR035': 0.1,
    'PR037': 0.1,
    'PR081': 0.1,
    'PR129': 0.1,
    'PR130': 0.2,
    'PR135': 0.1,
    'PR145': 0.2,
    'PR229': 0.2,
    'PR421': 0.1,
    'PR810': 0.1,
    'PROG420': 0.1,
    'SC021': 0.2,
    'SC022': 0.1,
    'SC025': 0.1,
    'SC029': 0.2,
    'SC030': 0.2,
    'SC031': 0.2,
    'SC034': 0.2,
    'SC035': 0.2,
    'SC035B': 0.2,
    'SC037': 0.2,
    'SC045': 0.2,
    'SC050': 0.1,
    'SC070': 0.2,
    'SC081': 0.1,
    'SC118': 0.2,
    'SC129': 0.2,
    'SC130': 0.2,
    'SC131': 0.2,
    'SC135': 0.2,
    'SC145': 0.2,
    'SC148': 0.2,
    'SC150': 0.1,
    'SC163': 0.2,
    'SC229': 0.2,
    'SC550': 0.2,
    'SC800': 0.1,
    'SC810': 0.2,
    'SCH024': 0.2,
    'SCH041': 0.2,
    'SCH421': 0.2,
    'SCHG420': 0.1,
    'SE021': 0.1,
    'SE022': 0.1,
    'SE023': 0.1,
    'SE024': 0.1,
    'SE025': 0.1,
    'SE029': 0.1,
    'SE030': 0.1,
    'SE035': 0.1,
    'SE035B': 0.1,
    'SE037': 0.1,
    'SE045': 0.1,
    'SE070': 0.2,
    'SE081': 0.1,
    'SE118': 0.1,
    'SE123': 0.2,
    'SE129': 0.2,
    'SE130': 0.2,
    'SE132': 0.2,
    'SE135': 0.2,
    'SE148': 0.2,
    'SE150': 0.2,
    'SE229': 0.2,
    'SE810': 0.2,
    'SED041': 0.1,
    'SED048': 0.1,
    'SO034': 0.1,
    'SOSTPAR421': 0.1,
    'SP005': 0.1,
    'SP205': 0.2,
    'SS229': 0.2,
    'TE027': 0.1,
    'TE054': 0.1,
    'TE127': 0.1,
    'TELPA034': 0.1,
    'TU023': 0.1,
    'TU035': 0.1,
    'TU045': 0.1,
    'TU070': 0.1,
    'TU123': 0.2,
    'TU330mm335': 0.1,
    'TU550': 0.2,
    'TUB048': 0.1,
    'TUB135': 0.1,
    'TUBBRAC029': 0.1,
    'TUBGANT048': 0.2,
    'U600': 0.1,
    }

cocin_product = {
    'CIN127AK': 'COCIN127',
    'CIN127AR': 'COCIN127',
    'CIN127AR3': 'COCIN127',
    'CIN127AZ1': 'COCIN127',
    'CIN127BE20': 'COCIN127',
    'CIN127BILUC': 'COCIN127',
    'CIN127BL11': 'COCIN127',
    'CIN127BL12': 'COCIN127',
    'CIN127BL15': 'COCIN127',
    'CIN127CO0737': 'COCIN127',
    'CIN127GC': 'COCIN127',
    'CIN127GI6': 'COCIN127',
    'CIN127GR0600': 'COCIN127',
    'CIN127GR14': 'COCIN127',
    'CIN127GU16': 'COCIN127',
    'CIN127NE': 'COCIN127',
    'CIN127NELUC': 'COCIN127',
    'CIN127RO8': 'COCIN127',
    'CIN127SE': 'COCIN127',
    'CIN127SG': 'COCIN127',
    'CIN127TA0711': 'COCIN127',
    'CIN127VE17': 'COCIN127',
    'CIN127VE4': 'COCIN127',
    'CIN127VS26': 'COCIN127',
    'CIN150BH': 'COCIN150',
    'CIN150BILUC': 'COCIN150',
    'CIN150BL11': 'COCIN150',
    'CIN150BL15': 'COCIN150',
    'CIN150GI6': 'COCIN150',
    'CIN150GR0600': 'COCIN150',
    'CIN150GR14': 'COCIN150',
    'CIN150RO8': 'COCIN150',
    'CIN150VE4': 'COCIN150',
    'CIN150VI5': 'COCIN150',
    'CIN900AR13': 'COCIN900',
    'CIN900BE20': 'COCIN900',
    'CIN900BILUC': 'COCIN900',
    'CIN900BL15': 'COCIN900',
    'CIN900GR14': 'COCIN900',
    'CIN900NE': 'COCIN900',
    'CIN900VS26': 'COCIN900',
    'ELA420': 'COELASET',
    'MS038D  BIBE': 'COMT038S',
    'MS127   JUT': 'CO127',
    'MS127IL BL': 'CO127IL',
    'MS127IL GIRO': 'CO127IL',
    'MS127IL NA': 'CO127IL',
    'MS127IL VS': 'CO127IL',
    'MS127S  AN': 'CO127S',
    'MS127S  AR': 'CO127S',
    'MS127S  B2': 'CO127S',
    'MS127S  BI': 'CO127S',
    'MS127S  BIBE': 'CO127S',
    'MS127S  BINE': 'CO127S',
    'MS127S  CO': 'CO127S',
    'MS127S  GR': 'CO127S',
    'MS127S  NE': 'CO127S',
    'MS127S  S4': 'CO127S',
    'MS127S  S7': 'CO127S',
    'MS127S  SG': 'CO127S',
    'MS127S  VS': 'CO127S',
    'MS127S3 GR': 'CO127S3',
    'MS127S3 NE': 'CO127S3',
    'MS128S  AN': 'CO128S',
    'MS128S  AR': 'CO128S',
    'MS128S  BI': 'CO128S',
    'MS128S  BIBE': 'CO128S',
    'MS128S  BINE': 'CO128S',
    'MS128S  BL': 'CO128S',
    'MS128S  CO': 'CO128S',
    'MS128S  GK': 'CO128S',
    'MS128S  NA': 'CO128S',
    'MS128S  S4': 'CO128S',
    'MS128S  SG': 'CO128S',
    'MS128S  VS': 'CO128S',
    'MS129D  AR': 'COMT129D',
    'MS129D  BIBE': 'COMT129D',
    'MS129D  BINE': 'COMT129D',
    'MS129D  BL': 'COMT129D',
    'MS129D  CO': 'COMT129D',
    'MS129D  MC': 'COMT129D',
    'MS129D  NA': 'COMT129D',
    'MS129D  NE': 'COMT129D',
    'MS129D  S7': 'COMT129D',
    'MS129D  TA': 'COMT129D',
    'MS129D  VI': 'COMT129D',
    'MS129D  VP': 'COMT129D',
    'MS129D AN': 'COMT129D',
    'MS129S  BIBE': 'COMT129S',
    'MS129S3 GR': 'COMT129S3',
    'MS129S3 NE': 'COMT129S3',
    'MS130D  BIBE': 'COMT130D',
    'MS130D  S7': 'COMT130D',
    'MS130D  TA': 'COMT130D',
    'MS130D  VS': 'COMT130D',
    'MS130DXQBINE': 'CO130DXQ',
    'MS130S3 BO': 'CO130S3',
    'MS130S3 GR': 'CO130S3',
    'MS130S3 NE': 'CO130S3',
    'MS135D  BI': 'COMT135D',
    'MS135D  MC': 'COMT135D',
    'MS135D  NE': 'COMT135D',
    'MS135D  VP': 'COMT135D',
    'MS135S  BIBE': 'COMT135S',
    'MS135S  BINE': 'COMT135S',
    'MS135S3 GR': 'COMT135S3',
    'MS135S3 TA': 'COMT135S3',
    'MS145D  AR': 'COMT145D',
    'MS145D  BI': 'COMT145D',
    'MS145D  NE': 'COMT145D',
    'MS145D  VP': 'COMT145D',
    'MS145D BINE': 'COMT145D',
    'MS145D MC': 'COMT145D',
    'MS145DX BIBE': 'CO145DX',
    'MS145S  MC': 'COMT145S',
    'MS145S  NE': 'COMT145S',
    'MS145S  SA': 'COMT145S',
    'MS145S3 GR': 'COMT145S3',
    'MS145S3 NE': 'COMT145S3',
    'MS900L  BL': 'CO900S',
    'MS900L  NA': 'CO900S',
    'MS900L  VS': 'CO900S',
    'MS900S  AR': 'CO900S',
    'MS900S  BIBE': 'CO900S',
    'MS900S  BINE': 'CO900S',
    'MS900S  BL': 'CO900S',
    'MS900S  NA': 'CO900S',
    'MS900S  NE': 'CO900S',
    'MS900S  S4': 'CO900S',
    'MS900S  S7': 'CO900S',
    'MS900S  VS': 'CO900S',
    'PO649TX   AK': 'CO649',
    'PO649TX   AR': 'CO649',
    'PO649TX   AZ1': 'CO649',
    'PO649TX   BAT': 'CO649',
    'PO649TX   BIBE': 'CO649',
    'PO649TX   BIBL': 'CO649',
    'PO649TX   BK': 'CO649',
    'PO649TX   BL': 'CO649',
    'PO649TX   CO': 'CO649',
    'PO649TX   MC': 'CO649',
    'PO649TX   MW': 'CO649',
    'PO649TX   OT': 'CO649',
    'PO649TX   RO': 'CO649',
    'PO649TX   SE': 'CO649',
    'PO649TX   TJ': 'CO649',
    'PO649TX   VB': 'CO649',
    'PO649TX   VE': 'CO649',
    'PO649TX   VI': 'CO649',
    'PO649TX   VN': 'CO649',
    'PO649TX   VS': 'CO649',
    'PO649TX BI': 'CO649',
    'PO649TX BIAQ': 'CO649',
    'PO649TX BIGR': 'CO649',
    'PO649TX BS': 'CO649',
    'PO649TX DR': 'CO649',
    'PO649TX GC': 'CO649',
    'PO649TX GR': 'CO649',
    'PO649TX GU': 'CO649',
    'PO649TX LI': 'CO649',
    'PO649TX MG': 'CO649',
    'PO649TX NE': 'CO649',
    'PO649TX SG': 'CO649',
    'PO649TX TA': 'CO649',
    'PO649TX VP': 'CO649',
    'PO649TXR': 'CO649',
    'PO649TXR  RIVI': 'CO649',
    'PO650TX   AZ1': 'CO650',
    'PO650TX   BIBE': 'CO650',
    'PO650TX   NE': 'CO650',
    'PO650TX   SU': 'CO650',
    'PO650TX   VP': 'CO650',
    'PO650TX AR': 'CO650',
    'PO650TX BI': 'CO650',
    'PO650TX BIGR': 'CO650',
    'PO650TX BK': 'CO650',
    'PO650TX CO': 'CO650',
    'PO650TX DR': 'CO650',
    'PO650TX GR': 'CO650',
    'PO650TX MG': 'CO650',
    'PO650TX SG': 'CO650',
    'PO650TX TA': 'CO650',
    'PO650TX VN': 'CO650',
    'PO650TXR  RIAR': 'CO650',
    'PO650TXR  RIVI': 'CO650',
    'PA600PE BL': 'CO600',
    'PA600PE NA': 'CO600',
    'PA600PE RO': 'CO600',
    'PA600PE TA': 'CO600',
    'PA600PE VS': 'CO600',
    'PA600TX   AC  S': 'CO600',
    'PA600TX   AK': 'CO600',
    'PA600TX   AR': 'CO600',
    'PA600TX   BIGR': 'CO600',
    'PA600TX   BK': 'CO600',
    'PA600TX   GC': 'CO600',
    'PA600TX   GR': 'CO600',
    'PA600TX   GU': 'CO600',
    'PA600TX   MW': 'CO600',
    'PA600TX   NE': 'CO600',
    'PA600TX   RO': 'CO600',
    'PA600TX   TA': 'CO600',
    'PA600TX   VI': 'CO600',
    'PA600TX   VN': 'CO600',
    'PA600TX   VP': 'CO600',
    'PA600TX   VS': 'CO600',
    'PA600TX BI': 'CO600',
    'PA600TX BIAQ': 'CO600',
    'PA600TX BIBE': 'CO600',
    'PA600TX CO': 'CO600',
    'PA600TX MG': 'CO600',
    'PA600TX OT': 'CO600',
    'PA600TXR  RIVI': 'CO600',
    'PA601TX   BL': 'CO600',
    'PA601TX   MW': 'CO600',
    'PA601TX   VE': 'CO600',
    'PA601TX BI': 'CO600',
    'PA601TX BIBE': 'CO600',
    'PA601TX BIGR': 'CO600',
    'PA601TX GR': 'CO600',
    'PA601TX NE': 'CO600',
    'PA601TX VN': 'CO600',
    'PA601TX VP': 'CO600',
    'PA601TX VS': 'CO600',
    'PA034PE BL': 'COPA034',
    'PA034PE TA': 'COPA034',
    'PA034PE VS': 'COPA034',
    'PA034TX AK': 'COPA034',
    'PA034TX AR': 'COPA034',
    'PA034TX BI': 'COPA034',
    'PA034TX BIAQ': 'COPA034',
    'PA034TX BIGR': 'COPA034',
    'PA034TX BK': 'COPA034',
    'PA034TX BL': 'COPA034',
    'PA034TX CO': 'COPA034',
    'PA034TX CT': 'COPA034',
    'PA034TX GR': 'COPA034',
    'PA034TX MW': 'COPA034',
    'PA034TX NE': 'COPA034',
    'PA034TX OT': 'COPA034',
    'PA034TX SG': 'COPA034',
    'PA034TX TA': 'COPA034',
    'PA034TX VN': 'COPA034',
    'PA034TX VP': 'COPA034',
    'PA038TX BI': 'COPA038',
    'PA038TX BIBE': 'COPA038',
    'PA038TX BIGR': 'COPA038',
    'PA038TX GR': 'COPA038',
    'PA038TX NE': 'COPA038',
    'PA038TX SG': 'COPA038',
    'PA038TX TA': 'COPA038',
    'PA038TX VP': 'COPA038',
    'TP127PE AG': 'CO127',
    'TP127PE BI': 'CO127',
    'TP127PE BL': 'CO127',
    'TP127PE NA': 'CO127',
    'TP127PE NE': 'CO127',
    'TP127PE TA': 'CO127',
    'TP127PE VS': 'CO127',
    'TP900PE BI': 'CO900',
    'TP900PE BL': 'CO900',
    'TP900PE NE': 'CO900',
    'TP900PE TA': 'CO900',
    'TP900PE VS': 'CO900',
    'TS021TX BI': 'CO021',
    'TS021TX BIAQ': 'CO021',
    'TS021TX BIBE': 'CO021',
    'TS021TX BIGR': 'CO021',
    'TS021TX BK': 'CO021',
    'TS021TX CO': 'CO021',
    'TS021TX GR': 'CO021',
    'TS021TX NE': 'CO021',
    'TS021TX TA': 'CO021',
    'TS021TX VN': 'CO021',
    'TS021TX VP': 'CO021',
    'TS021TX VS': 'CO021',
    'TS022PE AR': 'CO022',
    'TS022PE BL': 'CO022',
    'TS022PE NA': 'CO022',
    'TS022PE RO': 'CO022',
    'TS022PE TA': 'CO022',
    'TS022PE VE': 'CO022',
    'TS022PE VS': 'CO022',
    'TS022TX AK': 'CO022',
    'TS022TX AR': 'CO022',
    'TS022TX BI': 'CO022',
    'TS022TX BIAQ': 'CO022',
    'TS022TX BIBE': 'CO022',
    'TS022TX BIGR': 'CO022',
    'TS022TX BK': 'CO022',
    'TS022TX BL': 'CO022',
    'TS022TX GR': 'CO022',
    'TS022TX NE': 'CO022',
    'TS022TX OT': 'CO022',
    'TS022TX RO': 'CO022',
    'TS022TX TA': 'CO022',
    'TS022TX VP': 'CO022',
    'TS022TX VS': 'CO022',
    'TS024PE AR': 'CO024',
    'TS024PE BL': 'CO024',
    'TS024PE NA': 'CO024',
    'TS024PE RO': 'CO024',
    'TS024PE VE': 'CO024',
    'TS024PE VS': 'CO024',
    'TS024TX BI': 'CO024',
    'TS024TX BIBE': 'CO024',
    'TS024TX BK': 'CO024',
    'TS024TX GR': 'CO024',
    'TS024TX SG': 'CO024',
    'TS024TX TA': 'CO024',
    'TS033PE RO': 'CO021',
    'TS033TX BI': 'CO033',
    'TS033TX VI': 'CO033',
    'TS037TX AK': 'CO037',
    'TS037TX BI': 'CO037',
    'TS037TX BIBE': 'CO037',
    'TS037TX BK': 'CO037',
    'TS037TX BS': 'CO037',
    'TS037TX GR': 'CO037',
    'TS037TX NE': 'CO037',
    'TS037TX SE': 'CO037',
    'TS037TX TA': 'CO037',
    'TS037TX VS': 'CO037',
    'TS038TX BI': 'CO038',
    'TS038TX BIBE': 'CO038',
    'TS038TX BIGR': 'CO038',
    'TS038TX BK': 'CO038',
    'TS038TX CO': 'CO038',
    'TS038TX GR': 'CO038',
    'TS038TX NE': 'CO038',
    'TS038TX SG': 'CO038',
    'TS038TX TA': 'CO038',
    'TS038TX VP': 'CO038',
    'TS041PE AR': 'CO041',
    'TS041PE BL': 'CO041',
    'TS041PE NA': 'CO041',
    'TS041PE RO': 'CO041',
    'TS041PE TA': 'CO041',
    'TS041PE VE': 'CO041',
    'TS041PE VS': 'CO041',
    'TS041TX BI': 'CO041',
    'TS041TX BIAQ': 'CO041',
    'TS041TX BIGR': 'CO041',
    'TS041TX BK': 'CO041',
    'TS041TX SG': 'CO041',
    'TS041TX TA': 'CO041',
    'TS041TX VP': 'CO041',
    'TS055TX AK': 'CO055',
    'TS055TX AR': 'CO055',
    'TS055TX AZ1': 'CO055',
    'TS055TX BI': 'CO055',
    'TS055TX BIBE': 'CO055',
    'TS055TX BL': 'CO055',
    'TS055TX NE': 'CO055',
    'TS055TX RO': 'CO055',
    'TS055TX VE': 'CO055',
    'TS055TX VI': 'CO055',
    'TS055TX VN': 'CO055',
    'TS055TX VS': 'CO055',
    'TS070TX AZ1': 'CO170',
    'TS070TX BIBE': 'CO170',
    'TS070TX BIGR': 'CO170',
    'TS070TX GR': 'CO170',
    'TS070TX RO': 'CO170',
    'TS070TX VE': 'CO170',
    'TS070TX VI': 'CO170',
    'TS070TX VN': 'CO170',
    'TS070TX VS': 'CO170',
    'TS070XW BIBE': 'CO170',
    'TS070XW BK': 'CO170',
    'TS070XW NE': 'CO170',
    'TS070XW TA': 'CO170',
    'TS074TX BI': 'CO074',
    'TS074TX BIBE': 'CO074',
    'TS074TX BIGR': 'CO074',
    'TS074TX CO': 'CO074',
    'TS074TX TA': 'CO074',
    'TS118TX BK': 'CO118',
    'TS118TX TA': 'CO118',
    'TS119TX BIBE': 'CO119',
    'TS119TX MB': 'CO119',
    'TS119TX MG': 'CO119',
    'TS119TX VE': 'CO119',
    'TS123PE AR': 'CO123',
    'TS123PE BL': 'CO123',
    'TS123PE NA': 'CO123',
    'TS123PE NE': 'CO123',
    'TS123PE RO': 'CO123',
    'TS123PE TA': 'CO123',
    'TS123PE VS': 'CO123',
    'TS123TX AR': 'CO123',
    'TS123TX BAT': 'CO123',
    'TS123TX BIAQ': 'CO123',
    'TS123TX BIBE': 'CO123',
    'TS123TX BIGR': 'CO123',
    'TS123TX BK': 'CO123',
    'TS123TX BL': 'CO123',
    'TS123TX CO': 'CO123',
    'TS123TX GI': 'CO123',
    'TS123TX GL': 'CO123',
    'TS123TX GR': 'CO123',
    'TS123TX GU': 'CO123',
    'TS123TX MW': 'CO123',
    'TS123TX NE': 'CO123',
    'TS123TX OT': 'CO123',
    'TS123TX RO': 'CO123',
    'TS123TX SE': 'CO123',
    'TS123TX SG': 'CO123',
    'TS123TX TA': 'CO123',
    'TS123TX VN': 'CO123',
    'TS123TXRRIAR': 'CO123',
    'TS123TXRRIVI': 'CO123',
    'TS127PE AR': 'CO127',
    'TS127PE BL': 'CO127',
    'TS127PE NA': 'CO127',
    'TS127PE NE': 'CO127',
    'TS127PE RO': 'CO127',
    'TS127PE TA': 'CO127',
    'TS127PE VS': 'CO127',
    'TS127TX AK': 'CO127',
    'TS127TX AQ': 'CO127',
    'TS127TX AR': 'CO127',
    'TS127TX AZ1': 'CO127',
    'TS127TX B2': 'CO127',
    'TS127TX BAT': 'CO127',
    'TS127TX BI': 'CO127',
    'TS127TX BIAQ': 'CO127',
    'TS127TX BIBE': 'CO127',
    'TS127TX BIGR': 'CO127',
    'TS127TX BK': 'CO127',
    'TS127TX BL': 'CO127',
    'TS127TX BL': 'CO127',
    'TS127TX CO': 'CO127',
    'TS127TX CT': 'CO127',
    'TS127TX GA': 'CO127',
    'TS127TX GC': 'CO127',
    'TS127TX GI': 'CO127',
    'TS127TX GI': 'CO127',
    'TS127TX GR': 'CO127',
    'TS127TX GU': 'CO127',
    'TS127TX LI': 'CO127',
    'TS127TX MW': 'CO127',
    'TS127TX NE': 'CO127',
    'TS127TX OT': 'CO127',
    'TS127TX RIVI': 'CO127',
    'TS127TX RO': 'CO127',
    'TS127TX RS6': 'CO127',
    'TS127TX RS9': 'CO127',
    'TS127TX SE': 'CO127',
    'TS127TX SG': 'CO127',
    'TS127TX TA': 'CO127',
    'TS127TX TJ': 'CO127',
    'TS127TX VB': 'CO127',
    'TS127TX VE': 'CO127',
    'TS127TX VI': 'CO127',
    'TS127TX VN': 'CO127',
    'TS127TX VP': 'CO127',
    'TS127TXRRIAR': 'CO127',
    'TS128PE AG': 'CO128',
    'TS128PE BL': 'CO128',
    'TS128PE NA': 'CO128',
    'TS128PE NE': 'CO128',
    'TS128PE RO': 'CO128',
    'TS128PE TA': 'CO128',
    'TS128PE VS': 'CO128',
    'TS128TX AR': 'CO128',
    'TS128TX BI': 'CO128',
    'TS128TX BIAQ': 'CO128',
    'TS128TX BIBE': 'CO128',
    'TS128TX BIGR': 'CO128',
    'TS128TX BK': 'CO128',
    'TS128TX BL': 'CO128',
    'TS128TX BS': 'CO128',
    'TS128TX CT': 'CO128',
    'TS128TX GA': 'CO128',
    'TS128TX GR': 'CO128',
    'TS128TX GU': 'CO128',
    'TS128TX MG': 'CO128',
    'TS128TX NE': 'CO128',
    'TS128TX OT': 'CO128',
    'TS128TX RIVI': 'CO128',
    'TS128TX RO': 'CO128',
    'TS128TX RS6': 'CO128',
    'TS128TX SE': 'CO128',
    'TS128TX SG': 'CO128',
    'TS128TX TA': 'CO128',
    'TS128TX VE': 'CO128',
    'TS128TX VN': 'CO128',
    'TS128TX VP': 'CO128',
    'TS129JO BI': 'CO129',
    'TS129JO VE': 'CO129',
    'TS129JO ZE': 'CO129',
    'TS129TM AR': 'CO129',
    'TS129TM RO': 'CO129',
    'TS129TM VE': 'CO129',
    'TS129TX AK': 'CO129',
    'TS129TX AR': 'CO129',
    'TS129TX AZ1': 'CO129',
    'TS129TX BAT': 'CO129',
    'TS129TX BI': 'CO129',
    'TS129TX BIAQ': 'CO129',
    'TS129TX BIBE': 'CO129',
    'TS129TX BIBL': 'CO129',
    'TS129TX BIGR': 'CO129',
    'TS129TX BK': 'CO129',
    'TS129TX BL': 'CO129',
    'TS129TX BL2': 'CO129',
    'TS129TX BS': 'CO129',
    'TS129TX CO': 'CO129',
    'TS129TX CT': 'CO129',
    'TS129TX DR': 'CO129',
    'TS129TX GA': 'CO129',
    'TS129TX GC': 'CO129',
    'TS129TX GIRO': 'CO129',
    'TS129TX GR': 'CO129',
    'TS129TX GU': 'CO129',
    'TS129TX LI': 'CO129',
    'TS129TX MC': 'CO129',
    'TS129TX MG': 'CO129',
    'TS129TX MW': 'CO129',
    'TS129TX NE': 'CO129',
    'TS129TX OT': 'CO129',
    'TS129TX RIAR': 'CO129',
    'TS129TX RIVI': 'CO129',
    'TS129TX RO': 'CO129',
    'TS129TX SE': 'CO129',
    'TS129TX SG': 'CO129',
    'TS129TX TA': 'CO129',
    'TS129TX TJ': 'CO129',
    'TS129TX VB': 'CO129',
    'TS129TX VE': 'CO129',
    'TS129TX VI': 'CO129',
    'TS129TX VN': 'CO129',
    'TS129TX VP': 'CO129',
    'TS129TX VS': 'CO129',
    'TS129TXEBIBL': 'CO129',
    'TS129TXIOL': 'CO129',
    'TS130TX AR': 'CO130',
    'TS130TX AZ1': 'CO130',
    'TS130TX BI': 'CO130',
    'TS130TX BIBE': 'CO130',
    'TS130TX BIGR': 'CO130',
    'TS130TX BK': 'CO130',
    'TS130TX CO': 'CO130',
    'TS130TX DR': 'CO130',
    'TS130TX GR': 'CO130',
    'TS130TX MG': 'CO130',
    'TS130TX NE': 'CO130',
    'TS130TX SG': 'CO130',
    'TS130TX SU': 'CO130',
    'TS130TX TA': 'CO130',
    'TS130TX VN': 'CO130',
    'TS130TX VP': 'CO130',
    'TS130TXRRIAR': 'CO130',
    'TS130TXRRIVI': 'CO130',
    'TS132PE RO': 'CO132F',
    'TS132PE TA': 'CO132F',
    'TS132PE VS': 'CO132F',
    'TS132TX AK': 'CO132 ',
    'TS132TX BI': 'CO132 ',
    'TS132TX BIAQ': 'CO132 ',
    'TS132TX BIBE': 'CO132 ',
    'TS132TX BIGR': 'CO132 ',
    'TS132TX NE': 'CO132 ',
    'TS132TX TA': 'CO132 ',
    'TS132TX VN': 'CO132 ',
    'TS132TX VS': 'CO132 ',
    'TS135L  GAVB': 'CO135',
    'TS135L  GIRO': 'CO135',
    'TS135PE AR': 'CO135F',
    'TS135PE BL': 'CO135F',
    'TS135PE NA': 'CO135F',
    'TS135PE NE': 'CO135F',
    'TS135PE RO': 'CO135F',
    'TS135PE TA': 'CO135F',
    'TS135PE VS': 'CO135F',
    'TS135TX AK': 'CO135',
    'TS135TX AR': 'CO135',
    'TS135TX B2': 'CO135',
    'TS135TX BAT': 'CO135',
    'TS135TX BI': 'CO135',
    'TS135TX BIAQ': 'CO135',
    'TS135TX BIBE': 'CO135',
    'TS135TX BIGR': 'CO135',
    'TS135TX BK': 'CO135',
    'TS135TX BS': 'CO135',
    'TS135TX GA': 'CO135',
    'TS135TX GI': 'CO135',
    'TS135TX GR': 'CO135',
    'TS135TX GU': 'CO135',
    'TS135TX MW': 'CO135',
    'TS135TX NE': 'CO135',
    'TS135TX OT': 'CO135',
    'TS135TX RI14': 'CO135',
    'TS135TX SE': 'CO135',
    'TS135TX SG': 'CO135',
    'TS135TX TA': 'CO135',
    'TS135TX TJ': 'CO135',
    'TS135TX VE': 'CO135',
    'TS135TX VI': 'CO135',
    'TS135TX VN': 'CO135',
    'TS135TX VP': 'CO135',
    'TS135TX VS': 'CO135',
    'TS135TXRRIVI': 'CO135',
    'TS145TX AQ': 'CO145',
    'TS145TX BAT': 'CO145',
    'TS145TX BI': 'CO145',
    'TS145TX BIAQ': 'CO145',
    'TS145TX BIBE': 'CO145',
    'TS145TX BIGR': 'CO145',
    'TS145TX BK': 'CO145',
    'TS145TX BL': 'CO145',
    'TS145TX CO': 'CO145',
    'TS145TX DR': 'CO145',
    'TS145TX GA': 'CO145',
    'TS145TX GC': 'CO145',
    'TS145TX GI': 'CO145',
    'TS145TX GL': 'CO145',
    'TS145TX GR': 'CO145',
    'TS145TX GU': 'CO145',
    'TS145TX MC': 'CO145',
    'TS145TX MG': 'CO145',
    'TS145TX NE': 'CO145',
    'TS145TX OT': 'CO145',
    'TS145TX RO': 'CO145',
    'TS145TX SG': 'CO145',
    'TS145TX TA': 'CO145',
    'TS145TX TJ': 'CO145',
    'TS145TX VB': 'CO145',
    'TS145TX VI': 'CO145',
    'TS145TX VN': 'CO145',
    'TS145TX VP': 'CO145',
    'TS145TX VS': 'CO145',
    'TS145TXRRIAR': 'CO145',
    'TS145TXRRIVI': 'CO145',
    'TS145WX BI': 'CO145XW',
    'TS145XW AC': 'CO145XW',
    'TS145XW AR': 'CO145XW',
    'TS145XW BI': 'CO145XW',
    'TS145XW BIAQ': 'CO145XW',
    'TS145XW BIBE': 'CO145XW',
    'TS145XW BIGR': 'CO145XW',
    'TS145XW BK': 'CO145XW',
    'TS145XW BS': 'CO145XW',
    'TS145XW CO': 'CO145XW',
    'TS145XW DR': 'CO145XW',
    'TS145XW GR': 'CO145XW',
    'TS145XW LI': 'CO145XW',
    'TS145XW MC': 'CO145XW',
    'TS145XW OT': 'CO145XW',
    'TS145XW RO': 'CO145XW',
    'TS145XW TA': 'CO145XW',
    'TS145XW VN': 'CO145XW',
    'TS145XW VP': 'CO145XW',
    'TS150PE NA': 'CO150',
    'TS150TX AQ': 'CO150',
    'TS150TX BIGR': 'CO150',
    'TS150TX BL': 'CO150',
    'TS150TX FU': 'CO150',
    'TS150TX RO': 'CO150',
    'TS150TX RS6': 'CO150',
    'TS150TX TA': 'CO150',
    'TS150TX VP': 'CO150',
    'TS150TX VS': 'CO150',
    'TS190PE BL': 'CO190',
    'TS190PE NA': 'CO190',
    'TS190PE VE': 'CO190',
    'TS190PE VS': 'CO190',
    'TS190TX AK': 'CO190',
    'TS190TX AR': 'CO190',
    'TS190TX AZ1': 'CO190',
    'TS190TX BI': 'CO190',
    'TS190TX BIBE': 'CO190',
    'TS190TX BIGR': 'CO190',
    'TS190TX BK': 'CO190',
    'TS190TX BL': 'CO190',
    'TS190TX CO': 'CO190',
    'TS190TX GR': 'CO190',
    'TS190TX GU': 'CO190',
    'TS190TX NE': 'CO190',
    'TS190TX SG': 'CO190',
    'TS190TX TA': 'CO190',
    'TS190TX VE': 'CO190',
    'TS190TX VN': 'CO190',
    'TS190TX VP': 'CO190',
    'TS190TX VS': 'CO190',
    'TS190TXRRIVI': 'CO190',
    'TS205TX AK': 'CO205',
    'TS205TX AR': 'CO205',
    'TS205TX AZ': 'CO205',
    'TS205TX AZ13': 'CO205',
    'TS205TX B2': 'CO205',
    'TS205TX BAT': 'CO205',
    'TS205TX BE': 'CO205',
    'TS205TX BH': 'CO205',
    'TS205TX BI': 'CO205',
    'TS205TX BIAQ': 'CO205',
    'TS205TX BIBE': 'CO205',
    'TS205TX BIBL': 'CO205',
    'TS205TX BIGR': 'CO205',
    'TS205TX BIVE': 'CO205',
    'TS205TX BK': 'CO205',
    'TS205TX BL': 'CO205',
    'TS205TX CO': 'CO205',
    'TS205TX CT': 'CO205',
    'TS205TX GA': 'CO205',
    'TS205TX GC': 'CO205',
    'TS205TX GR': 'CO205',
    'TS205TX GU': 'CO205',
    'TS205TX MW': 'CO205',
    'TS205TX NE': 'CO205',
    'TS205TX OL': 'CO205',
    'TS205TX OT': 'CO205',
    'TS205TX RO': 'CO205',
    'TS205TX RS6': 'CO205',
    'TS205TX SE': 'CO205',
    'TS205TX SG': 'CO205',
    'TS205TX TA': 'CO205',
    'TS205TX TU': 'CO205',
    'TS205TX VE': 'CO205',
    'TS205TX VI': 'CO205',
    'TS205TX VN': 'CO205',
    'TS205TX VS': 'CO205',
    'TS205TXRRIAR': 'CO205',
    'TS205TXRRIVI': 'CO205',
    'TS220L  NA': 'CO220',
    'TS220L  VS': 'CO220',
    'TS220TX AK': 'CO220',
    'TS220TX NE': 'CO220',
    'TS220TX VP': 'CO220',
    'TS223TX BAT': 'CO223',
    'TS223TX BI': 'CO223',
    'TS223TX NE': 'CO223',
    'TS229TX MG': 'CO229',
    'TS230D  BIBE': 'CO230',
    'TS230D  S4': 'CO230',
    'TS230D  S7': 'CO230',
    'TS230L  BL': 'CO230',
    'TS230L  VS': 'CO230',
    'TS230L NA': 'CO230',
    'TS230TX AK': 'CO230',
    'TS230TX BI': 'CO230',
    'TS230TX BK': 'CO230',
    'TS230TX BL': 'CO230',
    'TS230TX GR': 'CO230',
    'TS230TX GU': 'CO230',
    'TS230TX NE': 'CO230',
    'TS230TX RO': 'CO230',
    'TS230TX SG': 'CO230',
    'TS230TX VN': 'CO230',
    'TS230TX VP': 'CO230',
    'TS230TX VS': 'CO230',
    'TS420TX AC': 'CO420',
    'TS420TX AV': 'CO420',
    'TS420TX BI': 'CO420',
    'TS420TX CO': 'CO420',
    'TS420TX LI': 'CO420',
    'TS420TX MG': 'CO420',
    'TS420TX VP': 'CO420',
    'TS550D  BIBE': 'CO550',
    'TS550D  BINE': 'CO550',
    'TS550TX BI': 'CO550',
    'TS550TX BIBE': 'CO550',
    'TS550TX BIGR': 'CO550',
    'TS550TX BL': 'CO550',
    'TS550TX NE': 'CO550',
    'TS550TX TA': 'CO550',
    'TS550TX VN': 'CO550',
    'TS550TX VS': 'CO550',
    'TS552D  BIBE': 'CO552',
    'TS830TX AK': 'CO830',
    'TS830TX AR': 'CO830',
    'TS830TX BI': 'CO830',
    'TS830TX BL': 'CO830',
    'TS830TX GA': 'CO830',
    'TS830TX GU': 'CO830',
    'TS830TX NE': 'CO830',
    'TS830TX TA': 'CO830',
    'TS830TX VE': 'CO830',
    'TS830TX VN': 'CO830',
    'TS830TXRRIAR': 'CO830',
    'TS830TXRRIVI': 'CO830',
    'TS840TX BI': 'CO840',
    'TS840TX BIBE': 'CO840',
    'TS840TX BIGR': 'CO840',
    'TS840TX GR': 'CO840',
    'TS840TX TA': 'CO840',
    'TS900TX BI': 'CO900',
    'TS900TX BIBE': 'CO900',
    'TS900TX BIGR': 'CO900',
    'TS900TX GR': 'CO900',
    'TS900TX NE': 'CO900',
    'TS900TX TA': 'CO900',
    'TS920L  BL': 'CO920',
    'TS930L  NA': 'CO930',
    'TS930L  VS': 'CO930',
    'TS930PE AR': 'CO930',
    'TS930TX AK': 'CO930',
    'TS930TX AR': 'CO930',
    'TS930TX BI': 'CO930',
    'TS930TX BIBE': 'CO930',
    'TS930TX BIGR': 'CO930',
    'TS930TX BL': 'CO930',
    'TS930TX CO': 'CO930',
    'TS930TX GR': 'CO930',
    'TS930TX NE': 'CO930',
    'TS930TX RO': 'CO930',
    'TS930TX SE': 'CO930',
    'TS930TX TA': 'CO930',
    'TS930TX VB': 'CO930',
    'TS930TX VN': 'CO930',
    'TS930TX VS': 'CO930',
    'TS931D  S4': 'CO931',
    'TS931TX BI': 'CO931',
    'TS931TX BIAQ': 'CO931',
    'TS931TX BIGR': 'CO931',
    'TS931TX GR': 'CO931',
    'TS931TX NE': 'CO931',
    'TS931TX TA': 'CO931',
    'TS931TX TJ': 'CO931',
    'TS931TX VB': 'CO931',
}

# -----------------------------------------------------------------------------
# Read configuration parameter:
# -----------------------------------------------------------------------------
# From config file:
cfg_file = os.path.expanduser('./openerp.cfg')

config = ConfigParser.ConfigParser()
config.read([cfg_file])
dbname = config.get('dbaccess', 'dbname')
user = config.get('dbaccess', 'user')
pwd = config.get('dbaccess', 'pwd')
server = config.get('dbaccess', 'server')
port = config.get('dbaccess', 'port')   # verify if it's necessary: getint

# -----------------------------------------------------------------------------
# Connect to ODOO:
# -----------------------------------------------------------------------------
odoo = erppeek.Client(
    'http://%s:%s' % (
        server, port),
    db=dbname,
    user=user,
    password=pwd,
    )

odoo.context = {
    'enable_bom_cost': True,
    'lang': 'it_IT',
    }

# Pool used:
product_pool = odoo.model('product.product')

# -----------------------------------------------------------------------------
# Generate Cocin Database
# -----------------------------------------------------------------------------
cocin_code = tuple(set(cocin_product.values()))
product_ids = product_pool.search([
    ('default_code', 'in', cocin_code),
    ])
cocin_db = {}
for product in product_pool.browse(product_ids):
    cocin_db[product.default_code] = product.bom_total_cost

product_ids = product_pool.search([
    #('default_code', '=ilike', '005TX%'),
    #('inventory_category_id', '=', False),
    ('mx_start_qty', '>', 0),
    ])

not_product_ids = product_pool.search([
    ('mx_start_qty', '<=', 0),
    ])


res = []
for product in product_pool.browse(product_ids):
    cost = product.bom_total_cost
    default_code = product.default_code or ''

    # -------------------------------------------------------------------------
    # Force lavoration on cocin product:
    # -------------------------------------------------------------------------
    if default_code in cocin_product:
        cocin_code = cocin_product[default_code]
        cocin_lavoration = cocin_db.get(cocin_code, 0.0)
    else:
        cocin_code = False
        cocin_lavoration = 0.0
    cost += cocin_lavoration

    # -------------------------------------------------------------------------
    # Force lavoration on hw:
    # -------------------------------------------------------------------------
    if default_code in wf_lavoration:
        lavoration = wf_lavoration[default_code]
    else:
        lavoration = 0.0
    cost += lavoration

    # -------------------------------------------------------------------------

    # -------------------------------------------------------------------------
    # Change temp product (TODO remove)
    # -------------------------------------------------------------------------
    if not cost and default_code in temp:
        cost = temp[default_code]
    # -------------------------------------------------------------------------

    qty = product.mx_start_qty
    if product.inventory_category_id:
        category = product.inventory_category_id.name
    else:
        category = 'NON CATALOGATO'

    res.append((
        product.bom_cost_mode,
        category,

        default_code,
        product.name,
        product.uom_id.name,

        qty,
        cost,
        product.bom_template_id,
        u'%s%s%s' % (
            ('[MANODOPERA: %s]   ' % lavoration) if lavoration else '',
            ('[MANODOPERA: %s=%s]   ' % (cocin_code, cocin_lavoration)
                ) if cocin_code else '',
            product.bom_total_cost_text,
            ),
        product.bom_total_cost_error,
        qty * cost,
        ))

# -----------------------------------------------------------------------------
#                            Excel file:
# -----------------------------------------------------------------------------
# Create WB:
workbooks = {
    'final': ExcelWriter('./prodotti_finito.xlsx', verbose=True),
    'half': ExcelWriter('./semilavorati.xlsx', verbose=True),
    'material': ExcelWriter('./materie_prime.xlsx', verbose=True),
    }

excel_format = {
    'final': {
        'f_title': workbooks['final'].get_format('title'),
        'f_header': workbooks['final'].get_format('header'),
        'f_text': workbooks['final'].get_format('text'),
        'f_number': workbooks['final'].get_format('number'),
        'f_text_red': workbooks['final'].get_format('bg_red'),
        'f_number_red': workbooks['final'].get_format('bg_red_number'),
        },
    'half': {
        'f_title': workbooks['half'].get_format('title'),
        'f_header': workbooks['half'].get_format('header'),
        'f_text': workbooks['half'].get_format('text'),
        'f_number': workbooks['half'].get_format('number'),
        'f_text_red': workbooks['half'].get_format('bg_red'),
        'f_number_red': workbooks['half'].get_format('bg_red_number'),
        },
    'material': {
        'f_title': workbooks['material'].get_format('title'),
        'f_header': workbooks['material'].get_format('header'),
        'f_text': workbooks['material'].get_format('text'),
        'f_number': workbooks['material'].get_format('number'),
        'f_text_red': workbooks['material'].get_format('bg_red'),
        'f_number_red': workbooks['material'].get_format('bg_red_number'),
        },
    }

# Counters:
counters = {
    'final': {},
    'half': {},
    'material': {},
    }

totals = {
    'final': {},
    'half': {},
    'material': {},
    }


# -----------------------------------------------------------------------------
# Utility:
# -----------------------------------------------------------------------------
def get_page(wb_name, ws_name, counters, excel_format):
    """ Get WS page or create if not present
        Add also header
        wb_name: Name of workbook (3 mode: final, half, material)
        ws_name: Sheet description
        counters: counter for 3 modes
        excel_format: format for 3 modes
    """
    if ws_name not in counters[wb_name]: # Create:
        # Add worksheet:
        workbooks[wb_name].create_worksheet(ws_name)

        # Setup columns:
        workbooks[wb_name].column_width(ws_name, (
            # 15,
            15, 40, 20, 4,
            11, 11, 11,
            50, 5, 15, 15,
            ))

        # Setup header title:
        counters[wb_name][ws_name] = 2 # Current line
        workbooks[wb_name].write_xls_line(
            ws_name, counters[wb_name][ws_name], (
                #u'Catalogo',
                u'Codice', u'Name', u'Modello ind.', u'UM',
                u'Q.', u'Costo', u'Costo modello',
                u'Dettaglio', u'Errore', u'Subtotale', u'Subtotale modello',
                ), excel_format[wb_name]['f_header'])
        counters[wb_name][ws_name] += 1
        totals[wb_name][ws_name] = [0.0, 0.0] # Total page (normal, template)

    return (
        workbooks[wb_name],  # WS
        counters[wb_name][ws_name],  # Counter
        )


for product in sorted(res):
    wb_name = product[0]
    ws_name = product[1]

    template = product[7]
    subtotal_bom = product[10]
    if template:
        template_name = template.default_code
        industrial = template.from_industrial
        subtotal_industrial = product[5] * industrial
    else:
        template_name = ''
        industrial = ''
        subtotal_industrial = ''

    if product[9]: # Error:
        text = excel_format[wb_name]['f_text_red']
        number = excel_format[wb_name]['f_number_red']
    else:
        text = excel_format[wb_name]['f_text']
        number = excel_format[wb_name]['f_number']

    Excel, row = get_page(wb_name, ws_name, counters, excel_format)

    Excel.write_xls_line(ws_name, row, (
        #product[1], # Category
        product[2], # Code
        product[3], # Name
        template_name, # Template
        product[4], # UOM

        (product[5], number), # stock qty
        (product[6], number), # unit cost
        (industrial, number), # industrial

        product[8],
        'X' if product[9] else ' ',
        (subtotal_bom, number),
        (subtotal_industrial, number),
        ), text)
    counters[wb_name][ws_name] += 1
    totals[wb_name][ws_name][0] += subtotal_bom or 0.0
    totals[wb_name][ws_name][1] += subtotal_industrial or 0.0

# -----------------------------------------------------------------------------
# Write total page:
# -----------------------------------------------------------------------------
ws_name = 'TOTALI'
for wb_name in totals:
    Excel = workbooks[wb_name]
    text = excel_format[wb_name]['f_text']
    number = excel_format[wb_name]['f_number']

    # Add total page:
    row = 0
    workbooks[wb_name].create_worksheet(ws_name)
    workbooks[wb_name].column_width(ws_name, (40, 15, 15))
    workbooks[wb_name].write_xls_line(
        ws_name, row, (
            u'Categoria', u'Totale DB', u'Totale industriale'),
            excel_format[wb_name]['f_header'])

    for category in totals[wb_name]:
        row += 1
        subtotal_bom = totals[wb_name][category][0]
        subtotal_industrial = totals[wb_name][category][1]
        # Write total in Total page:
        Excel.write_xls_line(ws_name, row, (
            category,
            (subtotal_bom, number),
            (subtotal_industrial, number),
            ), text)

        # Write total in sheet:
        workbooks[wb_name].write_xls_line(
            category, 0, (
                u'Totale categoria', '', '', '', '', '', '', '', '',
                (subtotal_bom, number),
                (subtotal_industrial, number),
                ), text)

# -----------------------------------------------------------------------------
# Write not included:
# -----------------------------------------------------------------------------
ws_name = 'Non inclusi'
Excel = ExcelWriter('./non_presenti.xlsx', verbose=True)

# Add total page:
row = 0
Excel.create_worksheet(ws_name)
Excel.column_width(ws_name, (30, 15, 40))
Excel.write_xls_line(ws_name, row, (u'Categoria', u'Codice', u'Nome'))

for product in sorted(
        product_pool.browse(not_product_ids),
        key=lambda x: (
            x.inventory_category_id.name if x.inventory_category_id else '',
            x.default_code)):
    row += 1
    Excel.write_xls_line(ws_name, row, (
        product.inventory_category_id.name if product.inventory_category_id \
            else 'NON ASSEGNATA',
        product.default_code or '',
        product.name,
        ))

del(Excel)
del(workbooks['final'])
del(workbooks['half'])
del(workbooks['material'])
