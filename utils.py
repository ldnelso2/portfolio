from collections import namedtuple


# Simple named tuple to organize the index of a cell, and if it is required or not
#
# Parsing immediately, and with intent of what must be there prevents
# a slew of boundary type errors or runtime ones.
Cell = namedtuple('Cell', ['col_id', 'name'])


# TODO: incorporate python traitlets for type checking
class SmartsheetRow():
    """
    Reusable Smartsheet class for parsing a row. To use, define a child class which contains
    class attributes with a namedtuple defining each cell that should be parsed. This child class will
    inherit from this one, and automatically load and process all defined attributes.
    It is also possible to define methods to override the value when necessary. For example, divide an
    annual value by four
    """
    def __init__(self, row_dict):
        self.row_dict = row_dict
        self.cells_dct = { str(cell['columnId']): cell for cell in row_dict['cells'] }
        self.row_number = row_dict['rowNumber']
        # essentially grab the class attributes
        self.cell_defs = [getattr(self, attr) for attr in dir(self) if 'CELL_' in attr]
        self._load_cells()

    def _load_cells(self):
        for cell_def in self.cell_defs:
            modifier = getattr(self, f'_{cell_def.name}', None) or self._identity
            unmodified = self._get_cell(cell_def)
            value = modifier(unmodified) if unmodified is not None else None
            setattr(self, cell_def.name, value)
    
    @staticmethod
    def _identity(x):
        return x

    def is_required(self, cells_dict, cell_descriptor):
        """Returns if cell is required or not. Defaults to all not required if not overriden"""
        return False
        
    def _get_cell(self, cell_descriptor):
        """Will try to grab the cell regardless, if it is required, an error will be logged"""
        try:
            if self.is_required(self.cells_dct, cell_descriptor):
                return self.cells_dct[cell_descriptor.col_id]['value']
            else:
                return self.cells_dct[cell_descriptor.col_id].get('value', None)
        except:
            raise Exception(f'Failed to process Row <{self.row_number}>. Missing {cell_descriptor.name}')

    def to_json(self):
        cell_defs = [getattr(self, attr) for attr in dir(self) if 'CELL_' in attr]
        return { cd.name: getattr(self, cd.name) for cd in cell_defs }


def get_smartsheet_col_by_id(sheet_row, col_id):
    row_dct = { str(cell['columnId']): cell for cell in sheet_row.to_dict()['cells'] }
    try:
        return row_dct[col_id]
    except KeyError:
        raise Exception(f'column with ID <{col_id}> does not exist in provided smartsheet row')


def get_smartsheet_cell(row, col, sheet, attribute=None):
    """"Returns cell value from passed in sheet
    
    Args:
        row (int) - row number to access
        col (int) - col number to access
        sheet     - SmartSheet sheet instance
        attribute (str | None) - If None, return dictionary of cell
            data. If provided, returns attribute.
    """
    try:
        row = sheet.rows[row - 1 ] # -1 for 0 based indexing
        cells = row.to_dict()['cells']
        cell_value = cells[col - 1] # -1 for 0 based indexing
        return cell_value if attribute is None else cell_value[attribute]
    except IndexError:
        return None
    except AttributeError:
        raise Exception(f'<{attribute}> does not exist in row')


def scan_rows_for_start_stop(sheet, string, as_index=True):
    """Get the starting and stop values for a given string. E.g. "Start Global Vars" to "End Global Vars"
    
    Args:
        sheet (smartsheet object)
        string (str): The string (excluding start/stop) which function will scan the rows for
        as_index (boolean): if the returned starting values should be the actual row numbers or their index
    """
    offset = 0 if as_index else 1
    start = None
    for row_index, row in enumerate(sheet.rows):
        cell_value = row.to_dict()['cells'][0].get('value', '').strip().lower()
        col_string = ' '.join(cell_value.split(' ')[1:])
        if col_string == string.lower():
            if start is None:
                start = row_index + 1 # +1 to not include the "start" row
                continue
            end = row_index
            return start + offset, end + offset
    raise Exception(f'could not find rows that started and ended with <{string}>')


def _clamp(val, minimum=0, maximum=255):
    if val < minimum:
        return int(minimum)
    if val > maximum:
        return int(maximum)
    return int(val)


def colorscale(hexstr, scalefactor):
    """
    Scales a hex string by ``scalefactor``. Returns scaled hex string.

    To darken the color, use a float value between 0 and 1.
    To brighten the color, use a float value greater than 1.

    >>> colorscale("#DF3C3C", .5)
    #6F1E1E
    >>> colorscale("#52D24F", 1.6)
    #83FF7E
    >>> colorscale("#4F75D2", 1)
    #4F75D2
    """

    hexstr = hexstr.strip('#')

    if scalefactor < 0 or len(hexstr) != 6:
        return hexstr

    r, g, b = int(hexstr[:2], 16), int(hexstr[2:4], 16), int(hexstr[4:], 16)

    r = _clamp(r * scalefactor)
    g = _clamp(g * scalefactor)
    b = _clamp(b * scalefactor)

    return "#%02x%02x%02x" % (r, g, b)

def human_currency_format(num):
    num = float('{:.3g}'.format(num))
    magnitude = 0
    while abs(num) >= 1000:
        magnitude += 1
        num /= 1000.0
    return '{}{}'.format('{:f}'.format(num).rstrip('0').rstrip('.'), ['', 'k', 'm', 'b', 't'][magnitude])

def currency_fmt_to_cols(cols):
    return lambda col: col.apply(human_currency_format) if col.name in cols else col
