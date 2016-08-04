from PyQt4 import QtGui, QtCore
import sys

from pynfb.protocols import SelectSSDFilterWidget
from pynfb.protocols.user_inputs import SelectCSPFilterWidget
from pynfb.widgets.spatial_filter_setup import SpatialFilterSetup
from pynfb.signals import DerivedSignal
from numpy import dot

class Table(QtGui.QTableWidget):
    def __init__(self, signals, *args):
        super(Table, self).__init__(*args)
        self.signals = signals
        self.names = [signal.name for signal in signals]

        # set size and names
        self.columns = ['Signal', 'Modified', 'Band', 'Rejections', 'Drop rejections', 'Spatial filter', 'Open SSD',
                        'Open CSP']
        self.setColumnCount(len(self.columns))
        self.setRowCount(len(signals))
        self.setHorizontalHeaderLabels(self.columns)

        # set ch names
        for ind, signal in enumerate(signals):

            # name
            name_item = QtGui.QTableWidgetItem(signal.name)
            name_item.setFlags(QtCore.Qt.ItemIsEnabled)
            self.setItem(ind, self.columns.index('Signal'), name_item)
            self.update_row(ind)


        # buttons
        self.buttons = []
        self.drop_rejections_buttons = []
        self.csp_buttons = []
        for ind, _w in enumerate(self.names):
            open_ssd_btn = QtGui.QPushButton('Open')
            self.buttons.append(open_ssd_btn)
            self.setCellWidget(ind, self.columns.index('Open SSD'), open_ssd_btn)
            btn = QtGui.QPushButton('Open')
            self.csp_buttons.append(btn)
            self.setCellWidget(ind, self.columns.index('Open CSP'), btn)
            save_btn = QtGui.QPushButton('Drop')
            self.drop_rejections_buttons.append(save_btn)
            self.setCellWidget(ind, self.columns.index('Drop rejections'), save_btn)


        # formatting
        self.current_row = None
        self.horizontalHeader().setStretchLastSection(True)
        self.verticalHeader().setVisible(False)
        self.resizeColumnsToContents()

    def update_row(self, ind, modified=False):
        signal = self.signals[ind]
        # status
        modified_item = QtGui.QTableWidgetItem('Yes' if modified else 'No')
        modified_item.setFlags(QtCore.Qt.ItemIsEnabled)
        self.setItem(ind, self.columns.index('Modified'), modified_item)

        # band
        band_widget = BandWidget()
        band_widget.set_band(signal.bandpass)
        self.setCellWidget(ind, self.columns.index('Band'), band_widget)

        # rejection
        n_rejections = len(signal.rejections)
        self.setItem(ind, self.columns.index('Rejections'), QtGui.QTableWidgetItem(str(n_rejections)))

        # spatial filter
        text = 'Zeros' if signal.spatial_filter_is_zeros() else 'Not trivial'
        self.setItem(ind, self.columns.index('Spatial filter'), QtGui.QTableWidgetItem(text))

class BandWidget(QtGui.QWidget):
    def __init__(self, max_freq=10000, **kwargs):
        super(BandWidget, self).__init__(**kwargs)
        layout = QtGui.QHBoxLayout(self)
        layout.setMargin(0)
        self.left = QtGui.QDoubleSpinBox()
        self.left.setMinimumHeight(25)
        self.left.setRange(0, max_freq)
        self.right = QtGui.QDoubleSpinBox()
        self.right.setRange(0, max_freq)
        self.right.setMinimumHeight(25)
        layout.addWidget(self.left)
        layout.addWidget(QtGui.QLabel('-'))
        layout.addWidget(self.right)
        layout.addWidget(QtGui.QLabel('Hz '))

    def set_band(self, band=(0, 0)):
        self.left.setValue(band[0])
        self.right.setValue(band[1])

    def get_band(self):
        return self.left.value(), self.right.value()



