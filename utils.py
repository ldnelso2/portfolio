from collections import namedtuple


# Simple named tuple to organize the index of a cell, and if it is required or not
#
# Parsing immediately, and with intent of what must be there prevents
# a slew of boundary type errors or runtime ones.
Cell = namedtuple('Cell', ['index', 'name', 'required'])


class SmartsheetRow():
    """Reusable Smartsheet class for parsing a row. To use, define a child class which contains
    class attributes with a namedtuple defining each cell that should be parsed. This child class will
    inherit from this one, and automatically load and process all defined attributes.
    It is also possible to define methods to override the value when necessary. For example, divide an
    annual value by four"""
    def __init__(self, row_dict):
        self.row_dict = row_dict
        self.cells = row_dict['cells']
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
        
    def _get_cell(self, cell_descriptor):
        """Will try to grab the cell regardless, if it is required, an error will be logged"""
        try:
            if cell_descriptor.required:
                cell_value = self.cells[cell_descriptor.index]['value']
                return cell_value
            else:
                cell = self.cells[cell_descriptor.index]
                return cell.get('value', None)
        except:
            raise Exception(f'Failed to process Row <{self.row_number}>. Missing {cell_descriptor.name}')

    def to_json(self):
        cell_defs = [getattr(self, attr) for attr in dir(self) if 'CELL_' in attr]
        return { cd.name: getattr(self, cd.name) for cd in cell_defs }


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
