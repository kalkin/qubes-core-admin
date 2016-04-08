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
from qubes.storage import Pool, QubesVmStorage, StoragePoolException, same_pool

log = logging.getLogger('qubes.lvm')
log.setLevel(logging.INFO)
log_h = logging.StreamHandler(sys.stdout)
log_h.setFormatter(logging.Formatter('%(name)s[%(levelname)s]: %(message)s'))
log.addHandler(log_h)


class ThinStorage(QubesVmStorage):

    def __init__(self, vm, vmdir, thin_pool, **kwargs):
        super(ThinStorage, self).__init__(vm, **kwargs)
        self.log = log

        self.thin_pool = thin_pool

        self.root_img = self._volume_path(vm.name + "-root")
        self.private_img = self._volume_path(vm.name + "-private")
        self.volatile_img = self._volume_path(vm.name + "-volatile")

    def root_dev_config(self):
        return self.format_disk_dev(self.root_img, None, self.root_dev, True)

    def private_dev_config(self):
        return self.format_disk_dev(self.private_img, None,
                                    self.private_dev, True)

    def volatile_dev_config(self):
        return self.format_disk_dev(self.volatile_img, None, self.volatile_dev,
                                    True)

    def _volume_path(self, volume):
        return os.path.abspath(
            os.path.join('/dev/', self.thin_pool, os.pardir, volume))

    def create_on_disk_root_img(self, verbose, source_template=None):
        vmname = self.vm.name

        if source_template is not None and not self.vm.updateable:
            # just use template's disk
            return
        elif source_template is not None and same_pool(self.vm,
                                                       source_template):
            self.log.info("Snapshot %s for vm %s"
                          % (source_template.root_img, vmname))
            create_snapshot(source_template.root_img, self.root_img)
        elif source_template is not None:
            new_volume(self.thin_pool, self.root_img, self.root_img_size)
            self._copy_file(source_template.root_img, self.root_img)
        else:
            self.log.info("Creating empty root img for %s" % vmname)
            new_volume(self.thin_pool, self.root_img, self.root_img_size)

    def create_on_disk_private_img(self, verbose, source_template=None):
        vmname = self.vm.name
        if source_template is not None and same_pool(self.vm, source_template):
            self.log.info("Snapshot %s for vm %s" %
                          (source_template.private_img, vmname))
            create_snapshot(source_template.private_img, self.private_img)
        elif source_template is not None:
            self.log.info("Importing from another pool for %s" % vmname)
            new_volume(self.thin_pool, self.private_img, self.private_img_size)
            self._copy_file(source_template.private_img, self.private_img)
        else:
            self.log.info("Creating empty private img for %s" % vmname)
            new_volume(self.thin_pool, self.private_img, self.private_img_size)

    def root_snapshot_config(self, vm):
        return self.format_disk_dev(self.root_img, None, self.root_dev, True)

    def prepare_for_vm_startup(self, verbose):
        self.reset_volatile_storage()
        if self.vm.is_appvm() and same_pool(self.vm, self.vm.template):
            remove_volume(self.root_img)
            create_snapshot(self.vm.template.root_img, self.root_img)

    def reset_volatile_storage(self, verbose=False, source_template=None):
        if source_template is None:
            source_template = self.vm.template

        if source_template is not None and self.vm.is_appvm() and \
                not same_pool(self.vm, source_template) and \
                not os.path.exists(self.volatile_img):
            f_template_root_img = open(source_template.storage.root_img, 'r')
            f_template_root_img.seek(0, os.SEEK_END)
            volatile_img_size = f_template_root_img.tell()
            new_volume(self.thin_pool, self.volatile_img, volatile_img_size)
        else:
            remove_volume(self.volatile_img)
            volatile_img_size = 1024000000  # 1GB
            new_volume(self.thin_pool, self.volatile_img, volatile_img_size)

            cmd = ['sudo', 'fdisk', self.volatile_img]
            p = subprocess.Popen(cmd, stdin=subprocess.PIPE)
            p.stdin.write("o\nn\np\n1\n\n\nw")
            p.communicate()

    def verify_files(self):
        self.log.debug("Verifying files")
        if not os.path.exists(self.vmdir):
            self.log.error("VM directory doesn't exist: %s" % self.vmdir)
            raise QubesException("VM directory doesn't exist: {0}".
                                 format(self.vmdir))

        if self.root_img and not os.path.exists(self.root_img) and \
                self.vm.is_updateable():
            self.log.error("VM root image doesn't exist: %s" % self.root_img)
            raise QubesException("VM root image file doesn't exist: {0}".
                                 format(self.root_img))

        if self.private_img and not os.path.exists(self.private_img):
            self.log.error("VM private image doesn't exist: %s"
                           % self.private_img)
            raise QubesException("VM private image file doesn't exist: {0}".
                                 format(self.private_img))
        if self.modules_img is not None and \
                not os.path.exists(self.modules_img):
            self.log.error(
                "VM modules image doesn't exist: %s" % self.modules_img)
            raise QubesException(
                "VM kernel modules image does not exists: {0}"
                .format(self.modules_img)
                )

    def rename(self, old_name, new_name):
        self.log.debug("Renaming %s to %s " % (old_name, new_name))
        old_vmdir = self.vmdir
        new_vmdir = os.path.join(os.path.dirname(self.vmdir), new_name)
        os.rename(self.vmdir, new_vmdir)
        self.vmdir = new_vmdir
        if self.private_img:
            self.private_img = rename_volume(
                self.private_img, self._volume_path(new_name + "-private"))
        if self.root_img:
            if self.vm.is_updateable():
                self.root_img = rename_volume(
                    self.root_img, self._volume_path(new_name + "-root"))
            else:
                self.root_img = self.root_img.replace(old_vmdir, new_vmdir)
        if self.volatile_img:
            self.volatile_img = self.volatile_img.replace(old_vmdir, new_vmdir)

    def remove_from_disk(self):
        remove_volume(self.private_img)
        remove_volume(self.volatile_img)
        if self.vm.is_updateable() or same_pool(self.vm, self.vm.template):
            remove_volume(self.root_img)
        shutil.rmtree(self.vmdir)

    def clone_disk_files(self, src_vm, verbose):
        if verbose:
            sys.stderr.write("--> Creating directory: {0}".format(self.vmdir))
        os.mkdir(self.vmdir)

        self.create_on_disk_private_img(verbose, source_template=src_vm)
        self.create_on_disk_root_img(verbose, source_template=src_vm)

    def _copy_file(self, source, destination):
        """ Effective file copy, preserving sparse files etc. """
        self.log.info("Copying file from %s to %s" % (source, destination))
        subprocess.check_output(['sudo', 'dd', 'if=' + source,
                                 "of=" + destination, 'bs=128M',
                                 'conv=sparse'])

    def commit_template_changes(self):
        pass

    def is_outdated(self):
        if self.vm.is_template():
            return lvm_image_changed(self.vm)
        elif self.vm.is_appvm():
            return self.vm.is_outdated()
        else:
            return False

    def shutdown(self):
        if self.vm.is_appvm() and same_pool(self.vm, self.vm.template):
            remove_volume(self.root_img)

        remove_volume(self.volatile_img)


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
    return True  # TODO Implement a fast version of the bellow
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