class SignalsSSDManager(QtGui.QDialog):
    def __init__(self, signals, x, pos, channels_names, sampling_freq=1000, message=None, **kwargs):
        super(SignalsSSDManager, self).__init__(**kwargs)

        # attributes
        self.signals = [signal for signal in signals if isinstance(signal, DerivedSignal)]
        self.x = x
        self.pos = pos
        self.channels_names = channels_names
        self.sampling_freq = sampling_freq

        #layout
        layout = QtGui.QVBoxLayout(self)
        self.setMinimumWidth(700)

        # table
        self.table = Table(self.signals)
        layout.addWidget(self.table)

        # message
        if message is not None:
            layout.addWidget(QtGui.QLabel(message))

        # ok button
        ok_button = QtGui.QPushButton('OK')
        ok_button.clicked.connect(self.ok_button_action)
        ok_button.setMaximumWidth(100)
        layout.addWidget(ok_button)

        for j, button in enumerate(self.table.buttons):
            button.clicked.connect(lambda: self.run_ssd())
            button.setEnabled(isinstance(self.signals[j], DerivedSignal))

        for j, button in enumerate(self.table.csp_buttons):
            button.clicked.connect(lambda: self.run_ssd(csp=True))
            button.setEnabled(isinstance(self.signals[j], DerivedSignal))

        for j, button in enumerate(self.table.drop_rejections_buttons):
            button.clicked.connect(lambda: self.drop_rejections())
            button.setEnabled(isinstance(self.signals[j], DerivedSignal))

    def drop_rejections(self):
        row = self.table.drop_rejections_buttons.index(self.sender())
        if len(self.signals[row].rejections) > 0:
            quit_msg = "Are you sure you want to drop {} rejections of signal \"{}\"?".format(
                len(self.signals[row].rejections),
                self.signals[row].name)
            reply = QtGui.QMessageBox.question(self, 'Message',
                                               quit_msg, QtGui.QMessageBox.Yes, QtGui.QMessageBox.No)
            if reply == QtGui.QMessageBox.Yes:
                self.signals[row].update_rejections(rejections=[], append=False)
                self.table.update_row(row, modified=True)

    def run_ssd(self, row=None, csp=False):
        if row is None and not csp:
            row = self.table.buttons.index(self.sender())
        elif row is None and csp:
            row = self.table.csp_buttons.index(self.sender())

        x = self.x
        for rejection in self.signals[row].rejections:
            x = dot(x, rejection)

        SelectFilterWidget = SelectCSPFilterWidget if csp else SelectSSDFilterWidget
        filter, bandpass, rejections = SelectFilterWidget.select_filter_and_bandpass(x, self.pos,
                                                                                        self.channels_names,
                                                                                        sampling_freq=
                                                                                        self.sampling_freq)
        if filter is not None:
            self.signals[row].update_spatial_filter(filter)

        if bandpass is not None:
            self.signals[row].update_bandpass(bandpass)

        self.signals[row].update_rejections(rejections, append=True)

        modified_flag = len(rejections)>0 or bandpass is not None or filter is not None
        self.table.update_row(row, modified=modified_flag)


    def ok_button_action(self):
        for row in range(self.table.rowCount()):
            band = self.table.cellWidget(row, self.table.columns.index('Band')).get_band()
            self.signals[row].update_bandpass(band)
        self.close()




if __name__ == '__main__':
    import numpy as np
    from pynfb.signals import CompositeSignal
    signals = [DerivedSignal(name='Signal'+str(k), bandpass_low=0+k, bandpass_high=1+10*k, spatial_filter=np.array([k]), n_channels=4) for k in range(3)]
    signals +=[CompositeSignal(signals, '', 'Composite')]
    app = QtGui.QApplication([])

    x = np.random.rand(1000, 4)
    from pynfb.widgets.helpers import ch_names_to_2d_pos
    channels = ['Cz', 'Fp1', 'Fp2', 'Pz']

    w = SignalsSSDManager(signals, x, ch_names_to_2d_pos(channels), channels)
    w.show()
    app.exec_()