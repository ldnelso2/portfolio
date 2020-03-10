import uuid
from functools import wraps
import math

import matplotlib.pyplot as plt
import numpy as np

from utils import Cell, SmartsheetRow


def discount(val, discount_rate, period_n):
    return val / ((1 + discount_rate) ** period_n)


class CashFlowBase():
    """Ensure all children implement the following methods"""

    @property
    def non_discounted_qtr(self):
        raise NotImplementedError
        
    @property
    def discounted_qtr(self):
        raise NotImplementedError
        
    @property
    def non_discounted_dg_qtr(self):
        raise NotImplementedError
        
    @property
    def discounted_dg_qtr(self):
        raise NotImplementedError

    @property
    def non_discounted_vc_qtr(self):
        raise NotImplementedError

    @property
    def discounted_vc_qtr(self):
        raise NotImplementedError

    @property
    def to_json(self):
        raise NotImplementedError


class CashFlow(CashFlowBase):
    """Generate a cash flow profile based on key assumptions
    
    Args:
        delay_qtrs (int): Delay until cash flow starts to take effect
        discount_rate (float): Discount rate used in discounted cash
            flow calculations.
        is_cost (boolean): Whether cash flow profile is a cost or not
        max_amt (float): Unitless amount that profile can scale up to
        scale_up_qtrs (int): How many quarters it takes to scale up a cash
            flow.
        function (string): Profile type of cash flow
    
    Keyword arguments:
        start_amt (float): Unitless amont that profile stars at after delay
            period.
        name (string): Descriptive name of the cash flow (default '')
        flow_id (UUID): A unique identifier for the cash flow. This is only
            important deletes become a thing (default UUID).
        tot_qtrs (int): Total number of quarters the profile will run over.
            Essentially dictates the length of the resulting data output
            (default 12).

    Returns:
        CashFlow instance
        
    TODO:
        * `discount_rate` should not be required if `discounted` is `False`
        * `discounted` attritubte should exist, but be private. `qtr` should also
          be private (_qtr). The idea of a cash flow holding state is a flaw.
        * args/kwargs should be validated
        * function profile types should be class attributes, e.g. CashFlow.SIGMOIDs
    """
    def __init__(self, delay_qtrs, digital_gallons, discount_rate, is_cost, max_amt, scale_up_qtrs,
                 function, vc_per_dg, start_amt=0, name='', flow_id=uuid.uuid4(), tot_qtrs=12):
        if scale_up_qtrs < 2: 
            raise Exception('the total number of quarters must be at least one')

        self.delay_qtrs = delay_qtrs
        self.digital_gallons = digital_gallons
        self.discount_rate = discount_rate / 4 # annual discount rate -> quarterly
        self.function = function # Will interpret an instance according to this setting
        self.id = flow_id
        self.is_cost = is_cost
        self.max_amt = max_amt
        self.name = name
        self.scale_up_qtrs = scale_up_qtrs
        self.start_amt = start_amt
        self.vc_per_dg = vc_per_dg
        self.tot_qtrs = tot_qtrs  # TODO: rename to "period"
        self.periods = list(range(1, tot_qtrs + 1))
        self.periods_index = list(range(tot_qtrs))
        self.periods_labels = ['Q' + str(q) for q in range(1, self.tot_qtrs + 1)]

    def _sigmoid(self, x, max_amt, start_amt):
        """
        We define y at 95% max at end of delay and scale up period 
        y = .95L = L / (1 + e^-k(x_end - x_naught)) # https://en.wikipedia.org/wiki/Logistic_function
        For us, this means the scaling factor (k) is
        k = ln(1/.95 - 1)/((delay_qtrs + scale_up_qtrs/2) - (delay_qtrs + scale_up_qtrs))
        """
        # 1 / 2 scale_up_qtrs to place x_naught at vertical of sigmoid from after delay
        x_naught = self.delay_qtrs + self.scale_up_qtrs / 2
        x_end = self.delay_qtrs + self.scale_up_qtrs
        k = math.log(1/.95 - 1) / (x_naught - x_end)
        return min((max_amt - start_amt) / (1 + math.exp(-k * (x - x_naught))), (max_amt - start_amt))
    
    def _linear(self, x, max_amt, start_amt):
        """y = mx + b. Units in amount (returned value) per quarter (x)"""
        m = (max_amt - start_amt) / self.scale_up_qtrs
        b = -m * self.delay_qtrs
        return min(m * x + b, max_amt - start_amt) # Never return more than max
    
    def _single(self, x, max_amt, start_amt):
        if x == self.delay_qtrs:
            return max_amt - start_amt
        else:
            return -1 * start_amt
    
    def _step(self, x, max_amt, start_amt):
        return max_amt - start_amt
    
    def _discounted(self, val, period_n):
        return discount(val, self.discount_rate, period_n)
 
    def _calculate_qtr(self, f, discounted):
        values = []
        for quarter_n in self.periods_index:
            if quarter_n < self.delay_qtrs:
                values.append(0)
            else:
                multiplier = -1 if self.is_cost else 1
                amt = f(quarter_n, self.max_amt, self.start_amt) + self.start_amt
                amt = multiplier * amt
                if discounted:
                    amt = self._discounted(amt, quarter_n)

                values.append(amt)
        return values

    def _calculate_dg_qtr(self, f, discounted):
        """calculates digital gallons per quarter"""
        values = []
        for quarter_n in self.periods_index:
            if quarter_n < self.delay_qtrs:
                values.append(0)
            else:
                start_gallons = 0
                amt = f(quarter_n, self.digital_gallons, start_gallons)
                if discounted:
                    amt = self._discounted(amt, quarter_n)

                values.append(amt)
        return values

    def _calculate_vc_qtr(self, discounted):
        """calculate the variable cost based on digital gallons
        """
        unit_multiplier = 10**6  # put in dollars
        dg_to_variable_cost = lambda v: -1 * v * unit_multiplier * self.vc_per_dg
        variable_cost = [0]  # No variable cost at Q0
        cf_attribute = 'discounted_dg_qtr' if discounted else 'non_discounted_dg_qtr'
        dg_cost = list(map(dg_to_variable_cost, getattr(self, cf_attribute)))

        # iterable is of form [(0, (0, 1)), (1, (1, 2)), (n, (n + 1))]
        for index, step in list(enumerate(zip(self.periods_index, self.periods)))[:-1]:
            # integraing using trapezoidal riemann sum
            step_vc = np.trapz([dg_cost[index], dg_cost[index + 1]], step)
            variable_cost.append(step_vc)

        return variable_cost

    def quick_view(self, discounted=True):
        fig = plt.figure()
        fig.patch.set_facecolor('#ffffff')
        ax = fig.add_subplot(1, 1, 1)
        ax.plot(self.periods_labels, self.sigmoid_qtr(discounted=discounted), label='sigmoid')
        ax.plot(self.periods_labels, self.linear_qtr(discounted=discounted), label='linear')
        ax.plot(self.periods_labels, self.step_qtr(discounted=discounted), label='step')
        ax.scatter(self.periods_labels, self.single_qtr(discounted=discounted), label='single')
        # mark key axis positions for start value, delay, ramp, max value, etc
        ax.axvline(x=self.delay_qtrs, color='black', linestyle='--', linewidth=2)
        ax.axvline(x=self.scale_up_qtrs + self.delay_qtrs, color='black', linestyle='--', linewidth=2)
        ax.axvline(x=self.delay_qtrs + self.scale_up_qtrs / 2, color='b', linestyle='--', linewidth=1)
        ax.axhline(y=self.start_amt, color='black', linestyle='--', linewidth=2)
        ax.axhline(y=self.start_amt + (self.max_amt - self.start_amt) / 2, color='b', linestyle='--', linewidth=1)
        ax.axhline(y=self.max_amt, color='black', linestyle='--', linewidth=2)
        ax.legend(loc='upper left')
        ax.grid(True)
    
    def _qtr(self, discounted):
        """calculates quarter for instance based on set function type"""
        return self._calculate_qtr(getattr(self, f'_{self.function.lower()}'), discounted)

    def _dg_qtr(self, discounted):
        """calculates quarter values for digital gallons"""
        return self._calculate_dg_qtr(getattr(self, f'_{self.function.lower()}'), discounted)

    @property
    def non_discounted_qtr(self):
        return self._qtr(False)

    @property
    def discounted_qtr(self):
        """returns cash flow profile, ignoring discounted"""
        return self._qtr(True)

    @property
    def non_discounted_dg_qtr(self):
        return self._dg_qtr(False)
    
    @property
    def discounted_dg_qtr(self):
        return self._dg_qtr(True)

    @property
    def non_discounted_vc_qtr(self):
        return self._calculate_vc_qtr(False)

    @property
    def discounted_vc_qtr(self):
        return self._calculate_vc_qtr(True)

    def sigmoid_qtr(self, discounted=True):
        """returns cash flow profile with a sigmoid profile, ignoring "function" attribute"""
        return self._calculate_qtr(self._sigmoid, discounted)

    def linear_qtr(self, discounted=True):
        """returns cash flow profile with a linear profile, ignoring "function" attribute"""
        return self._calculate_qtr(self._linear, discounted)
    
    def step_qtr(self, discounted=True):
        """returns cash flow profile with a step profile, ignoring "function" attribute"""
        return self._calculate_qtr(self._step, discounted)
    
    def single_qtr(self, discounted=True):
        """returns cash flow profile with a one-time amounts, ignoring "function" attribute"""
        return self._calculate_qtr(self._single, discounted)

    def sigmoid_dg_qtr(self, discounted=True):
        """returns digital gallon profile with a sigmoid profile, ignoring "function" attribute"""
        return self._calculate_dg_qtr(self._sigmoid, discounted)

    def linear_dg_qtr(self, discounted=True):
        """returns digital gallon profile with a linear profile, ignoring "function" attribute"""
        return self._calculate_dg_qtr(self._linear, discounted)

    def step_dg_qtr(self, discounted=True):
        """returns digital gallon profile with a step profile, ignoring "function" attribute"""
        return self._calculate_dg_qtr(self._step, discounted)

    def single_dg_qtr(self, discounted=True):
        """returns digital gallon profile with a one-time amounts, ignoring "function" attribute"""
        return self._calculate_dg_qtr(self._single, discounted)
    
    def to_json(self):
        return {
            "delay_qtrs": self.delay_qtrs,
            "digital_gallons": self.digital_gallons,
            "discount_rate": self.discount_rate,
            "flow_id": str(self.id),
            "function": self.function,
            "is_cost": self.is_cost,
            "name": self.name,
            "start_amt": self.start_amt,
            "max_amt": self.max_amt,
            "scale_up_qtrs": self.scale_up_qtrs,
            "tot_qtrs": self.tot_qtrs,
        }