def thin_volume_exists(volume):
    """ Check if the given volume exists and is a thin volume """
    log.debug("Checking if the %s thin volume exists" % volume)
    assert volume is not None

    cmd = ['sudo', 'lvs', '-o',  'lv_modules', '--rows', volume]
    try:
        output = subprocess.check_output(cmd, stderr=subprocess.STDOUT)
        log.debug(output)
        # Just because the above command succeded it does not mean that we
        # really have a volume managed by a thin pool. It could be just any
        # volume. Below we check that the volume uses the thin-pool module.
        if "thin-pool,thin" in output:
            return True
    except subprocess.CalledProcessError:
        return False


def remove_volume(img):
    """ Tries to remove the specified logical volume.

        If the removal fails it will try up to 3 times waiting 1, 2 and 3
        seconds between tries. Most of the time this function fails if some
        process still has the volume locked.
    """
    if not thin_volume_exists(img):
        log.warn("Is not a LVM thin volume %s. Ignoring it" % img)
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

        if successful:
            break
        else:
            time.sleep(tries)
            tries += 1

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

        if not thin_pool_exists(thin_pool):
            raise StoragePoolException("LVM Thin Pool %s does not exist"
                                       % thin_pool)
        self.thin_pool = thin_pool

    def getStorage(self):
        return ThinStorage(self.vm, thin_pool=self.thin_pool, vmdir=self.vmdir)
