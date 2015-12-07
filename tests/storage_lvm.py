# The Qubes OS Project, https://www.qubes-os.org/
#
# Copyright (C) 2015  Bahtiar `kalkin-` Gadimov <bahtiar@gadimov.de>
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License along
# with this program; if not, write to the Free Software Foundation, Inc.,
# 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.

import os

import qubes.storage
from qubes.storage.lvm import ThinStorage, thin_pool_exists, remove_volume
from qubes.tests import QubesTestCase, SystemTestsMixin


class TC_00_LvmThinPool(SystemTestsMixin, QubesTestCase):

    POOL_NAME = 'lvm-test-pool'

    def setUp(self):
        """ Add a test lvm thin pool pool """
        super(TC_00_LvmThinPool, self).setUp()
        qubes.storage.add_pool(self.POOL_NAME, driver='lvm-thin')

    def tearDown(self):
        """ Remove test lvm thin pool """
        super(TC_00_LvmThinPool, self).tearDown()
        qubes.storage.remove_pool(self.POOL_NAME)

    def test_000_lvm_thin_pool(self):
        """ The predefined thin pool should be ``qubes_dom0/pool00`` """
        vm = self._init_app_vm()
        result = qubes.storage.get_pool(self.POOL_NAME, vm).thin_pool
        expected = 'qubes_dom0/pool00'
        self.assertEquals(result, expected)

    def test_001_lvm_storage_class(self):
        """ Check when using lvm thin pool the Storage is ``ThinStorage``. """
        result = self._init_app_vm().storage
        self.assertIsInstance(result, ThinStorage)

    def test_002_thin_pool_does_not_exist(self):
        self.assertFalse(thin_pool_exists("hfasdkhasdf/saisdfhkasd"))

    def _init_app_vm(self):
        """ Return initalised, but not created, AppVm. """
        vmname = self.make_vm_name('appvm')
        template = self.qc.get_default_template()
        return self.qc.add_new_vm('QubesAppVm', name=vmname, template=template,
                                  pool_name=self.POOL_NAME)


class TC_01_LvmThinPool(SystemTestsMixin, QubesTestCase):

    VM_NAME = 'test-opfer'
    POOL_NAME = 'lvm-test-pool'
    ROOT_PATH = '/dev/qubes_dom0/' + VM_NAME + '-root'
    PRIVATE_PATH = '/dev/qubes_dom0/' + VM_NAME + '-private'
    VOLATILE_PATH = '/dev/qubes_dom0/' + VM_NAME + '-volatile'

    def setUp(self):
        """ Add a test lvm thin pool pool """
        super(TC_01_LvmThinPool, self).setUp()
        qubes.storage.add_pool(self.POOL_NAME, driver='lvm-thin')
        self.template = self.qc.get_default_template()

    def tearDown(self):
        """ Remove test lvm thin pool """
        super(TC_01_LvmThinPool, self).tearDown()
        qubes.storage.remove_pool(self.POOL_NAME)
        remove_volume(self.ROOT_PATH)
        remove_volume(self.PRIVATE_PATH)
        remove_volume(self.VOLATILE_PATH)

    def test_000_hvm_image_paths(self):
        vm = self.qc.add_new_vm('QubesHVm', name=self.VM_NAME,
                                pool_name=self.POOL_NAME)
        vm.create_on_disk(verbose=False)
        self.assertEqualsAndExists(vm.root_img, self.ROOT_PATH)
        self.assertEqualsAndExists(vm.private_img, self.PRIVATE_PATH)

    def test_001_appvm_based_on_xen_template(self):
        template = self.qc.get_default_template()
        vm = self.qc.add_new_vm('QubesAppVm', name=self.VM_NAME,
                                template=template, pool_name=self.POOL_NAME)

        vm.create_on_disk(verbose=False)
        self.assertFalse(os.path.exists(self.ROOT_PATH))
        self.assertEqualsAndExists(vm.private_img, self.PRIVATE_PATH)

        vm.start()
        self.assertEquals(vm.get_power_state(), "Running")
        vm.shutdown()

    def test_002_clone_xen_based_template(self):
        vm = self.clone_vm(self.VM_NAME, self.template)
        self.assertEqualsAndExists(vm.root_img, self.ROOT_PATH)
        self.assertEqualsAndExists(vm.private_img, self.PRIVATE_PATH)
        vm.start()
        self.assertEquals(vm.get_power_state(), "Running")
        vm.shutdown()

    def assertEqualsAndExists(self, result_path, expected_path):
        """ Check if the ``result_path``, matches ``expected_path`` and exists.

            See also: :meth:``assertExist``
        """
        self.assertEquals(result_path, expected_path)
        self.assertExist(result_path)

    def assertExist(self, path):
        """ Assert that the given path exists. """
        self.assertTrue(os.path.exists(path))

    def clone_vm(self, name, template):
        vm = self.qc.add_new_vm("QubesTemplateVm", template=None, name=name,
                                pool_name=self.POOL_NAME)
        vm.clone_attrs(template)
        vm.clone_disk_files(src_vm=template, verbose=False)

        return vm