class FTECashFlow(CashFlowBase):
    def __init__(self, discount_rate, fte_per_period, fte_period_cost, fte_y1, fte_y2, fte_y3, name, flow_id=uuid.uuid4()):
        self.name = name
        self.id = flow_id
        self.discount_rate = discount_rate
        self.fte_per_period = fte_per_period
        self.fte_period_cost = fte_period_cost
        self.fte_y1 = fte_y1
        self.fte_y2 = fte_y2
        self.fte_y3 = fte_y3
        self.is_cost = True
        self.multiplier = -1 if self.is_cost else 1

    @property
    def discounted_qtr(self):
        return [
            self.multiplier * discount(
                self.fte_period_cost * period_fte,
                self.discount_rate,
                period
            ) for period, period_fte in enumerate(self.fte_per_period)
        ]

    @property
    def non_discounted_qtr(self):
        return [self.multiplier * self.fte_period_cost * period_fte for period_fte in self.fte_per_period]

    @property
    def non_discounted_dg_qtr(self):
        return [0 for _ in range(12)]
    
    @property
    def discounted_dg_qtr(self):
        return [0 for _ in range(12)]

    @property
    def non_discounted_vc_qtr(self):
        return [0 for _ in range(12)]

    @property
    def discounted_vc_qtr(self):
        return [0 for _ in range(12)]

    def to_json(self):
        return {
            "name": self.name,
            "discount_rate": self.discount_rate,
            "fte_y1": self.fte_y1,
            "fte_y2": self.fte_y2,
            "fte_y3": self.fte_y3,
            "flow_id": str(self.id)
        }
    
    
