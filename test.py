import unittest
import uuid

from portfolio import CashFlow

class TestCashFlow(unittest.TestCase):

    def test_can_create_instance(self):
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
    
    def test_linear_cash_flow(self):
        cf = CashFlow(
            delay_qtrs=2, discount_rate=.5, is_cost=False, max_amt=10,
            scale_up_qtrs=4, function='linear', name='Test Profile',
            discounted=False, tot_qtrs=8
        )
        self.assertListEqual(cf.qtr, [
            0,  # delayed
            0,  # delayed
            0.0,  # scaling
            2.5,  # scaling
            5.0,  # scaling
            7.5,  # scaling
            10.0, # reach max
            10  # max value
        ])

    @unittest.skip('not implemented')
    def test_sigmoid_cash_flow(self):
        pass


if __name__ == '__main__':
    unittest.main()
