from extronlib.system import Wait


class ScrollingTable():
    # helper class **************************************************************
    class Cell():
        def __init__(self, row, col, btn=None, callback=None):
            self._row = row
            self._col = col
            self._btn = btn
            self._callback = callback
            self._Text = ''

        def SetText(self, text):
            if self._Text is not text:
                self._btn.SetText(text)
                self._Text = text

        def __str__(self):
            return 'Cell Object:\nrow={}\ncol={}\nbtn={}\ncallback={}'.format(self._row, self._col, self._btn,
                                                                              self._callback)

    # class ********************************************************************
    def __init__(self):
        self._header_btns = []
        self._cells = []
        self._data_rows = []  # list of dicts. each list element is a row of data. represents the full spreadsheet.
        self._current_row_offset = 0  # indicates the data row in the top left corner
        self._current_col_offset = 0  # indicates the data col in the top left corner
        self._max_row = 0
        self._max_col = 0
        self._table_header_order = []

        def UpdateTable():
            try:
                self._update_table()
            except Exception as e:
                # need this try/except because current Wait class only shows generic "Wait error" message
                print('Exception in self._update_table()\n', e)

        self._refresh_Wait = Wait(0.5, UpdateTable)
        self._refresh_Wait.Cancel()

    def set_table_header_order(self, header_list=[]):
        # header_list example: ['IP Address', 'Port']
        all_headers = []
        for row in self._data_rows:
            for key in row:
                if key not in all_headers:
                    all_headers.append(key)

        all_headers.sort()  # if some headers are not defined, put them alphabetically

        for key in header_list:
            if key in all_headers:
                all_headers.remove(key)

        # now all_headers contains all headers that are not in header_list
        header_list.extend(all_headers)
        self._table_header_order = header_list

        self._refresh_Wait.Restart()

    def register_header_buttons(self, *args):
        '''
        example: ScrollingTable.register_header_buttons(Button(TLP, 1), Button(TLP, 2) )
        '''
        self._header_btns = []
        for arg in args:
            self._header_btns.append(arg)

        self._refresh_Wait.Restart()

    def register_row_buttons(self, row_number, *args):
        '''example:
        ScrollingTable.register_row(row_number=1, Button(TLP, 1), Button(TLP, 2) )
        '''
        index = 0
        for arg in args:
            col_number = index
            self.register_cell(row_number, col_number, btn=arg, callback=self._cell_callback)
            index += 1

        self._refresh_Wait.Restart()

    def add_new_row_data(self, row_dict):
        '''example:
        ScrollingTable.register_data_row({'key1':'value1', 'key2':'value2', ...})
        '''
        print('ScrollingTable.add_new_row_data(row_dict={})'.format(row_dict))
        self._data_rows.append(row_dict)

        for key in row_dict:
            if key not in self._table_header_order:
                self._table_header_order.append(key)

        self._refresh_Wait.Restart()

    def clear_all_data(self):
        self._data_rows = []
        self._refresh_Wait.Restart()

    def update_row_data(self, where_dict, replace_dict):
        '''
        Find a row in self._data_rows that containts all the key/value pairs from where_dict
        replace/append the key/value pairs in that row with the key/values from replace_dict

        '''
        print('ScrollingTable.update_row_data(where_dict={}, replace_dict={})'.format(where_dict, replace_dict))
        # Check the data for a row that containts the key/value pair from where_dict

        if len(self._data_rows) == 0:
            return False

        for row in self._data_rows:
            # verify all the keys from where_dict are in row and the values match
            all_keys_match = True
            for key in where_dict:
                if key in row:
                    if where_dict[key] != row[key]:
                        all_keys_match = False
                        break
                else:
                    all_keys_match = False
                    break

            if all_keys_match:
                # All the key/values from where_dict match row, update row with replace dict values
                for key in replace_dict:
                    row[key] = replace_dict[key]

        self._refresh_Wait.Restart()

    def has_row(self, where_dict):
        print('ScrollingTable.has_row(where_dict={})'.format(where_dict))
        # Check the data for a row that containts the key/value pair from where_dict

        if len(self._data_rows) == 0:
            return False

        for row in self._data_rows:
            # verify all the keys from where_dict are in row and the values match
            all_keys_match = True
            for key in where_dict:
                if key in row:
                    if where_dict[key] != row[key]:
                        all_keys_match = False
                        break
                else:
                    all_keys_match = False
                    break

            if all_keys_match:
                return True

        return False

    def register_cell(self, *args, **kwargs):
        NewCell = self.Cell(*args, **kwargs)
        self._cells.append(NewCell)

        self._find_max_row_col()

        self._refresh_Wait.Restart()

    def _find_max_row_col(self):
        for cell in self._cells:
            if cell._col > self._max_col:
                self._max_col = cell._col

            if cell._row > self._max_row:
                self._max_row = cell._row

    def _cell_callback(self, cell):
        print('ScrollingTable._cell_callback(\nself={},\ncell={},\n)'.format(self, cell))

    def scroll_up(self):
        print('ScrollingTable.scroll_up(self={})'.format(self))
        self._current_row_offset -= 1
        if self._current_row_offset < 0:
            self._current_row_offset = 0

        self._update_table()

    def scroll_down(self):
        print('ScrollingTable.scroll_down(self={})'.format(self))
        self._current_row_offset += 1
        if self._current_row_offset > self._max_row:
            self._current_row_offset = self._max_row

        self._update_table()

    def scroll_left(self):
        print('ScrollingTable.scroll_left(self={})'.format(self))
        self._current_col_offset -= 1
        if self._current_col_offset < 0:
            self._current_col_offset = 0

        self._update_table()

    def scroll_right(self):
        print('ScrollingTable.scroll_right(self={})'.format(self))
        self._current_col_offset += 1
        if self._current_col_offset > self._max_col:
            self._current_col_offset = self._max_col

        self._update_table()

    def _update_table(self):
        print('_update_table()')
        debug = True

        # iterate over all the cell objects
        for cell in self._cells:
            row_index = cell._row + self._current_row_offset
            if debug:
                print('cell=', cell)
                print('cell._row=', cell._row)
                print('self._current_row_offset=', self._current_row_offset)
                print('row_index=', row_index)
                print('self._data_rows=', self._data_rows)

            if row_index <= len(self._data_rows) - 1:
                row_dict = self._data_rows[row_index]
                if debug: print('row_dict=', row_dict)

                col_header_index = cell._col + self._current_col_offset
                if debug: print('col_header_index=', col_header_index)

                col_header = self._table_header_order[col_header_index]
                if debug: print('col_header=', col_header)

                cell_data = row_dict[col_header]  # cell_data holds data for this cell
                if debug: print('cell_data=', cell_data)

                cell.SetText(str(cell_data))
            else:
                # no data for this cell
                cell.SetText('')


