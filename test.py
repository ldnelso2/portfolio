import unittest
import uuid

from portfolio import CashFlow

class TestCashFlow(unittest.TestCase):

    def test_can_create(self):
        cf_kwargs = {
            'delay_qtrs': 2,
            'discount_rate': .5,
            'is_cost': False,
            'max_amt': .4,
            'scale_up_qtrs': 4,
            'function': 'linear',
            'name': 'Test Profile',
            'discounted': False,
        }
        cf = CashFlow(**cf_kwargs)
        self.assertIsInstance(cf, CashFlow)
        

if __name__ == '__main__':
    unittest.main()
