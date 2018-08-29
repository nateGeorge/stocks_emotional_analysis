# from concurrent.futures import ProcessThread
import sys
sys.path.append('../../stock_prediction/code')
import dl_quandl_EOD as dlq
dfs = dlq.load_stocks()
