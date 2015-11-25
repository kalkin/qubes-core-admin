#!/usr/bin/python2
#
# The Qubes OS Project, http://www.qubes-os.org
#
# Copyright (C) 2015  Bahtiar `kalkin-` Gadimov <bahtiar@gadimov.de>
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation; either version 2
# of the License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301,
# USA.

from __future__ import absolute_import, print_function

from qubes.storage import Pool, QubesVmStorage

class ThinStorage(QubesVmStorage):

    def __init__(self, vm, **kwargs):
        super(ThinStorage, self).__init__(vm, **kwargs)
        self.private_img = LVM + vm.name + "-private"
        if self.vm.is_updateable() or (self.vm.template and
                                       self.vm.template.storage_type == "lvm"):
            self.root_img = LVM + vm.name + "-root"


class ThinPool(Pool):
    pass