def combine_flows(flows, attribute):
    values = map(lambda cf: getattr(cf, attribute), flows)
    aggregated_values = [sum(values) for values in zip(*values)]
    return aggregated_values


class PortfolioSheetRow(SmartsheetRow):
    """All cells that are desired MUST have a class attribute defined where:
       "CELL_" is part of the name. The class will use those attributes to parse the row.
       
       Any methods defined with the same "name" as the attribute preceeded by an underscore
       will apploy that function to the attribute as a clean way to modify the value if necessary.
    """
    CELL_00 = Cell(0, 'name', True)
    CELL_01 = Cell(1, 'scenario', False)
    CELL_02 = Cell(2, 'fte', False)
    CELL_03 = Cell(3, 'fte_unallocated', False)
    CELL_04 = Cell(4, 'fte_other', False)
    CELL_05 = Cell(5, 'fte_y1', False)
    CELL_06 = Cell(6, 'fte_y2', False)
    CELL_07 = Cell(7, 'fte_y3', False)
    CELL_08 = Cell(8, 'include_in_model', True)
    CELL_09 = Cell(9, 'project_code', True)
    CELL_10 = Cell(10, 'annual_revenue', False)
    CELL_11 = Cell(11, 'gross_profit_perc', False)
    CELL_12 = Cell(12, 'attribution_perc', False)
    CELL_13 = Cell(13, 'is_cost', True)
    CELL_14 = Cell(14, 'function', True)
    CELL_15 = Cell(15, 'discount_rate', True)
    CELL_16 = Cell(16, 'start_value', True)
    CELL_17 = Cell(17, 'delay_qtrs', True)
    CELL_18 = Cell(18, 'max_amt', True)
    CELL_19 = Cell(19, 'scale_up_qtrs', True)
    CELL_20 = Cell(20, 'max_plants', False)
    CELL_21 = Cell(21, 'digital_gallons', True)
    CELL_22 = Cell(22, 'comments', False)

    def __init__(self, row):
        self.amt_unit_conversion = 10**6 # covert from millions to dollars
        self.periods_in_year = 4
        super().__init__(row)
        
    def _discount_rate(self, val):
        """By convention, discount rates are expressed in annualized terms. Convert to period"""
        return val / self.periods_in_year
        
    @staticmethod
    def _function(val):
        text = val.strip().lower()
        # TODO: replace returns with FUNCTION.SIGMOID type class attributes
        if text == 'continuous' or text == 'step':
            return 'step'
        elif text == 'single pmt.':
            return 'single'
        elif text == 'logistic':
            return 'sigmoid'
        elif text == 'linear':
            return 'linear'
        elif text == 'multi-step (yr)':
            raise Exception('Should be using PortfolioFTEParser, there is a bug in code')
        else:
            raise Exception(f'Unknown profile type: {val}')
    
    @staticmethod
    def _include_in_model(val):
        return val.lower() == 'yes'

    @staticmethod
    def _is_cost(val):
        return val.lower() == 'cost'

    def _max_amt(self, val):
        return (val * self.amt_unit_conversion) / 4

    def _start_value(self, val):
        return (val * self.amt_unit_conversion) / 4


