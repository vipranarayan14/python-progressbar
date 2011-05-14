#!/usr/bin/python
# -*- coding: iso-8859-1 -*-
#
# progressbar  - Text progress bar library for python.
# Copyright (c) 2005 Nilton Volpato
#
# This library is free software; you can redistribute it and/or
# modify it under the terms of the GNU Lesser General Public
# License as published by the Free Software Foundation; either
# version 2.1 of the License, or (at your option) any later version.
#
# This library is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public
# License along with this library; if not, write to the Free Software
# Foundation, Inc., 51 Franklin St, Fifth Floor, Boston, MA  02110-1301  USA


"""Text progress bar library for python.

This library provides a text mode progress bar. This is typically used
to display the progress of a long running operation, providing a
visual clue that processing is underway.

The ProgressBar class manages the progress, and the format of the line
is given by a number of widgets. A widget is an object that may
display differently depending on the state of the progress. There are
three types of widget:
- a string, which always shows itself;
- a ProgressBarWidget, which may return a different value every time
it's update method is called; and
- a ProgressBarWidgetHFill, which is like ProgressBarWidget, except it
expands to fill the remaining width of the line.

The progressbar module is very easy to use, yet very powerful. And
automatically supports features like auto-resizing when available.
"""

from __future__ import division

__author__ = "Nilton Volpato"
__author_email__ = "first-name dot last-name @ gmail.com"
__date__ = "2006-05-07"
__version__ = "2.3-dev"

import sys, time, os
import datetime
from array import array

try:
    from fcntl import ioctl
    import termios
except ImportError:
    pass

import signal

try:
    basestring
except NameError:
    basestring = (str,)


# Python 3.x (and backports) use a modified iterator syntax
# This will allow 2.x to behave with 3.x iterators
if not hasattr(__builtins__, 'next'):
    def next(iter):
        try:
            # Try new style iterators
            return iter.__next__()
        except AttributeError:
            # Fallback in case of a "native" iterator
            return iter.next()

# Python 3.x int is practically synonymous for a long in 2.x so create an alias
if not hasattr(__builtins__, 'long'):
    long = int


class ProgressBarWidget(object):
    """This is an element of ProgressBar formatting.

    The ProgressBar object will call it's update value when an update
    is needed. It's size may change between call, but the results will
    not be good if the size changes drastically and repeatedly.

    If the class constant TIME_SENSITIVE is True, then the ProgressBar
    will be updated at least once every second, provided update() is called.
    """
    TIME_SENSITIVE = False
    def update(self, pbar):
        """Returns the string representing the widget.

        The parameter pbar is a reference to the calling ProgressBar,
        where one can access attributes of the class for knowing how
        the update must be made.

        At least this function must be overridden."""
        pass

class ProgressBarWidgetHFill(ProgressBarWidget):
    """This is a variable width element of ProgressBar formatting.

    The ProgressBar object will call it's update value, informing the
    width this object must the made. This is like TeX \\hfill, it will
    expand to fill the line. You can use more than one in the same
    line, and they will all have the same width, and together will
    fill the line.
    """
    def update(self, pbar, width):
        """Returns the string representing the widget.

        The parameter pbar is a reference to the calling ProgressBar,
        where one can access attributes of the class for knowing how
        the update must be made. The parameter width is the total
        horizontal width the widget must have.

        At least this function must be overridden."""
        pass


class ETA(ProgressBarWidget):
    "Widget for the Estimated Time of Arrival"
    TIME_SENSITIVE = True
    def format_time(self, seconds):
        return str(datetime.timedelta(seconds=int(seconds)))
    def update(self, pbar):
        if pbar.currval == 0:
            return 'ETA:  --:--:--'
        elif pbar.finished:
            return 'Time: %s' % self.format_time(pbar.seconds_elapsed)
        else:
            elapsed = pbar.seconds_elapsed
            eta = elapsed * pbar.maxval / pbar.currval - elapsed
            return 'ETA:  %s' % self.format_time(eta)

class FileTransferSpeed(ProgressBarWidget):
    "Widget for showing the transfer speed (useful for file transfers)."
    def __init__(self, unit='B'):
        self.unit = unit
        self.fmt = '%6.2f %s'
        self.prefixes = ['', 'K', 'M', 'G', 'T', 'P']
    def update(self, pbar):
        if pbar.seconds_elapsed < 2e-6:#== 0:
            bps = 0.0
        else:
            bps = pbar.currval / pbar.seconds_elapsed
        spd = bps
        for u in self.prefixes:
            if spd < 1000:
                break
            spd /= 1000
        return self.fmt % (spd, u + self.unit + '/s')

