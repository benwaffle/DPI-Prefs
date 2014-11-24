#!/usr/bin/env python2

import os, signal, tempfile, shutil
from gi.repository import GObject, Gio, Gtk, Gdk
from gi.repository.GLib import Variant

class DPIPrefs(object):
    class GNOMEPrefs(GObject.GObject):
        def __init__(self):
            GObject.GObject.__init__(self)
            gst = Gio.Settings.new('org.gnome.desktop.interface')
            gst.bind('scaling-factor', self, 'scaling_factor', 0) 
            gst.bind('text-scaling-factor', self, 'text_scaling_factor', 0)

        scaling_factor = GObject.property(type=int)
        text_scaling_factor = GObject.property(type=float)

        def set_scaling_factor(self, w):
            self.scaling_factor = w.get_value_as_int()
        
        def set_text_scaling_factor(self, w):
            self.text_scaling_factor = w.get_value()

        def restart(self, w):
            os.kill(int(os.popen('pidof gnome-shell').read()), signal.SIGHUP)

    class GDKPrefs(object):
        class Overrides(object):
            xst = Gio.Settings.new('org.gnome.settings-daemon.plugins.xsettings')
            
            def __get__(self, instance, klass):
                return self.xst.get_value('overrides').unpack()

            def __set__(self, instance, value):
                self.xst.set_value('overrides', self.mk_gvariant(value))

            def mk_gvariant(self, obj):
                if type(obj) is int or type(obj) is long:
                    return Variant.new_int32(obj)
                if type(obj) is float:
                    return Variant.new_double(obj)
                if type(obj) is str:
                    return Variant.new_string(obj)
                if type(obj) is dict:
                    return Variant('a{sv}', dict([(k, self.mk_gvariant(obj[k])) for k in obj.keys()]))
                return None
        
        overrides = Overrides()

        def set_window_scaling_factor(self, w):
            o = self.overrides
            o['Gdk/WindowScalingFactor'] = w.get_value()
            self.overrides = o

        def set_unscaled_dpi(self, w):
            o = self.overrides
            o['Gdk/UnscaledDPI'] = w.get_value()
            self.overrides = o

    class XRANDRPrefs(object):
        def scale(self, x, y):
            output = os.popen("xrandr | grep ' connected' | head -1 | awk '{ print $1 }'").read().rstrip('\n')
            os.system("xrandr --output " + output + ' --scale ' + x.get_text() + 'x' + y.get_text())

        def dpi(self, w):
            os.system('xrandr --current --dpi ' + w.get_text())

    gnome = GNOMEPrefs()
    gdk = GDKPrefs()
    xrandr = XRANDRPrefs()

def hbox_rl(left, right, rightfill=False):
    hbox = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
    hbox.pack_start(left, False, False, 10)
    hbox.pack_end(right, rightfill, rightfill, 10)
    return hbox

def row_spinbutton(text='', value=0, min=0, max=9999999999, onChange=None, float=True):
    spinbutton = Gtk.SpinButton.new_with_range(min, max, 1)
    spinbutton.set_digits(2 if float else 0)
    spinbutton.set_numeric(True)
    spinbutton.set_value(value)
    spinbutton.set_update_policy(Gtk.SpinButtonUpdatePolicy.IF_VALID)
    if onChange:
        spinbutton.connect('value-changed', onChange)
    return hbox_rl(Gtk.Label(text), spinbutton)

def textfield_apply(text, applyfunc=None):
    textfield, button = Gtk.Entry(), Gtk.Button("apply")
    hbox = hbox_rl(Gtk.Label(text), button)
    hbox.pack_end(textfield, False, False, 10)
    if applyfunc:
        button.connect('clicked', lambda w: applyfunc(textfield))
    return hbox

def setenv(var, val):
    if os.access('/etc/environment', os.W_OK):
        fd, tmp_path = tempfile.mkstemp()
        tmp = open(tmp_path, 'w')
        env = open('/etc/environment')
        found = False
        for line in env:
            if line.startswith(var):
                found = True
                line = var + '=' + str(val) + '\n'
            tmp.write(line)
        if not found:
            tmp.write(var + '=' + str(val) + '\n')
        tmp.close()
        os.close(fd)
        env.close()
        os.remove('/etc/environment')
        shutil.move(tmp_path, '/etc/environment')
    else:
        print 'Error: I don\'t have permission to change /etc/environment'

class DPIApp(Gtk.Window):
    def gnome(self, listbox):
        listbox.add(Gtk.Label('GNOME'))
        listbox.add(row_spinbutton('Scaling Factor', dpi.gnome.scaling_factor, 0, 4294967295, dpi.gnome.set_scaling_factor, False))
        listbox.add(row_spinbutton('Text Scaling Factor', dpi.gnome.text_scaling_factor, 0.5, 3.0, dpi.gnome.set_text_scaling_factor))
        listbox.add(row_spinbutton('GDK Window Scaling Factor', dpi.gdk.overrides['Gdk/WindowScalingFactor'], 0, onChange=dpi.gdk.set_window_scaling_factor))
        listbox.add(row_spinbutton('GDK Unscaled DPI', dpi.gdk.overrides['Gdk/UnscaledDPI'], 0, onChange=dpi.gdk.set_unscaled_dpi, float=False))

        killgnome = Gtk.Button("Restart GNOME")
        killgnome.connect('clicked', dpi.gnome.restart)
        listbox.add(killgnome)

    def gdk(self, listbox):
        listbox.add(Gtk.Label('GDK'))
        listbox.add(textfield_apply('GDK_SCALE (environment variable)', lambda w: setenv('GDK_SCALE', w.get_text())))

    def xrandr(self, listbox):
        listbox.add(Gtk.Label('xrandr'))
        listbox.add(textfield_apply('DPI (may have no effect)', dpi.xrandr.dpi))
        
        row = textfield_apply('Scale')
        row.pack_end(Gtk.Label('X'), False, False, 0)
        row.pack_end(Gtk.Entry(), False, False, 10)
        c = row.get_children()
        x, y, b = c[1], c[3], c[4]
        b.connect('clicked', lambda w: dpi.xrandr.scale(x, y))
        listbox.add(row)

    def __init__(self):
        Gtk.Window.__init__(self, title='HiDPI Settings')
        listbox = Gtk.ListBox()
        self.add(listbox)
        listbox.set_selection_mode(Gtk.SelectionMode.NONE)

        self.gnome(listbox)
        listbox.add(Gtk.HSeparator())
        self.gdk(listbox)
        listbox.add(Gtk.HSeparator())
        self.xrandr(listbox)
    
        self.connect('delete-event', Gtk.main_quit)
        self.show_all()

dpi = DPIPrefs()
DPIApp()
Gtk.main()
