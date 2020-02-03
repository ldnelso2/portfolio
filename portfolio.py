import uuid
from functools import wraps
import math

from utils import Cell, SmartsheetRow

class CashFlow():
    """Generate a cash flow profile based on key assumptions
    
    Args:
        delay_qtrs (int): Delay until cash flow starts to take effect
        discount_rate (float): Discount rate used in discounted cash
            flow calculations
        is_cost (boolean): Whether cash flow profile is a cost or not
        max_amt (float): Unitless amount that profile can scale up to
        scale_up_qtrs (int): How many quarters it takes to scale up a cash
            flow.
        function (string): Profile type of cash flow
    
    Keyword arguments:
        name (string): Descriptive name of the cash flow (default '')
        discounted (boolean): Whether or not `.qtr` will return a discounted
            profile (default: True).
        flow_id (UUID): A unique identifier for the cash flow. This is only
            important deletes become a thing (default UUID).
        tot_qtrs (int): Total number of quarters the profile will run over.
            Essentially dictates the length of the resulting data output
            (default 12).

    Returns:
        CashFlow instance
        
    TODO:
        * `discount_rate` should not be required if `discounted` is `False`
        * args/kwargs should be validated
        * function profile types should be class attributes, e.g. CashFlow.SIGMOIDs
    """
    def __init__(self, delay_qtrs, discount_rate, is_cost, max_amt, scale_up_qtrs,
                 function, name='', discounted=True, flow_id=uuid.uuid4(), tot_qtrs=12):
        if scale_up_qtrs < 2: 
            raise Exception('the total number of quarters must be at least one')

        self.delay_qtrs = delay_qtrs
        self.discounted = discounted
        self.discount_rate = discount_rate / 4 # annual discount rate -> quarterly
        self.function = function # Will interpret an instance according to this setting
        self.id = flow_id
        self.is_cost = is_cost
        self.max_amt = max_amt
        self.name = name
        self.scale_up_qtrs = scale_up_qtrs
        self.tot_qtrs = tot_qtrs  # TODO: rename to "period"
        
    def _sigmoid(self, x):
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
        return self.max_amt / (1 + math.exp(-k * (x - x_naught)))
    
    def _linear(self, x):
        """y = mx + b. Units in amount (returned value) per quarter (x)"""
        m = self.max_amt / self.scale_up_qtrs
        b = -m * self.delay_qtrs
        return min(m * x + b, self.max_amt) # Never return more than max
    
    def _single(self, x):
        if x == self.delay_qtrs:
            return self.max_amt
        else:
            return 0
    
    def _step(self, x):
        return self.max_amt
 
    def _discounted(self, f):
        @wraps(f)
        def discounted_wrapper(quarter_n):
            return f(quarter_n) / (1 + self.discount_rate) ** quarter_n

        return discounted_wrapper
    
    def _calculate_qtr(self, f):
        values = []
        discounted_f = self._discounted(f) if self.discounted else f
        for quarter_n in range(0, self.tot_qtrs):
            if quarter_n < self.delay_qtrs:
                values.append(0)
            else:
                multiplier = -1 if self.is_cost else 1
                # TODO: multiply by -1 here if it is a COST we are considering
                values.append(multiplier * discounted_f(quarter_n))
        return values

    def quick_view(self):
        fig = plt.figure()
        ax = fig.add_subplot(1, 1, 1)
        ax.plot(range(self.tot_qtrs), self.sigmoid_qtr, label='sigmoid')
        ax.plot(range(self.tot_qtrs), self.linear_qtr, label='linear')
        ax.plot(range(self.tot_qtrs), self.step_qtr, label='step')
        ax.scatter(range(self.tot_qtrs), self.single_qtr, label='single')
        ax.legend(loc='upper left')
        ax.grid(True)
    
    @property
    def qtr(self):
        """calculates quarter for instance based on set function type"""
        return self._calculate_qtr(getattr(self, f'_{self.function.lower()}'))

    @property
    def discounted_qtr(self):
        """returns cash flow profile, ignoring discounted"""
        discounted = self.discounted
        self.discounted = True
        qtr = self.qtr
        self.discounted = discounted
        return qtr

    @property
    def non_discounted_qtr(self):
        """returns cash flow profile, ignoring discounted"""
        discounted = self.discounted
        self.discounted = False
        qtr = self.qtr
        self.discounted = discounted
        return qtr
    
    @property
    def sigmoid_qtr(self):
        """returns cash flow profile with a sigmoid profile, ignoring "function" attribute"""
        return self._calculate_qtr(self._sigmoid)
    
    @property
    def linear_qtr(self):
        """returns cash flow profile with a linear profile, ignoring "function" attribute"""
        return self._calculate_qtr(self._linear)
    
    @property
    def step_qtr(self):
        """returns cash flow profile with a step profile, ignoring "function" attribute"""
        return self._calculate_qtr(self._step)
    
    @property
    def single_qtr(self):
        """returns cash flow profile with a one-time amounts, ignoring "function" attribute"""
        return self._calculate_qtr(self._single)
    
    def to_json(self):
        return {
            "delay_qtrs": self.delay_qtrs,
            "discount_rate": self.discount_rate,
            "flow_id": str(self.id),
            "function": self.function,
            "is_cost": self.is_cost,
            "name": self.name,
            "max_amt": self.max_amt,
            "scale_up_qtrs": self.scale_up_qtrs,
            "tot_qtrs": self.tot_qtrs,
        }



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
    CELL_12 = Cell(12, 'start_value', False)
    CELL_13 = Cell(13, 'delay_qtrs', True)
    CELL_14 = Cell(14, 'max_amt', True)
    CELL_15 = Cell(15, 'scale_up_qtrs', True)
    CELL_16 = Cell(16, 'comments', False)
    
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
