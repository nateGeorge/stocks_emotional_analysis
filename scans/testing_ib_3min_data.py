import sys
sys.path.append('../stocktwits/')

import scan_utils as su
import get_st_data as gt

trades_3mins = gt.load_ib_data('TSLA', timeframe='3 mins')
