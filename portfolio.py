import uuid
from functools import wraps
import math

import matplotlib.pyplot as plt

from utils import Cell, SmartsheetRow

class CashFlow():
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
                 function, start_amt=0, name='', flow_id=uuid.uuid4(), tot_qtrs=12):
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
        self.tot_qtrs = tot_qtrs  # TODO: rename to "period"
        
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
 
    def _discounted(self, f):
        @wraps(f)
        def discounted_wrapper(quarter_n, max_amt, start_amt):
            return f(quarter_n, max_amt, start_amt) / (1 + self.discount_rate) ** quarter_n

        return discounted_wrapper
    
    def _calculate_qtr(self, f, discounted):
        values = []
        discounted_f = self._discounted(f) if discounted else f
        for quarter_n in range(0, self.tot_qtrs):
            if quarter_n < self.delay_qtrs:
                values.append(0)
            else:
                multiplier = -1 if self.is_cost else 1
                amt = discounted_f(quarter_n, self.max_amt, self.start_amt)
                values.append(multiplier * amt + self.start_amt)
        return values

    def _calculate_dg_qtr(self, f, discounted):
        """calculates digital gallons per quarter"""
        values = []
        discounted_f = self._discounted(f) if discounted else f
        for quarter_n in range(0, self.tot_qtrs):
            if quarter_n < self.delay_qtrs:
                values.append(0)
            else:
                start_gallons = 0
                values.append(discounted_f(quarter_n, self.digital_gallons, start_gallons))
        return values

    def quick_view(self, discounted=True):
        fig = plt.figure()
        ax = fig.add_subplot(1, 1, 1)
        x_labels = quarter_labels = ['Q' + str(q) for q in range(1, self.tot_qtrs + 1)]
        ax.plot(x_labels, self.sigmoid_qtr(discounted=discounted), label='sigmoid')
        ax.plot(x_labels, self.linear_qtr(discounted=discounted), label='linear')
        ax.plot(x_labels, self.step_qtr(discounted=discounted), label='step')
        ax.scatter(x_labels, self.single_qtr(discounted=discounted), label='single')
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
    CELL_01 = Cell(1, 'fte', False)
    CELL_02 = Cell(2, 'fte_unallocated', False)
    CELL_03 = Cell(3, 'fte_other', False)
    CELL_04 = Cell(4, 'include_in_model', True)
    CELL_05 = Cell(5, 'project_code', True)
    CELL_06 = Cell(6, 'annual_revenue', False)
    CELL_07 = Cell(7, 'gross_profit_perc', False)
    CELL_08 = Cell(8, 'attribution_perc', False)
    CELL_09 = Cell(9, 'is_cost', True)
    CELL_10 = Cell(10, 'function', True)
    CELL_11 = Cell(11, 'discount_rate', True)
    CELL_12 = Cell(12, 'start_value', True)
    CELL_13 = Cell(13, 'delay_qtrs', True)
    CELL_14 = Cell(14, 'max_amt', True)
    CELL_15 = Cell(15, 'scale_up_qtrs', True)
    CELL_16 = Cell(16, 'max_plants', False)
    CELL_17 = Cell(17, 'digital_gallons', True)
    CELL_16 = Cell(18, 'comments', False)
    
    def __init__(self, row):
        # Extra logic is used to decide if row should be processed at all
        # This allows us to "fail fast" when a row we want to parse doesn't have the data we want
        cells = row['cells']
        include = cells[PortfolioSheetRow.CELL_04.index].get('value', None)
        self.project_code = cells[PortfolioSheetRow.CELL_05.index].get('value', None)
        self.include_in_model = True if include == "Yes" else False
        
        if self.include_in_model and self.project_code:
            super().__init__(row)
        
    @staticmethod
    def _function(val):
        text = val.strip().lower()
        if text == 'continuous' or text == 'step':
            return 'step'
        elif text == 'single pmt.':
            return 'single'
        elif text == 'logistic':
            return 'sigmoid'
        elif text == 'linear':
            return 'linear'
        else:
            raise Exception(f'Unknown profile type: {val}')
    
    @staticmethod
    def _include_in_model(val):
        return val.lower() == 'yes'

    @staticmethod
    def _is_cost(val):
        return val.lower() == 'cost'

    
def debug_row(row_num, sheet):
    """Very quickly see how the parser parses and outputs any single row"""
    row = sheet.rows[row_num - 1]
    r = PortfolioSheetRow(row.to_dict())
    blacklisted = [
        '__', 'cell_defs', 'CELL', 'cells', 'sheet_row', '_get_cell',
        '_identity', '_profile_type', 'row_number', '_include'
    ]
    for a in dir(r):
        if any([s in a for s in blacklisted]):
            continue
        print(a + '\t\t\t' + str(getattr(r, a)))