class RotatingMarker(ProgressBarWidget):
    "A rotating marker for filling the bar of progress."
    def __init__(self, markers='|/-\\'):
        self.markers = markers
        self.curmark = -1
    def update(self, pbar):
        if pbar.finished:
            return self.markers[0]
        self.curmark = (self.curmark + 1) % len(self.markers)
        return self.markers[self.curmark]

class Percentage(ProgressBarWidget):
    "Just the percentage done."
    def update(self, pbar):
        return '%3d%%' % pbar.percentage()

class SimpleProgress(ProgressBarWidget):
    "Returns what is already done and the total, e.g.: '5 of 47'"
    def __init__(self, sep=' of '):
        self.sep = sep
    def update(self, pbar):
        return '%d%s%d' % (pbar.currval, self.sep, pbar.maxval)

class Bar(ProgressBarWidgetHFill):
    "The bar of progress. It will stretch to fill the line."
    def __init__(self, marker='#', left='|', right='|', fillchar=' '):
        self.marker = marker
        self.left = left
        self.right = right
        self.fillchar = fillchar
    def _format_marker(self, pbar):
        if isinstance(self.marker, basestring):
            return self.marker
        else:
            return self.marker.update(pbar)
    def update(self, pbar, width):
        percent = pbar.percentage()
        cwidth = width - len(self.left) - len(self.right)
        marked_width = int(percent * cwidth // 100)
        m = self._format_marker(pbar)
        bar = (self.left +
               (m * marked_width).ljust(cwidth, self.fillchar) +
               self.right)
        return bar

class ReverseBar(Bar):
    "The reverse bar of progress, or bar of regress. :)"
    def update(self, pbar, width):
        percent = pbar.percentage()
        cwidth = width - len(self.left) - len(self.right)
        marked_width = int(percent * cwidth // 100)
        m = self._format_marker(pbar)
        bar = (self.left + (m*marked_width).rjust(cwidth) + self.right)
        return bar

default_widgets = [Percentage(), ' ', Bar()]
class ProgressBar(object):
    """This is the ProgressBar class, it updates and prints the bar.

    A common way of using it is like:
    >>> pbar = ProgressBar().start()
    >>> for i in xrange(100):
    ...    # do something
    ...    pbar.update(i+1)
    ...
    >>> pbar.finish()

    You can also use a ProgressBar as an iterator:
    >>> progress = ProgressBar()
    >>> for i in progress(some_iterable):
    ...    # do something
    ...

    But anything you want to do is possible (well, almost anything).
    You can supply different widgets of any type in any order. And you
    can even write your own widgets! There are many widgets already
    shipped and you should experiment with them.

    The term_width parameter must be an integer or None. In the latter case
    it will try to guess it, if it fails it will default to 80 columns.

    When implementing a widget update method you may access any
    attribute or function of the ProgressBar object calling the
    widget's update method. The most important attributes you would
    like to access are:
    - currval: current value of the progress, 0 <= currval <= maxval
    - maxval: maximum (and final) value of the progress
    - finished: True if the bar has finished (reached 100%), False o/w
    - start_time: the time when start() method of ProgressBar was called
    - seconds_elapsed: seconds elapsed since start_time
    - percentage(): percentage of the progress [0..100]. This is a method.

    The attributes above are unlikely to change between different versions,
    the other ones may change or cease to exist without notice, so try to rely
    only on the ones documented above if you are extending ProgressBar.
    """

    __slots__ = ('currval', 'fd', 'finished', 'last_update_time', 'maxval',
                 'next_update', 'num_intervals', 'seconds_elapsed',
                 'signal_set', 'start_time', 'term_width', 'update_interval',
                 'widgets', '_iterable', '_time_sensitive')

    _DEFAULT_MAXVAL = 100

    def __init__(self, maxval=None, widgets=default_widgets, term_width=None,
                 fd=sys.stderr):
        self.maxval = maxval
        self.widgets = widgets
        self.fd = fd
        self.signal_set = False
        if term_width is not None:
            self.term_width = term_width
        else:
            try:
                self._handle_resize(None, None)
                signal.signal(signal.SIGWINCH, self._handle_resize)
                self.signal_set = True
            except (SystemExit, KeyboardInterrupt):
                raise
            except:
                self.term_width = int(os.environ.get('COLUMNS', 80)) - 1

        self._time_sensitive = False
        for w in widgets:
          if getattr(w, 'TIME_SENSITIVE', False):
            self._time_sensitive = True
            break

        self.currval = 0
        self.finished = False
        self.start_time = None
        self.last_update_time = None
        self.seconds_elapsed = 0
        self._iterable = None

    def __call__(self, iterable):
        try:
            self.maxval = len(iterable)
        except TypeError:
            # If the iterable has no length, then rely on the value provided
            # by the user, otherwise fail.
            if not (isinstance(self.maxval, (int, long)) and self.maxval > 0):
                raise RuntimeError('Could not determine maxval from iterable. '
                                   'You must explicitly provide a maxval.')
        self._iterable = iter(iterable)
        return self

    def __iter__(self):
        return self

    def __next__(self):
        try:
            value = next(self._iterable)
            if self.start_time is None:
                self.start()
            else:
                self.update(self.currval + 1)
            return value
        except StopIteration:
            self.finish()
            raise

    # Create an alias so that Python 2.x won't complain about not being
    # an iterator.
    next = __next__

    def _handle_resize(self, signum, frame):
        h, w = array('h', ioctl(self.fd, termios.TIOCGWINSZ, '\0' * 8))[:2]
        self.term_width = w

    def percentage(self):
        "Returns the percentage of the progress."
        return self.currval * 100.0 / self.maxval

    def _format_widgets(self):
        r = []
        hfill_inds = []
        num_hfill = 0
        currwidth = 0
        for i, w in enumerate(self.widgets):
            if isinstance(w, ProgressBarWidgetHFill):
                r.append(w)
                hfill_inds.append(i)
                num_hfill += 1
            elif isinstance(w, basestring):
                r.append(w)
                currwidth += len(w)
            else:
                weval = w.update(self)
                currwidth += len(weval)
                r.append(weval)
        for iw in hfill_inds:
            widget_width = int((self.term_width - currwidth) // num_hfill)
            r[iw] = r[iw].update(self, widget_width)
        return r

    def _format_line(self):
        return ''.join(self._format_widgets()).ljust(self.term_width)

    def _next_update(self):
        return int((int(self.num_intervals *
                        (self.currval / self.maxval)) + 1) *
                   self.update_interval)

    def _need_update(self):
        """Returns true when the ProgressBar should print an updated line.

        You can override this method if you want finer grained control over
        updates.

        Ideally you could call self._format_line() and see if it's different
        from the previous _format_line() call, but calling _format_line() takes
        around 20 times more time than calling this implementation of
        _need_update().
        """
        return (self.currval >= self.next_update or self.finished or
                (self._time_sensitive and
                 int(time.time() - self.last_update_time) > 1))

    def update(self, value):
        "Updates the ProgressBar to a new value."
        assert 0 <= value <= self.maxval, '0 <= %d <= %d' % (value, self.maxval)
        self.currval = value
        if not self._need_update():
            return
        if self.start_time is None:
            raise RuntimeError('You must call start() before calling update()')
        now = time.time()
        self.seconds_elapsed = now - self.start_time
        self.next_update = self._next_update()
        self.fd.write(self._format_line() + '\r')
        self.last_update_time = now

    def start(self):
        """Starts measuring time, and prints the bar at 0%.

        It returns self so you can use it like this:
        >>> pbar = ProgressBar().start()
        >>> for i in xrange(100):
        ...    # do something
        ...    pbar.update(i+1)
        ...
        >>> pbar.finish()
        """
        if self.maxval is None:
            self.maxval = self._DEFAULT_MAXVAL
        assert self.maxval > 0

        self.num_intervals = max(100, self.term_width)
        self.update_interval = self.maxval / self.num_intervals
        self.next_update = 0

        self.start_time = self.last_update_time = time.time()
        self.update(0)
        return self

    def finish(self):
        """Used to tell the progress is finished."""
        self.finished = True
        self.update(self.maxval)
        self.fd.write('\n')
        if self.signal_set:
            signal.signal(signal.SIGWINCH, signal.SIG_DFL)