class PortfolioFTEParser(SmartsheetRow):
    CELL_00 = Cell(0, 'name', True)
    CELL_05 = Cell(5, 'fte_y1', True)
    CELL_06 = Cell(6, 'fte_y2', True)
    CELL_07 = Cell(7, 'fte_y3', True)
    CELL_09 = Cell(9, 'project_code', True)
    CELL_15 = Cell(15, 'discount_rate', True)

    def __init__(self, row, periods_in_year=4):
        self.amt_unit_conversion = 10**6 # covert from millions to dollars
        self.periods_in_year = periods_in_year
        super().__init__(row)
        self.fte_per_period = [self.fte_y1 for _ in range(self.periods_in_year)] + \
                          [self.fte_y2 for _ in range(self.periods_in_year)] + \
                          [self.fte_y3 for _ in range(self.periods_in_year)]
        
    def _discount_rate(self, val):
        """By convention, discount rates are expressed in annualized terms. Convert to period"""
        return val / self.periods_in_year

    def _fte_y1(self, val):
        return val * self.amt_unit_conversion
    
    def _fte_y2(self, val):
        return val * self.amt_unit_conversion

    def _fte_y3(self, val):
        return val * self.amt_unit_conversion

    
def debug_row(row_num, sheet, cb=None):
    """Very quickly see how the parser parses and outputs any single row"""
    row = sheet.rows[row_num - 1]
    print('--------------------------------------')
    r = PortfolioFTEParser(row.to_dict())
    print('--------------------------------------')
    desc_list = [f'{i} - {cell}' for i, cell in enumerate(row.to_dict()['cells'])]
    for line in desc_list:
        print(line)
    print('--------------------------------------')
    return r
