import unittest
import uuid

from collections import namedtuple

from portfolio import CashFlow


Point = namedtuple('Point', ['x', 'y'])

class TestCashFlow(unittest.TestCase):
    def setUp(self):
        self.delay_qtrs = 2
        self.scale_up_qtrs = 4
        self.start_amt = 1
        self.max_amt = 5
        self.cf = CashFlow(
            delay_qtrs=self.delay_qtrs, digital_gallons=5, discount_rate=.1, function='sigmoid',
            is_cost=False, start_amt=self.start_amt, max_amt=self.max_amt, scale_up_qtrs=self.scale_up_qtrs,
            tot_qtrs=8, name='test'
        )
        self.update_points()

    def update_points(self):
        self.start_scale_point = Point(self.delay_qtrs, self.start_amt)
        self.mid_scale_point = Point(
            self.delay_qtrs + self.scale_up_qtrs // 2,
            self.start_amt + (self.max_amt - self.start_amt) / 2
        )
        self.end_scale_point = Point(self.delay_qtrs + self.scale_up_qtrs, self.max_amt)
        # Since the sigmoid is written to hit poits at 95% of value, it's off by 5%
        self.sigmoid_correction = (self.max_amt - self.start_amt) * .05

    def set_prop(self, attr, value):
        """Updates `delay_qtrs` and other instance attrs, also updates CashFlow instance"""
        setattr(self, attr, value)
        setattr(self.cf, attr, value)
        self.update_points()

    def test_can_create_instance(self):
        self.assertIsInstance(self.cf, CashFlow)
    
    def test_key_points_linear(self):
        qtr = self.cf.linear_qtr(discounted=False)
        self.assertEqual(qtr[self.start_scale_point.x], self.start_scale_point.y)
        self.assertEqual(qtr[self.mid_scale_point.x], self.mid_scale_point.y)
        self.assertEqual(qtr[self.end_scale_point.x], self.end_scale_point.y)

        self.set_prop('start_amt', 0)
        qtr = self.cf.linear_qtr(discounted=False)
        self.assertEqual(qtr[self.start_scale_point.x], self.start_scale_point.y)
        self.assertEqual(qtr[self.mid_scale_point.x], self.mid_scale_point.y)
        self.assertEqual(qtr[self.end_scale_point.x], self.end_scale_point.y)

    def test_key_points_sigmoid(self):
        qtr = self.cf.sigmoid_qtr(discounted=False)
        start_y = self.start_scale_point.y + self.sigmoid_correction
        end_y = self.end_scale_point.y - self.sigmoid_correction
        self.assertAlmostEqual(qtr[self.start_scale_point.x], start_y)
        self.assertEqual(qtr[self.mid_scale_point.x], self.mid_scale_point.y)
        self.assertAlmostEqual(qtr[self.end_scale_point.x], end_y)

        self.set_prop('start_amt', 0)
        qtr = self.cf.sigmoid_qtr(discounted=False)
        start_y = self.start_scale_point.y + self.sigmoid_correction
        end_y = self.end_scale_point.y - self.sigmoid_correction
        self.assertAlmostEqual(qtr[self.start_scale_point.x], start_y)
        self.assertEqual(qtr[self.mid_scale_point.x], self.mid_scale_point.y)
        self.assertAlmostEqual(qtr[self.end_scale_point.x], end_y)

if __name__ == '__main__':
    unittest.main()
