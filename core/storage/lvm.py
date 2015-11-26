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

import datetime
import logging
import os
import shutil
import subprocess
import sys
import time

from qubes.qubes import QubesException
from qubes.storage import Pool, QubesVmStorage

log = logging.getLogger('qubes.lvm')


class ThinStorage(QubesVmStorage):

    def __init__(self, vm, vmdir, thin_pool, **kwargs):
        super(ThinStorage, self).__init__(vm, **kwargs)
        self.private_img = LVM + vm.name + "-private"
        if self.vm.is_updateable() or (self.vm.template and
                                       self.vm.template.storage_type == "lvm"):
            self.root_img = LVM + vm.name + "-root"


def lvm_image_changed(vm):
    vm_root = vm.root_img
    tp_root = vm.template.root_img
    if not os.path.exists(vm_root):
        return False
    cmd = 'date +"%%s" -d "' + \
        '`sudo tune2fs %s -l|grep "Last write time"|cut -d":" -f2,3,4`"'
    result1 = subprocess.check_output(cmd % vm_root, shell=True).strip()
    result2 = subprocess.check_output(cmd % tp_root, shell=True).strip()

    result1 = datetime.datetime.strptime(result1, '%c')
    result2 = datetime.datetime.strptime(result2, '%c')
    return result2 > result1


def thin_pool_exists(name):
    """ Check if given name is an lvm thin volume. """
    log.debug("Checking if LVM Thin Pool %s exists" % name)
    cmd = ['sudo', 'lvs', '-o',  'data_lv', '--rows', name]
    try:
        output = subprocess.check_output(cmd, stderr=subprocess.STDOUT)
        log.debug(output)
        # Just because the above command succeded it does not mean that we
        # really have a thin pool. It could be just any volume. Below we check
        # that the output string contains tdata. (Edgecase: thin pool called
        # tdata)
        if "tdata" in output:
            return True
    except subprocess.CalledProcessError:
        return False


def remove_volume(img):
    """ Tries to remove the specified logical volume.

        If the removal fails it will try up to 3 times waiting 1, 2 and 3
        seconds between tries. Most of the time this function fails if some
        process still has the volume locked.
    """
    assert img is not None
    if not os.path.exists(img):
        log.warn('Volume ' + img + ' does not exist. Already removed?')
        return
    tries = 1
    successful = False
    cmd = ['sudo', 'lvremove', '-f', img]

    while tries <= 3 and not successful:
        log.info("Trying to remove LVM %s" % img)
        try:
            output = subprocess.check_output(cmd, stderr=subprocess.STDOUT)
            log.debug(output)
            successful = True
        except subprocess.CalledProcessError:
            successful = False

        if not successful:
            time.sleep(tries)

    if not successful:
        log.error('Could not remove volume ' + img)


def create_snapshot(old, new_name):
    """ Calls lvcreate and creates new snapshot. """
    cmd = ["sudo", "lvcreate", "-kn", "-ay", "-s", old, "-n", new_name]
    output = subprocess.check_output(cmd)
    log.debug(output)
    return new_name


def new_volume(thin_pool, name, size):
    """ Creates a new volume in the specified thin pool, formated with ext4 """
    log.info("Creating new Thin LVM %s in %s VG %s bytes"
             % (name, thin_pool, size))
    cmd = ['sudo', 'lvcreate', '-T', thin_pool, '-kn', '-ay', '-n',
           name, '-V', str(size)+'B']

    lvm_output = subprocess.check_output(cmd)
    log.debug(lvm_output)

    mkfs = ["sudo", "mkfs.ext4", name]
    mkfs_output = subprocess.check_output(mkfs, stderr=subprocess.STDOUT)
    log.debug(mkfs_output)
    return name


def get_vg(volume_path):
    return os.path.abspath(os.path.join(volume_path, os.pardir))


def rename_volume(old_name, new_name):
    log.debug("Renaming LVM  %s to %s " % (old_name, new_name))
    retcode = subprocess.call(["sudo", "lvrename", old_name, new_name])
    if retcode != 0:
        raise IOError("Error renaming LVM  %s to %s " % (old_name, new_name))
    return new_name


class ThinPool(Pool):
    def __init__(self, vm, thin_pool=None, dir_path='/var/lib/qubes/'):
        super(ThinPool, self).__init__(vm, dir_path)
        if thin_pool is None:
            thin_pool = 'qubes_dom0/pool00'
        self.thin_pool = thin_pool

    def getStorage(self):
        return ThinStorage(self.vm, thin_pool=self.thin_pool, vmdir=self.vmdir)
