# -*- encoding: utf-8 -*-
#
# The Qubes OS Project, http://www.qubes-os.org
#
# Copyright (C) 2017 Marek Marczykowski-Górecki
#                               <marmarek@invisiblethingslab.com>
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
# with this program; if not, see <http://www.gnu.org/licenses/>.

'''Extension responsible for qvm-service framework'''

import qubes.ext

class ServicesExtension(qubes.ext.Extension):
    '''This extension export features with 'service.' prefix to QubesDB in
    /qubes-service/ tree.
    '''
    # pylint: disable=no-self-use
    @qubes.ext.handler('domain-qdb-create')
    def on_domain_qdb_create(self, vm, event):
        '''Actually export features'''
        # pylint: disable=unused-argument
        for feature, value in vm.features.items():
            if not feature.startswith('service.'):
                continue
            service = feature[len('service.'):]
            # forcefully convert to '0' or '1'
            vm.untrusted_qdb.write('/qubes-service/{}'.format(service),
                str(int(bool(value))))

    @qubes.ext.handler('domain-feature-set')
    def on_domain_feature_set(self, vm, event, feature, value, oldvalue=None):
        '''Update /qubes-service/ QubesDB tree in runtime'''
        # pylint: disable=unused-argument
        if not vm.is_running():
            return
        if not feature.startswith('service.'):
            return
        service = feature[len('service.'):]
        # forcefully convert to '0' or '1'
        vm.untrusted_qdb.write('/qubes-service/{}'.format(service),
            str(int(bool(value))))

    @qubes.ext.handler('domain-feature-delete')
    def on_domain_feature_delete(self, vm, event, feature):
        '''Update /qubes-service/ QubesDB tree in runtime'''
        # pylint: disable=unused-argument
        if not vm.is_running():
            return
        if not feature.startswith('service.'):
            return
        service = feature[len('service.'):]
        vm.untrusted_qdb.rm('/qubes-service/{}'.format(service))
